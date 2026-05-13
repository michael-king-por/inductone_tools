"""
Release-time serial allocation for InductOne Builds.

Called from the InductOne Build form via client-script button before
release_to_builder_now.

Now also propagates the allocated serial to any existing InductOne
Configuration Order(s) for the same build. This ensures that the CO
print format and the builder readme always reflect the current serial
state, regardless of whether the CO was generated before or after
serial allocation.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from inductone_tools.serial_allocation.tranche import (
    allocate_next_serial,
)


@frappe.whitelist()
def allocate_serial_for_build(build_name):
    """
    Allocate the next system_serial for an InductOne Build from the active
    tranche of its builder_supplier. Stamps the Build with the result.
    Also stamps any existing CO that links back to this Build.

    Idempotent: if a serial is already allocated, returns it without
    re-allocating. Will still backfill any CO that's missing the serial
    even on idempotent calls, so the CO and Build stay in sync.
    """
    if not build_name:
        frappe.throw(_("build_name is required."))

    build = frappe.get_doc("InductOne Build", build_name)

    existing = getattr(build, "system_serial", None)
    if existing:
        # Idempotent path — but still ensure CO is in sync.
        co_updates = _propagate_serial_to_existing_cos(build_name, existing)
        return {
            "ok": True,
            "already_allocated": True,
            "system_serial": existing,
            "build_name": build_name,
            "co_updates": co_updates,
        }

    if not getattr(build, "builder_supplier", None):
        frappe.throw(_(
            "Cannot allocate serial: Build {0} has no builder_supplier set. "
            "Choose a builder first."
        ).format(build_name))

    status = getattr(build, "build_status", None)
    blocked_states = {"RELEASED_TO_BUILDER", "SUPERSEDED", "COMPLETED"}
    if status in blocked_states:
        frappe.throw(_(
            "Cannot allocate serial: Build {0} is in status '{1}'. "
            "Serial allocation is only permitted before release."
        ).format(build_name, status))

    user = frappe.session.user
    now = now_datetime()

    result = allocate_next_serial(build.builder_supplier, user=user)

    build.db_set("system_serial", result["serial"], update_modified=True)
    build.db_set("builder_tranche", result["tranche_name"], update_modified=False)
    build.db_set("serial_allocated_at", now, update_modified=False)
    build.db_set("serial_allocated_by", user, update_modified=False)

    # Propagate to any CO(s) that already exist for this Build.
    co_updates = _propagate_serial_to_existing_cos(build_name, result["serial"])

    return {
        "ok": True,
        "already_allocated": False,
        "system_serial": result["serial"],
        "tranche_name": result["tranche_name"],
        "build_name": build_name,
        "co_updates": co_updates,
    }


def _propagate_serial_to_existing_cos(build_name, system_serial):
    """
    Find any InductOne Configuration Order(s) linked to this Build and
    stamp the system_serial onto them if not already set.

    Returns a list of CO names that were updated. An empty list means
    either no COs exist for this Build, or all existing COs already had
    the same serial.

    Does NOT overwrite a CO that has a different serial — that would
    indicate a data inconsistency and should be investigated, not
    silently corrected.
    """
    cos = frappe.get_all(
        "InductOne Configuration Order",
        filters={"inductone_build": build_name},
        fields=["name", "system_serial"],
    )

    updated = []
    for co in cos:
        current = co.get("system_serial")
        if current == system_serial:
            continue
        if current and current != system_serial:
            frappe.log_error(
                title="Serial mismatch on CO",
                message=(
                    f"CO {co['name']} has system_serial '{current}' but "
                    f"Build {build_name} now has '{system_serial}'. "
                    f"Not overwriting. Investigate manually."
                ),
            )
            continue
        # Empty current value — safe to stamp.
        frappe.db.set_value(
            "InductOne Configuration Order",
            co["name"],
            "system_serial",
            system_serial,
            update_modified=False,
        )
        updated.append(co["name"])

    return updated


@frappe.whitelist()
def preview_serial_for_build(build_name):
    """Read-only preview of what serial would be allocated."""
    from inductone_tools.serial_allocation.tranche import (
        preview_next_serial,
    )

    if not build_name:
        return {"ok": False, "error": "build_name required"}

    build = frappe.db.get_value(
        "InductOne Build",
        build_name,
        ["builder_supplier", "system_serial"],
        as_dict=True,
    )
    if not build:
        return {"ok": False, "error": "build not found"}

    if build.get("system_serial"):
        return {
            "ok": True,
            "already_allocated": True,
            "serial": build["system_serial"],
        }

    if not build.get("builder_supplier"):
        return {"ok": False, "error": "builder_supplier not set on build"}

    preview = preview_next_serial(build["builder_supplier"])
    return preview
