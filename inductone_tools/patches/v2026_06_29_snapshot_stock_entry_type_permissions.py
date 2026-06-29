"""Snapshot-manage Stock Entry Type before adding curated read access.

The 2026-06-29 Desk link probe confirmed Operations Manager and Gripper
Manufacturer cannot use the Stock Entry form because the mandatory Stock Entry
Type link search raises PermissionError.

Stock Entry Type was previously unmanaged by Custom DocPerm. Adding the first
Custom DocPerm row to an unmanaged DocType makes Frappe ignore the standard
DocPerm table for that DocType, which would strip access from roles such as
System Manager, Stock Manager, Manufacturing Manager, and Stock User.

This patch therefore snapshots all standard DocPerm rows for Stock Entry Type
as Custom DocPerm first, then adds read-only rows for the curated transaction
roles that need link-picker access.
"""

from __future__ import annotations

import frappe


PERM_FIELDS = (
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
)

CURATED_READ_ROLES = (
    "Operations Manager",
    "Inventory Operator",
    "Gripper Manufacturer",
)

READ = {
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
    "select": 1,
    "if_owner": 0,
}


def execute():
    doctype = "Stock Entry Type"
    if not frappe.db.exists("DocType", doctype):
        frappe.throw(f"Required ERPNext DocType is missing: {doctype}")

    snapshot_standard_docperms(doctype)
    for role in CURATED_READ_ROLES:
        ensure_docperm(doctype, role, 0, READ)

    frappe.clear_cache()


def snapshot_standard_docperms(doctype: str) -> None:
    standard_rows = frappe.get_all(
        "DocPerm",
        filters={"parent": doctype},
        fields=["role", "permlevel", *PERM_FIELDS],
        order_by="idx asc",
    )
    if not standard_rows:
        frappe.throw(f"No standard DocPerm rows found for {doctype}")

    for row in standard_rows:
        role = row["role"]
        permlevel = int(row.get("permlevel") or 0)
        bits = {field: int(bool(row.get(field))) for field in PERM_FIELDS}
        ensure_docperm(doctype, role, permlevel, bits)


def ensure_docperm(doctype: str, role: str, permlevel: int, bits: dict[str, int]) -> None:
    existing = frappe.db.exists(
        "Custom DocPerm",
        {
            "parent": doctype,
            "role": role,
            "permlevel": int(permlevel or 0),
        },
    )
    if existing:
        doc = frappe.get_doc("Custom DocPerm", existing)
    else:
        doc = frappe.get_doc(
            {
                "doctype": "Custom DocPerm",
                "parent": doctype,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": role,
                "permlevel": int(permlevel or 0),
            }
        )

    for field in PERM_FIELDS:
        setattr(doc, field, int(bool(bits.get(field))))

    if existing:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)
