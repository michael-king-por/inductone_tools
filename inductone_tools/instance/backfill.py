"""
Backfill creation for InductOne Instances that exist outside the formal
workflow.

Used for units that were built (and sometimes also shipped or installed)
before the InductOne Build -> Completion -> As-Built -> Instance pipeline
was applied to them. These units have no Build record, no Completion
record, and no As-Built Record in ERPNext. The only record they get is
the Instance itself, created directly from serial data captured by
whatever out-of-band means existed (on-site serial form, builder
workbook, etc.).

Design decisions:
  - No fabricated As-Built Record. The Instance stands alone.
  - inductone_build, as_built_record, and configuration_order are all
    required Link fields on the DocType. We leave them null and insert
    with ignore_mandatory=True. Honest absence beats fabricated records.
  - born_at is set to the actual acceptance/build date, not the system
    timestamp. For field-found backfills this is the on-site date; for
    just-accepted backfills it is the acceptance date.
  - status is parameterized. The original use case (field-found units)
    was Installed; the IND-3001 use case (accepted-but-not-shipped) is
    Ready for Ship. Default remains Installed to preserve original
    behavior. Callers may also pass Shipped if appropriate.
  - deployment_site is only required when status == Installed. For
    earlier-lifecycle statuses (Ready for Ship, Shipped) the site may
    not yet be known.
  - installed_at is only stamped when status == Installed.
  - backfill_notes records the provenance gap explicitly.
  - Component serials are stored in the InductOne Instance Serial child
    table.
"""

import frappe
from frappe import _
from frappe.utils import getdate


_VALID_STATUSES = ("Ready for Ship", "Shipped", "Installed")


def create_backfill_instance(
    system_serial,
    build_date,
    builder_supplier,
    serials,
    deployment_site=None,
    physical_location=None,
    status="Installed",
    backfill_notes=None,
    user=None,
):
    """
    Create an InductOne Instance record for a unit that exists outside
    the formal workflow. Called from bench console scripts.

    Args:
        system_serial   (str):  The IND-#### stenciled on the unit.
        build_date      (str):  ISO date string, e.g. "2025-10-29". Used
                                as born_at and (if status == Installed)
                                installed_at.
        builder_supplier(str):  Exact ERPNext Supplier record name.
        serials         (list): List of dicts with keys:
                                  component_label (str)
                                  serial_number   (str)
        deployment_site (str):  Free-text site label. Used only as a fallback
                                when no canonical physical_location is known.
        physical_location(str): Optional POR Physical Location Cell link. When
                                supplied, deployment_site is derived from the
                                Cell's full_path.
        status          (str):  One of "Ready for Ship", "Shipped",
                                "Installed". Defaults to "Installed" to
                                preserve original behavior.
        backfill_notes  (str):  Optional extra context. A standard
                                provenance note is always prepended.
        user            (str):  ERPNext user to record as born_by.
                                Defaults to frappe.session.user.

    Returns:
        str: The name of the created Instance record (== system_serial).

    Raises:
        frappe.ValidationError on any of:
            - missing required arg
            - status not in allowed set
            - status == Installed without deployment_site
            - duplicate Instance with this serial
            - unknown Supplier
    """
    if not system_serial:
        frappe.throw(_("system_serial is required."))
    if not build_date:
        frappe.throw(_("build_date is required."))
    if not builder_supplier:
        frappe.throw(_("builder_supplier is required."))

    if status not in _VALID_STATUSES:
        frappe.throw(_(
            "status must be one of {0}. Got: {1}"
        ).format(", ".join(_VALID_STATUSES), status))

    if physical_location:
        location = frappe.db.get_value(
            "POR Physical Location",
            physical_location,
            ["name", "location_type", "full_path"],
            as_dict=True,
        )
        if not location:
            frappe.throw(_("POR Physical Location '{0}' not found.").format(physical_location))
        if location.location_type != "Cell":
            frappe.throw(_("physical_location must point to a Cell location."))
        deployment_site = location.full_path or deployment_site

    if status == "Installed" and not (deployment_site or physical_location):
        frappe.throw(_(
            "deployment_site or physical_location is required when status is Installed."
        ))

    user = user or frappe.session.user

    if frappe.db.exists("InductOne Instance", system_serial):
        frappe.throw(_(
            "InductOne Instance '{0}' already exists. "
            "Cannot create a duplicate backfill record."
        ).format(system_serial))

    if not frappe.db.exists("Supplier", builder_supplier):
        frappe.throw(_(
            "Supplier '{0}' not found in ERPNext. "
            "Check the exact name in your Supplier list."
        ).format(builder_supplier))

    build_date_obj = getdate(build_date)

    standard_note = (
        "BACKFILL -- unit exists outside the formal InductOne workflow. "
        "No Build, Completion, or As-Built Record exists in ERPNext. "
        "Serial data captured out-of-band (on-site form or builder "
        "workbook). Builder release, acceptance, and audit trail "
        "are not available."
    )
    full_notes = standard_note
    if backfill_notes:
        full_notes = standard_note + "\n\n" + backfill_notes.strip()

    instance = frappe.new_doc("InductOne Instance")
    instance.system_serial = system_serial
    instance.status = status

    # born_at: acceptance moment (per DocType description). For
    # field-found backfills this is the on-site build date; for
    # just-accepted backfills this is the acceptance date.
    instance.born_at = build_date_obj
    instance.born_by = user
    instance.build_date = build_date_obj

    # installed_at only when actually installed
    if status == "Installed":
        instance.installed_at = build_date_obj

    # All three required Link fields stay null.
    instance.inductone_build = None
    instance.as_built_record = None
    instance.configuration_order = None

    instance.builder_supplier = builder_supplier
    instance.deployment_site = deployment_site  # may be None for pre-install
    if physical_location:
        instance.physical_location = physical_location

    instance.backfill_notes = full_notes

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
