"""
Backfill creation for InductOne Instances that predate the formal workflow.

Used for units that were built and shipped before the InductOne Build →
Completion → As-Built → Instance pipeline existed. These units have no
Build record, no Completion record, and no As-Built Record in ERPNext.
The only record they get is the Instance itself, created directly from
serial data collected on-site.

Design decisions:
  - No fabricated As-Built Record. The Instance stands alone.
  - as_built_record field is left blank (field is not reqd in the DocType;
    if your DocType has it marked reqd, this function works around it by
    inserting with ignore_mandatory=True — the field is intentionally empty
    for backfill units, which is more honest than a fake record).
  - born_at is set to the actual build date, not the system timestamp.
  - status is set to 'Installed' — these units are already in the field.
  - installed_at is set to the build date as the best available proxy.
  - A backfill_notes field records the provenance gap explicitly.
  - Component serials are stored in the InductOne Instance Serial child table.
"""

import frappe
from frappe import _
from frappe.utils import getdate


def create_backfill_instance(
    system_serial,
    build_date,
    builder_supplier,
    deployment_site,
    serials,
    backfill_notes=None,
    user=None,
):
    """
    Create an InductOne Instance record for a unit that predates the
    formal workflow. Called from bench console scripts.

    Args:
        system_serial   (str):  The IND-#### stenciled on the unit.
        build_date      (str):  ISO date string, e.g. "2025-10-29".
        builder_supplier(str):  Exact ERPNext Supplier record name.
        deployment_site (str):  Free-text site name, e.g. "UPS Worldport".
        serials         (list): List of dicts with keys:
                                  component_label (str)
                                  serial_number   (str)
        backfill_notes  (str):  Optional extra context. A standard note
                                is always prepended regardless.
        user            (str):  ERPNext user to record as born_by.
                                Defaults to frappe.session.user.

    Returns:
        str: The name of the created Instance record (== system_serial).

    Raises:
        frappe.ValidationError if the serial already exists.
    """
    if not system_serial:
        frappe.throw(_("system_serial is required."))
    if not build_date:
        frappe.throw(_("build_date is required."))
    if not builder_supplier:
        frappe.throw(_("builder_supplier is required."))

    user = user or frappe.session.user

    # Guard against duplicates
    existing = frappe.db.exists("InductOne Instance", system_serial)
    if existing:
        frappe.throw(_(
            "InductOne Instance '{0}' already exists. "
            "Cannot create a duplicate backfill record."
        ).format(system_serial))

    # Verify supplier exists
    if not frappe.db.exists("Supplier", builder_supplier):
        frappe.throw(_(
            "Supplier '{0}' not found in ERPNext. "
            "Check the exact name in your Supplier list."
        ).format(builder_supplier))

    build_date_obj = getdate(build_date)

    standard_note = (
        "BACKFILL — unit predates formal InductOne workflow. "
        "No Build, Completion, or As-Built Record exists in ERPNext. "
        "Serial data collected on-site. "
        "Builder release, acceptance, and audit trail are not available."
    )
    full_notes = standard_note
    if backfill_notes:
        full_notes = standard_note + "\n\n" + backfill_notes.strip()

    instance = frappe.new_doc("InductOne Instance")
    instance.system_serial = system_serial
    instance.status = "Installed"

    # born_at and installed_at set to actual build date, not system time
    instance.born_at = build_date_obj
    instance.born_by = user
    instance.installed_at = build_date_obj

    # Provenance — all blank/null; no fabricated links
    instance.inductone_build = None
    instance.as_built_record = None
    instance.configuration_order = None

    # Builder and site
    instance.builder_supplier = builder_supplier
    instance.deployment_site = deployment_site

    # Notes
    instance.notes = full_notes

    # Component serials
    for row in (serials or []):
        label = (row.get("component_label") or "").strip()
        serial = (row.get("serial_number") or "").strip()
        if not label or not serial:
            continue
        instance.append("component_serials", {
            "component_label": label,
            "serial_number": serial,
        })

    instance.insert(ignore_permissions=True, ignore_mandatory=True)

    frappe.db.commit()

    return instance.name
