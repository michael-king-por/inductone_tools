"""Customer-root POR Physical Location tree + FCO list labels.

This patch is intentionally data-derived and idempotent:

- create one Customer POR Physical Location node for each existing non-empty
  location customer;
- reparent Site nodes under their Customer node;
- recompute readable Customer / Site / Lane / Cell full paths;
"""

from __future__ import annotations

import frappe


LOCATION_DOCTYPE = "POR Physical Location"
INSTANCE_DOCTYPE = "InductOne Instance"
REQUEST_DOCTYPE = "InductOne Field Change Request"
FIELD_CHANGE_DOCTYPE = "InductOne Field Change"


def execute():
    if not frappe.db.exists("DocType", LOCATION_DOCTYPE):
        return

    ensure_schema_support()
    customer_nodes = ensure_customer_nodes()
    reparent_sites(customer_nodes)
    refresh_full_paths()
    refresh_instance_deployment_labels()
    frappe.clear_cache()


def ensure_schema_support() -> None:
    """Patch-time schema support.

    Frappe runs patches before fixture sync, so this data migration cannot rely
    on the updated DocType fixture already being applied.
    """

    _set_docfield_options(
        LOCATION_DOCTYPE,
        "location_type",
        "Customer\nSite\nLane\nCell\nRobot",
    )
    _set_docfield_options(
        LOCATION_DOCTYPE,
        "naming_series",
        "POR-CUST.####\nPOR-SITE.####\nPOR-LANE.####\nPOR-CELL.####\nPOR-ROBOT.####",
    )


def _set_docfield_options(parent: str, fieldname: str, options: str) -> None:
    name = frappe.db.get_value("DocField", {"parent": parent, "fieldname": fieldname}, "name")
    if name:
        frappe.db.set_value("DocField", name, "options", options, update_modified=False)


def ensure_customer_nodes() -> dict[str, str]:
    customers = sorted(
        {
            row.customer
            for row in frappe.get_all(
                LOCATION_DOCTYPE,
                filters={"customer": ["is", "set"]},
                fields=["customer"],
            )
            if row.customer
        }
    )

    customer_nodes: dict[str, str] = {}
    for customer in customers:
        existing = frappe.db.get_value(
            LOCATION_DOCTYPE,
            {"location_type": "Customer", "customer": customer},
            "name",
        )
        if existing:
            customer_nodes[customer] = existing
            continue

        doc = frappe.get_doc(
            {
                "doctype": LOCATION_DOCTYPE,
                "naming_series": "POR-CUST.####",
                "location_type": "Customer",
                "location_code": customer,
                "location_name": customer,
                "customer": customer,
                "is_group": 1,
                "full_path": customer,
            }
        )
        doc.insert(ignore_permissions=True)
        customer_nodes[customer] = doc.name

    return customer_nodes


def reparent_sites(customer_nodes: dict[str, str]) -> None:
    for row in frappe.get_all(
        LOCATION_DOCTYPE,
        filters={"location_type": "Site", "customer": ["is", "set"]},
        fields=["name", "customer", "parent_por_physical_location"],
    ):
        parent = customer_nodes.get(row.customer)
        if not parent or row.parent_por_physical_location == parent:
            continue
        doc = frappe.get_doc(LOCATION_DOCTYPE, row.name)
        doc.parent_por_physical_location = parent
        doc.save(ignore_permissions=True)


def refresh_full_paths() -> None:
    rows = frappe.get_all(
        LOCATION_DOCTYPE,
        fields=[
            "name",
            "location_type",
            "location_name",
            "location_code",
            "parent_por_physical_location",
        ],
        order_by="lft asc",
    )
    by_name = {row.name: row for row in rows}

    def label(row) -> str:
        return (row.location_name or row.location_code or row.name or "").strip()

    def path_for(row) -> str:
        parts = [label(row)]
        parent_name = row.parent_por_physical_location
        while parent_name:
            parent = by_name.get(parent_name)
            if not parent:
                break
            parts.append(label(parent))
            parent_name = parent.parent_por_physical_location
        return " / ".join(reversed([part for part in parts if part]))

    for row in rows:
        path = path_for(row)
        is_group = 1 if row.location_type in {"Customer", "Site", "Lane"} else 0
        frappe.db.set_value(
            LOCATION_DOCTYPE,
            row.name,
            {"full_path": path, "is_group": is_group},
            update_modified=False,
        )


def refresh_instance_deployment_labels() -> None:
    if not frappe.db.exists("DocType", INSTANCE_DOCTYPE):
        return
    for row in frappe.get_all(
        INSTANCE_DOCTYPE,
        filters={"physical_location": ["is", "set"]},
        fields=["name", "physical_location"],
    ):
        full_path = frappe.db.get_value(LOCATION_DOCTYPE, row.physical_location, "full_path")
        if full_path:
            frappe.db.set_value(
                INSTANCE_DOCTYPE,
                row.name,
                "deployment_site",
                full_path,
                update_modified=False,
            )

