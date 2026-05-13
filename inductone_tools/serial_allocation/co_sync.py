"""
Build <-> Configuration Order serial sync helpers.

These functions are called from existing CO-related code to keep the
system_serial in sync. Three integration points:

  1. CO generation (whichever function creates a new CO from a Build):
     call stamp_co_with_build_serial(co, build) after assigning the
     basic CO fields, before insert.

  2. Allocate Serial button flow: handled in
     serial_allocation/release.py via _propagate_serial_to_existing_cos.

  3. Release-to-builder gate: call assert_co_has_serial(co_name) at the
     top of release_to_builder_now (or wherever the CO transitions out
     of Draft / Released).
"""

import frappe
from frappe import _


def stamp_co_with_build_serial(co_doc, build_doc=None):
    """
    Stamp the CO's system_serial from its parent Build, if the Build has
    one. Called during CO generation.

    Args:
        co_doc: an unsaved (or saved) CO Document instance.
        build_doc: optional Build Document. If not provided, looked up
                   from co_doc.inductone_build.

    Returns:
        The serial that was stamped, or None if there was nothing to stamp.

    Behavior:
        - If Build has no system_serial: no-op, returns None.
        - If CO already has the same serial: no-op, returns the serial.
        - If CO already has a different serial: raises. This indicates
          a data inconsistency that should be fixed manually, not
          silently overwritten.
    """
    if not co_doc:
        return None

    if build_doc is None:
        build_name = getattr(co_doc, "inductone_build", None)
        if not build_name:
            return None
        build_doc = frappe.get_doc("InductOne Build", build_name)

    build_serial = getattr(build_doc, "system_serial", None)
    if not build_serial:
        return None

    co_serial = getattr(co_doc, "system_serial", None)

    if co_serial == build_serial:
        return build_serial

    if co_serial and co_serial != build_serial:
        frappe.throw(_(
            "Refusing to stamp CO {0}: it already has system_serial '{1}', "
            "but the parent Build {2} has '{3}'. "
            "Investigate this mismatch manually."
        ).format(
            co_doc.name or "(unsaved)",
            co_serial,
            build_doc.name,
            build_serial,
        ))

    # Empty — safe to stamp.
    co_doc.system_serial = build_serial
    return build_serial


def assert_co_has_serial(co_name):
    """
    Release gate. Raises ValidationError if the CO has no system_serial.
    Called at the top of release_to_builder_now (or wherever the CO
    leaves Draft state).

    The serial must be present BEFORE release because the release
    package (CO PDF, builder instructions) needs to communicate the
    serial to the builder. Without it, the builder has no instruction
    on what to stencil.
    """
    if not co_name:
        frappe.throw(_("co_name is required for release gate check."))

    co = frappe.db.get_value(
        "InductOne Configuration Order",
        co_name,
        ["system_serial", "inductone_build"],
        as_dict=True,
    )
    if not co:
        frappe.throw(_("Configuration Order {0} not found.").format(co_name))

    if co.get("system_serial"):
        return  # Gate passes.

    # Gate fails — produce an actionable error.
    build_name = co.get("inductone_build")
    if build_name:
        build_serial = frappe.db.get_value(
            "InductOne Build", build_name, "system_serial"
        )
        if build_serial:
            # Build has it; CO doesn't. Stamp it now and proceed.
            frappe.db.set_value(
                "InductOne Configuration Order",
                co_name,
                "system_serial",
                build_serial,
                update_modified=False,
            )
            return

    frappe.throw(_(
        "Cannot release Configuration Order {0}: no system_serial has "
        "been allocated. The serial must be allocated on the parent "
        "InductOne Build before release, so it can be communicated to "
        "the builder in the release package. "
        "Open Build {1} and click 'Allocate Serial', then retry."
    ).format(co_name, build_name or "(unknown)"))
