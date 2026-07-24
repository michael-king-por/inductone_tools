"""Update Custom DocPerm fixtures for hardened operational roles.

This script is intentionally checked into the repo as an audit artifact. It
turns the agreed role model into concrete Custom DocPerm fixture rows for
standard ERPNext/business doctypes.

It does not assign users to roles. User assignment remains operational database
state and is validated separately in the candidate sandbox.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "inductone_tools" / "fixtures" / "custom_docperm.json"

PERM_FIELDS = [
    "read",
    "write",
    "create",
    "delete",
    "submit",
    "cancel",
    "amend",
    "report",
    "export",
    "import",
    "share",
    "print",
    "email",
    "select",
    "if_owner",
]

RETIRED_ROLES = {
    "Finance Viewer",
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def name_for(parent: str, role: str, permlevel: int) -> str:
    suffix = "" if int(permlevel or 0) == 0 else f"__level_{int(permlevel)}"
    return f"perm_{slug(parent)}__{slug(role)}{suffix}"


def base_row(parent: str, role: str, permlevel: int = 0) -> dict:
    row = {
        "docstatus": 0,
        "doctype": "Custom DocPerm",
        "name": name_for(parent, role, permlevel),
        "parent": parent,
        "parentfield": "permissions",
        "parenttype": "DocType",
        "permlevel": int(permlevel or 0),
        "role": role,
    }
    row.update({field: 0 for field in PERM_FIELDS})
    return row


def merge_bits(existing: dict, bits: dict) -> None:
    for field in PERM_FIELDS:
        existing[field] = int(bool(existing.get(field) or bits.get(field)))


def add_perm(rows: dict, parent: str, role: str, permlevel: int = 0, **bits: int) -> None:
    if role in RETIRED_ROLES:
        return
    key = (parent, role, int(permlevel or 0))
    if key not in rows:
        rows[key] = base_row(parent, role, permlevel)
    merge_bits(rows[key], bits)


READ = {
    "read": 1,
    "report": 1,
    "export": 1,
    "print": 1,
    "select": 1,
}

GLOBAL_VIEWER = {
    "read": 1,
    "write": 0,
    "create": 0,
    "delete": 0,
    "submit": 0,
    "cancel": 0,
    "amend": 0,
    "report": 1,
    "export": 1,
    "import": 0,
    "share": 0,
    "print": 1,
    "email": 0,
    "select": 0,
    "if_owner": 0,
}

MAINTAIN = {
    "read": 1,
    "write": 1,
    "create": 1,
    "delete": 0,
    "report": 1,
    "export": 1,
    "import": 1,
    "print": 1,
    "email": 1,
    "share": 1,
    "select": 1,
}

TRANSACTION = {
    **MAINTAIN,
    "submit": 1,
    "cancel": 1,
    "amend": 1,
}

SYSTEM_FULL = {
    **MAINTAIN,
    "delete": 1,
}

LIMITED_WRITE = {
    "read": 1,
    "write": 1,
    "create": 0,
    "delete": 0,
    "submit": 0,
    "cancel": 0,
    "amend": 0,
    "report": 1,
    "export": 1,
    "import": 0,
    "print": 1,
    "email": 1,
    "share": 0,
    "select": 1,
}


# Core business documents the Operations Viewer should be able to inspect
# without mutation. Finance/audit broad read visibility now lives in Global
# Viewer, which is generated across all applicable DocTypes.
BUSINESS_READ_DOCS = [
    "Item",
    "BOM",
    "Product Bundle",
    "Sales Order",
    "Delivery Note",
    "Stock Entry",
    "Stock Ledger Entry",
    "Serial and Batch Bundle",
    "Batch",
    "Warehouse",
    "Bin",
    "Serial No",
    "Work Order",
    "Purchase Order",
    "Purchase Receipt",
    "Purchase Invoice",
    "Sales Invoice",
    "Payment Entry",
    "Company",
    "Currency",
    "Territory",
    "Fiscal Year",
    "Supplier",
    "Customer",
    "Address",
    "Contact",
    "Item Price",
    "Price List",
    "UOM",
    "Item Group",
    "Brand",
    "Stock Reconciliation",
    "Material Request",
    "Pick List",
    "Packed Item",
    "Account",
    "GL Entry",
    "Journal Entry",
    "Cost Center",
    "Payment Ledger Entry",
]


# Operations Manager owns normal non-InductOne operational execution. This is
# deliberately not an accounting mutation role.
OPERATIONS_MANAGER_MASTER_DOCS = [
    "Item",
    "BOM",
    "Product Bundle",
    "Warehouse",
    "Serial No",
    "Item Group",
    "Brand",
    "UOM",
    "Supplier",
    "Customer",
    "Address",
    "Contact",
    "Item Price",
    "Price List",
]

OPERATIONS_MANAGER_TRANSACTION_DOCS = [
    "Sales Order",
    "Delivery Note",
    "Stock Entry",
    "Work Order",
    "Purchase Order",
    "Purchase Receipt",
    "Material Request",
    "Pick List",
    "Stock Reconciliation",
]


# Inventory Operator can execute movement/count/receiving/shipping workflows,
# but does not own master data like Item/BOM/Sales Order.
INVENTORY_TRANSACTION_DOCS = [
    "Delivery Note",
    "Stock Entry",
    "Purchase Receipt",
    "Material Request",
    "Pick List",
    "Stock Reconciliation",
]

INVENTORY_READ_DOCS = [
    "Item",
    "BOM",
    "Product Bundle",
    "Sales Order",
    "Purchase Order",
    "Warehouse",
    "Bin",
    "Serial No",
    "Stock Ledger Entry",
    "Work Order",
    "Supplier",
    "Customer",
]


# Serialized gripper manufacturing/refurbishment role: manufacturing execution
# only, without general InductOne or ERP master-data ownership.
GRIPPER_TRANSACTION_DOCS = ["Work Order", "Stock Entry", "Pick List"]
GRIPPER_READ_DOCS = [
    "Item",
    "BOM",
    "Product Bundle",
    "Warehouse",
    "Bin",
    "Serial No",
    "Stock Ledger Entry",
]

TRANSACTION_ROLE_DEPENDENCIES = {
    "Operations Manager": {
        "transaction": ["Serial and Batch Bundle"],
        "maintain": ["Batch", "Serial No"],
        "read": ["Company", "Currency", "Fiscal Year", "Territory", "Account"],
    },
    "Inventory Operator": {
        "transaction": ["Serial and Batch Bundle"],
        "maintain": ["Batch", "Serial No"],
        "read": ["Company", "Currency", "Fiscal Year", "Territory"],
    },
    "Gripper Manufacturer": {
        "transaction": ["Serial and Batch Bundle"],
        "maintain": ["Batch", "Serial No"],
        "read": ["Company", "Currency", "Fiscal Year", "Territory"],
    },
}


# Procurement maintains purchasing/commercial metadata. It can write Item level
# 0 and pricing/vendor records, but only read Item permlevel 1 so it cannot
# silently mutate valuation/opening-stock-adjacent fields just to reach
# standard_rate.
PROCUREMENT_WRITE_DOCS = [
    "Item",
    "Supplier",
    "Address",
    "Contact",
    "Item Price",
    "Price List",
    "UOM",
    "Item Group",
    "Brand",
]
PROCUREMENT_READ_DOCS = [
    "BOM",
    "Product Bundle",
    "Purchase Order",
    "Purchase Receipt",
    "Purchase Invoice",
    "Stock Ledger Entry",
    "Warehouse",
    "Bin",
]


# Link-read dependencies surfaced by the static link dependency audit
# (scripts/run_static_link_dependency_audit.py, 2026-06-29). Each role can write
# a DocType that links to these targets but lacked read on the target itself,
# which breaks link resolution / list lookups on the form.
#
# IMPORTANT: only DocTypes ALREADY managed by this fixture are listed here.
# Adding the *first* Custom DocPerm row to an unmanaged DocType makes Frappe
# ignore ALL of that DocType's standard DocPerms, stripping access from every
# other role. The unmanaged live targets (Country, Stock Entry Type, User) are
# intentionally NOT handled here; see
# docs/security/downstream-loss-triage-2026-06-29.md for their gameplan.
LINK_READ_DEPENDENCIES_MANAGED = {
    # Engineering signoff users review BOMs and need report access to BOM-backed
    # engineering reports such as Electrical Balloon Callouts.
    "Engineering User": ["BOM"],
    # InductOne lifecycle roles read the standard records their own InductOne
    # DocTypes link to (Build / Configuration Order / Snapshot / Export Package),
    # so the role is self-sufficient instead of depending on being paired with
    # Operations Manager.
    "InductOne Manager": ["Item", "BOM", "Sales Order", "Supplier"],
    "InductOne Process Architect": ["Item", "BOM", "Sales Order", "Supplier"],
    # Procurement maintains Price List and creates Purchase Orders; those
    # workflows need Currency/Company link-read without broader ERP mutation.
    "Procurement User": ["Currency", "Company"],
    # Inventory Operator's Delivery Note references a selling Price List.
    "Inventory Operator": ["Price List"],
}


# Snapshot-managed standard DocTypes.
#
# Stock Entry Type was confirmed on 2026-06-29 to block Desk link selection
# for Operations Manager / Gripper Manufacturer. It previously had no Custom
# DocPerm rows, so adding a bare curated row would make Frappe ignore these
# standard DocPerms. We therefore snapshot the complete standard role set first,
# then add only the curated read rows needed by the hardened transaction roles.
STOCK_ENTRY_TYPE_STANDARD_DOCPERMS = [
    {
        "role": "System Manager",
        "permlevel": 0,
        "read": 1,
        "write": 1,
        "create": 1,
        "submit": 0,
        "cancel": 0,
        "amend": 0,
        "delete": 1,
        "report": 1,
        "export": 1,
        "import": 0,
        "share": 1,
        "print": 1,
        "email": 1,
        "select": 0,
        "if_owner": 0,
    },
    {
        "role": "Manufacturing Manager",
        "permlevel": 0,
        "read": 1,
        "write": 1,
        "create": 1,
        "submit": 0,
        "cancel": 0,
        "amend": 0,
        "delete": 1,
        "report": 1,
        "export": 1,
        "import": 0,
        "share": 1,
        "print": 1,
        "email": 1,
        "select": 0,
        "if_owner": 0,
    },
    {
        "role": "Stock Manager",
        "permlevel": 0,
        "read": 1,
        "write": 1,
        "create": 1,
        "submit": 0,
        "cancel": 0,
        "amend": 0,
        "delete": 1,
        "report": 1,
        "export": 1,
        "import": 0,
        "share": 1,
        "print": 1,
        "email": 1,
        "select": 0,
        "if_owner": 0,
    },
    {
        "role": "Stock User",
        "permlevel": 0,
        "read": 1,
        "write": 0,
        "create": 0,
        "submit": 0,
        "cancel": 0,
        "amend": 0,
        "delete": 0,
        "report": 0,
        "export": 0,
        "import": 0,
        "share": 0,
        "print": 0,
        "email": 0,
        "select": 0,
        "if_owner": 0,
    },
]

STOCK_ENTRY_TYPE_CURATED_READ_ROLES = [
    "Operations Manager",
    "Inventory Operator",
    "Gripper Manufacturer",
    # Read-only viewer tier: they can read Stock Entry, so the stock_entry_type
    # label should resolve for them once this DocType is Custom-DocPerm-managed.
    "Operations Viewer",
]


FCO_MANAGED_DOCTYPES = [
    "InductOne Field Change Request",
    "InductOne Field Change",
]

FCO_WRITE_ROLES = [
    "Operations Manager",
    "InductOne Manager",
    "InductOne Process Architect",
]

FCO_MAINTAIN = {
    **MAINTAIN,
    "import": 0,
}

FCO_SYSTEM = {
    **SYSTEM_FULL,
    "import": 0,
}

OPTIONS_CATALOG_DOCTYPE = "InductOne Options Catalog"
OPTIONS_CATALOG_PRINT_ROLES = [
    # Engineering signoff users need to review and print both the default
    # released-only catalog and the comprehensive filtered catalog.
    "Engineering User",
]


def load_rows() -> dict[tuple[str, str, int], dict]:
    current = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows: dict[tuple[str, str, int], dict] = {}
    for row in current:
        row = dict(row)
        if row.get("role") in RETIRED_ROLES:
            continue
        permlevel = int(row.get("permlevel") or 0)
        row["permlevel"] = permlevel
        row["name"] = name_for(row["parent"], row["role"], permlevel)
        for field in PERM_FIELDS:
            row[field] = int(bool(row.get(field)))
        key = (row["parent"], row["role"], permlevel)
        if key in rows:
            merge_bits(rows[key], row)
        else:
            rows[key] = row
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--site",
        help="Frappe site used when synchronizing live Custom DocPerm rows or adding Global Viewer to all DocTypes.",
    )
    parser.add_argument(
        "--sites-path",
        help="Frappe sites path used with --site.",
    )
    parser.add_argument(
        "--sync-current-custom-docperms",
        action="store_true",
        help=(
            "Read current candidate Custom DocPerm rows and add their keys to the "
            "fixture with deterministic names. This closes DB-only permission-key "
            "outliers without changing effective permissions."
        ),
    )
    parser.add_argument(
        "--global-viewer-all-doctypes",
        action="store_true",
        help=(
            "Add Global Viewer read/report/export/print rows for every non-child "
            "DocType. Previously unmanaged DocTypes are snapshot-managed first by "
            "copying their standard DocPerm rows into deterministic Custom DocPerm "
            "fixture rows, avoiding the Custom DocPerm replace-trap."
        ),
    )
    return parser.parse_args()


def require_frappe(args: argparse.Namespace):
    if not args.site or not args.sites_path:
        raise SystemExit("--site and --sites-path are required for this operation")

    import frappe

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    return frappe


def add_current_custom_docperms(rows: dict[tuple[str, str, int], dict], frappe) -> None:
    fields = ["parent", "role", "permlevel", *PERM_FIELDS]
    for row in frappe.get_all("Custom DocPerm", fields=fields, order_by="parent asc, role asc, permlevel asc"):
        if row.get("role") in RETIRED_ROLES:
            continue
        bits = {field: int(bool(row.get(field))) for field in PERM_FIELDS}
        add_perm(rows, row["parent"], row["role"], int(row.get("permlevel") or 0), **bits)


def non_child_doctypes(frappe) -> list[str]:
    return frappe.get_all(
        "DocType",
        filters={"istable": 0},
        pluck="name",
        order_by="name asc",
    )


def standard_docperms_for(frappe, doctype: str) -> list[dict]:
    return frappe.get_all(
        "DocPerm",
        filters={"parent": doctype},
        fields=["role", "permlevel", *PERM_FIELDS],
        order_by="role asc, permlevel asc",
    )


def add_global_viewer_all_doctypes(rows: dict[tuple[str, str, int], dict], frappe) -> None:
    managed_parents = {parent for (parent, _role, _lvl) in rows}
    for doctype in non_child_doctypes(frappe):
        if doctype not in managed_parents:
            for standard_row in standard_docperms_for(frappe, doctype):
                role = standard_row.get("role")
                if not role:
                    continue
                permlevel = int(standard_row.get("permlevel") or 0)
                bits = {field: int(bool(standard_row.get(field))) for field in PERM_FIELDS}
                add_perm(rows, doctype, role, permlevel=permlevel, **bits)
        add_perm(rows, doctype, "Global Viewer", **GLOBAL_VIEWER)


def main() -> None:
    args = parse_args()
    rows = load_rows()

    frappe = None
    if args.sync_current_custom_docperms or args.global_viewer_all_doctypes:
        frappe = require_frappe(args)
        if args.sync_current_custom_docperms:
            add_current_custom_docperms(rows, frappe)

    for role in ["Operations Viewer"]:
        for doctype in BUSINESS_READ_DOCS:
            add_perm(rows, doctype, role, **READ)

    for doctype in OPERATIONS_MANAGER_MASTER_DOCS:
        add_perm(rows, doctype, "Operations Manager", **MAINTAIN)
    for doctype in OPERATIONS_MANAGER_TRANSACTION_DOCS:
        add_perm(rows, doctype, "Operations Manager", **TRANSACTION)
    for doctype in ["Stock Ledger Entry", "Bin", "GL Entry", "Payment Ledger Entry"]:
        add_perm(rows, doctype, "Operations Manager", **READ)
    # Sales Order custom_approved is permlevel 2 in the restored site. Operations
    # Manager needs submit/approval carry-forward authority.
    add_perm(rows, "Sales Order", "Operations Manager", permlevel=2, **LIMITED_WRITE)

    for doctype in INVENTORY_TRANSACTION_DOCS:
        add_perm(rows, doctype, "Inventory Operator", **TRANSACTION)
    for doctype in INVENTORY_READ_DOCS:
        add_perm(rows, doctype, "Inventory Operator", **READ)

    for doctype in GRIPPER_TRANSACTION_DOCS:
        add_perm(rows, doctype, "Gripper Manufacturer", **TRANSACTION)
    for doctype in GRIPPER_READ_DOCS:
        add_perm(rows, doctype, "Gripper Manufacturer", **READ)

    for role, dependency_map in TRANSACTION_ROLE_DEPENDENCIES.items():
        for doctype in dependency_map["transaction"]:
            add_perm(rows, doctype, role, **TRANSACTION)
        for doctype in dependency_map["maintain"]:
            add_perm(rows, doctype, role, **MAINTAIN)
        for doctype in dependency_map["read"]:
            add_perm(rows, doctype, role, **READ)

    for doctype in PROCUREMENT_WRITE_DOCS:
        add_perm(rows, doctype, "Procurement User", **LIMITED_WRITE)
    add_perm(rows, "Item Price", "Procurement User", create=1)
    # Model of record: Procurement User can create/view Purchase Orders but
    # does not own submission/accounting authority.
    add_perm(rows, "Purchase Order", "Procurement User", **LIMITED_WRITE)
    add_perm(rows, "Purchase Order", "Procurement User", create=1)
    for doctype in PROCUREMENT_READ_DOCS:
        add_perm(rows, doctype, "Procurement User", **READ)
    add_perm(rows, "Item", "Procurement User", permlevel=1, **READ)

    # Managed link-read dependencies. Guard: refuse to add a row to any DocType
    # that this fixture does not already manage, because that would replace its
    # standard DocPerm set (see LINK_READ_DEPENDENCIES_MANAGED docstring).
    managed_parents = {parent for (parent, _role, _lvl) in rows}
    for role, doctypes in LINK_READ_DEPENDENCIES_MANAGED.items():
        for doctype in doctypes:
            if doctype not in managed_parents:
                raise SystemExit(
                    f"refusing to add link-read for unmanaged DocType {doctype!r}: "
                    "adding the first Custom DocPerm would replace its standard perms"
                )
            add_perm(rows, doctype, role, **READ)

    for standard_row in STOCK_ENTRY_TYPE_STANDARD_DOCPERMS:
        role = standard_row["role"]
        permlevel = standard_row["permlevel"]
        bits = {field: standard_row.get(field, 0) for field in PERM_FIELDS}
        add_perm(rows, "Stock Entry Type", role, permlevel=permlevel, **bits)
    for role in STOCK_ENTRY_TYPE_CURATED_READ_ROLES:
        add_perm(rows, "Stock Entry Type", role, **READ)

    # CSA/FCO as-installed records: internal operations/process owners can
    # create and maintain Request/Field Change records, Operations Viewer can
    # inspect the register, and external builders intentionally receive no row.
    for doctype in FCO_MANAGED_DOCTYPES:
        add_perm(rows, doctype, "System Manager", **FCO_SYSTEM)
        for role in FCO_WRITE_ROLES:
            add_perm(rows, doctype, role, **FCO_MAINTAIN)
        add_perm(rows, doctype, "Operations Viewer", **READ)

    # Options Catalog is a Single custom DocType used as the print surface for
    # released-only and comprehensive option catalogs. Adding any Custom
    # DocPerm row makes Frappe ignore the embedded standard permission, so
    # preserve System Manager explicitly before granting Engineering read/print.
    add_perm(rows, OPTIONS_CATALOG_DOCTYPE, "System Manager", **SYSTEM_FULL)
    for role in OPTIONS_CATALOG_PRINT_ROLES:
        add_perm(rows, OPTIONS_CATALOG_DOCTYPE, role, **READ)

    if args.global_viewer_all_doctypes:
        add_global_viewer_all_doctypes(rows, frappe)

    # Fixture Export Control is deliberately restricted to System Manager and
    # InductOne Process Architect. Remove any stale broad-role rows that may
    # have been carried forward from earlier generated fixtures.
    add_perm(rows, "Fixture Export Control", "System Manager", **SYSTEM_FULL)
    add_perm(rows, "Fixture Export Control", "InductOne Process Architect", **SYSTEM_FULL)

    # External builders must be able to create their returned Build Completion
    # records/workbook uploads while remaining isolated from raw underlying ERP
    # records. Earlier fixtures had read/write but no create, which made the
    # portal visible while blocking the actual return workflow.
    add_perm(
        rows,
        "InductOne Build Completion",
        "InductOne External Builder",
        read=1,
        write=1,
        create=1,
    )

    # External builders should work only from their assigned Configuration
    # Orders and Build Completion records. They should not retain direct
    # workspace/list access to underlying Snapshot or BOM Export Package
    # records; generated files are exposed through the Configuration Order
    # document index instead.
    for doctype in ["BOM Export Package", "Configured BOM Snapshot"]:
        rows.pop((doctype, "InductOne External Builder", 0), None)

    for role in [
        "Operations Viewer",
        "InductOne Manager",
        "Engineering User",
        "Operations Manager",
        "Inventory Operator",
        "Gripper Manufacturer",
        "Procurement User",
        "Global Viewer",
    ]:
        rows.pop(("Fixture Export Control", role, 0), None)

    final_rows = sorted(rows.values(), key=lambda r: (r["parent"], r["role"], r["permlevel"]))
    FIXTURE.write_text(json.dumps(final_rows, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(final_rows)} Custom DocPerm fixture rows")

    if frappe:
        frappe.destroy()


if __name__ == "__main__":
    main()
