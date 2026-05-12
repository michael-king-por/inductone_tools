"""
Release-time serial allocation for InductOne Builds.

Called from the InductOne Build form via client-script button before
release_to_builder_now.
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

    Idempotent: if a serial is already allocated, returns it without re-allocating.
    """
    if not build_name:
        frappe.throw(_("build_name is required."))

    build = frappe.get_doc("InductOne Build", build_name)

    existing = getattr(build, "system_serial", None)
    if existing:
        return {
            "ok": True,
            "already_allocated": True,
            "system_serial": existing,
            "build_name": build_name,
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

    return {
        "ok": True,
        "already_allocated": False,
        "system_serial": result["serial"],
        "tranche_name": result["tranche_name"],
        "build_name": build_name,
    }


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
