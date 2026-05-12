"""
Instance creation logic for InductOne.

This module owns the "birth" of an InductOne Instance from an accepted
As-Built Record. It is called from inside the atomic acceptance flow
(see acceptance.py: accept_completion_create_as_built) after the As-Built
is locked, the CO is closed, and the Build is marked COMPLETED.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime


def create_instance_from_as_built(as_built_name, user=None):
    """
    Create the InductOne Instance record for a locked As-Built Record.

    Preconditions:
      - The As-Built Record exists and is in status 'Locked'.
      - The As-Built has a populated system_serial (inherited from Build).
      - No Instance already exists for this As-Built (1:1 invariant).

    Returns the new Instance name. Does not commit — caller owns transaction.
    """
    if not as_built_name:
        frappe.throw(_("as_built_name is required."))

    user = user or frappe.session.user

    as_built = frappe.get_doc("InductOne As-Built Record", as_built_name)

    if as_built.status != "Locked":
        frappe.throw(_(
            "Cannot create Instance from As-Built {0}: status is '{1}', expected 'Locked'."
        ).format(as_built_name, as_built.status))

    existing = frappe.db.get_value(
        "InductOne Instance",
        {"as_built_record": as_built_name},
        "name",
    )
    if existing:
        frappe.throw(_(
            "Instance already exists for As-Built {0}: {1}. "
            "Each As-Built can produce only one Instance."
        ).format(as_built_name, existing))

    build = frappe.get_doc("InductOne Build", as_built.inductone_build)

    system_serial = getattr(build, "system_serial", None)
    if not system_serial:
        frappe.throw(_(
            "Cannot create Instance: source Build {0} has no system_serial. "
            "The serial should have been allocated at builder release. "
            "Allocate via the Builder Tranche system before retrying."
        ).format(build.name))

    sales_order_name = getattr(build, "sales_order", None)
    customer = None
    if sales_order_name:
        customer = frappe.db.get_value("Sales Order", sales_order_name, "customer")

    config_summary = _build_configuration_summary(build)
    builder_tranche = _resolve_tranche_for_serial(system_serial)

    instance = frappe.new_doc("InductOne Instance")
    instance.system_serial = system_serial
    instance.status = "Ready for Ship"
    instance.born_at = now_datetime()
    instance.born_by = user

    instance.inductone_build = build.name
    instance.as_built_record = as_built.name
    instance.configuration_order = as_built.configuration_order
    instance.builder_supplier = as_built.builder_supplier or getattr(build, "builder_supplier", None)
    if builder_tranche:
        instance.builder_tranche = builder_tranche

    instance.sales_order = sales_order_name
    instance.customer = customer
    instance.customer_project_label = getattr(build, "customer_project_label", None)
    instance.orientation = getattr(build, "orientation", None)
    instance.top_item = getattr(build, "top_item", None)

    instance.configuration_summary = config_summary

    instance.insert(ignore_permissions=True)

    return instance.name


def _build_configuration_summary(build):
    """Produce a human-readable, line-per-option summary of the build's
    selected options at acceptance. Frozen text artifact."""
    if not getattr(build, "selections", None):
        return ""

    lines = []
    for row in build.selections:
        if hasattr(row, "is_selected") and not getattr(row, "is_selected", False):
            continue
        category = (getattr(row, "option_category", "") or "").strip()
        code = (getattr(row, "option_code", "") or "").strip()
        name = (getattr(row, "option_name", "") or "").strip()
        if not code:
            continue
        if category:
            lines.append("{0}: {1} — {2}".format(category, code, name))
        else:
            lines.append("{0} — {1}".format(code, name))

    return "\n".join(lines) if lines else ""


def _resolve_tranche_for_serial(system_serial):
    """Look up which tranche produced a given serial. Returns tranche name
    or None. Not fatal if missing."""
    if not system_serial or not system_serial.startswith("IND-"):
        return None

    suffix = system_serial[4:]
    if not suffix.isdigit():
        return None

    serial_int = int(suffix)

    rows = frappe.db.sql(
        """
        SELECT name
        FROM `tabInductOne Builder Tranche`
        WHERE tranche_start <= %(s)s AND tranche_end >= %(s)s
        LIMIT 1
        """,
        {"s": serial_int},
        as_dict=True,
    )
    if rows:
        return rows[0]["name"]
    return None
