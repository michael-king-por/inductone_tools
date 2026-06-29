"""Grant transaction roles stock dependency permissions.

Operations Manager, Inventory Operator, and Gripper Manufacturer are curated
roles that intentionally do not inherit broad ERPNext stock profiles. They must
still be able to complete stock/manufacturing transactions end-to-end when
items use serial and batch tracking. ERPNext creates and submits
``Serial and Batch Bundle`` records as part of those workflows, and references
master DocTypes such as Company, Currency, Fiscal Year, and Territory.

This patch mirrors the repo-owned Custom DocPerm fixture generator and is
idempotent so restored candidate sites and production migrations converge to
the same hardened role model.
"""

from __future__ import annotations

import frappe


TRANSACTION = {
    "read": 1,
    "write": 1,
    "create": 1,
    "delete": 0,
    "submit": 1,
    "cancel": 1,
    "amend": 1,
    "report": 1,
    "export": 1,
    "import": 1,
    "print": 1,
    "email": 1,
    "share": 1,
    "select": 1,
}

MAINTAIN = {
    "read": 1,
    "write": 1,
    "create": 1,
    "delete": 0,
    "submit": 0,
    "cancel": 0,
    "amend": 0,
    "report": 1,
    "export": 1,
    "import": 1,
    "print": 1,
    "email": 1,
    "share": 1,
    "select": 1,
}

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
    "print": 1,
    "email": 0,
    "share": 0,
    "select": 1,
}

TRANSACTION_ROLE_DEPENDENCIES = {
    "Operations Manager": {
        "transaction": ("Serial and Batch Bundle",),
        "maintain": ("Batch", "Serial No"),
        "read": ("Company", "Currency", "Fiscal Year", "Territory"),
    },
    "Inventory Operator": {
        "transaction": ("Serial and Batch Bundle",),
        "maintain": ("Batch", "Serial No"),
        "read": ("Company", "Currency", "Fiscal Year", "Territory"),
    },
    "Gripper Manufacturer": {
        "transaction": ("Serial and Batch Bundle",),
        "maintain": ("Batch", "Serial No"),
        "read": ("Company", "Currency", "Fiscal Year", "Territory"),
    },
}


def execute():
    for role, dependency_map in TRANSACTION_ROLE_DEPENDENCIES.items():
        for doctype in dependency_map["transaction"]:
            ensure_custom_docperm(doctype, role, **TRANSACTION)
        for doctype in dependency_map["maintain"]:
            ensure_custom_docperm(doctype, role, **MAINTAIN)
        for doctype in dependency_map["read"]:
            ensure_custom_docperm(doctype, role, **READ)

    frappe.clear_cache()


def ensure_custom_docperm(doctype: str, role: str, **bits: int) -> None:
    if not frappe.db.exists("DocType", doctype):
        frappe.throw(f"Required ERPNext DocType is missing: {doctype}")

    existing = frappe.db.exists(
        "Custom DocPerm",
        {
            "parent": doctype,
            "role": role,
            "permlevel": 0,
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
                "permlevel": 0,
            }
        )

    for field, value in bits.items():
        setattr(doc, field, value)

    if existing:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)
