"""Grant curated roles read on managed link-target DocTypes.

The static link dependency audit (scripts/run_static_link_dependency_audit.py,
2026-06-29) found curated roles that can write a DocType but lacked read on a
DocType it links to, breaking link resolution on the form.

This patch only augments DocTypes that are ALREADY managed by the repo-owned
Custom DocPerm fixture. Adding the *first* Custom DocPerm row to an unmanaged
DocType makes Frappe ignore ALL of that DocType's standard DocPerms, which would
strip access from every other role. The runtime guard below makes that mistake
impossible: the patch skips (and logs) any DocType that is not already managed.

The unmanaged live targets (Country, Stock Entry Type, User) are intentionally
handled separately; see docs/security/downstream-loss-triage-2026-06-29.md.

This patch is idempotent and mirrors the fixture generator so restored candidate
sites and production migrations converge to the same hardened role model.
"""

from __future__ import annotations

import frappe


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

LINK_READ_GRANTS = {
    "InductOne Manager": ("Item", "BOM", "Sales Order", "Supplier"),
    "InductOne Process Architect": ("Item", "BOM", "Sales Order", "Supplier"),
    "Procurement User": ("Currency",),
    "Inventory Operator": ("Price List",),
}


def execute():
    for role, doctypes in LINK_READ_GRANTS.items():
        for doctype in doctypes:
            ensure_managed_read_docperm(doctype, role)

    frappe.clear_cache()


def ensure_managed_read_docperm(doctype: str, role: str) -> None:
    if not frappe.db.exists("DocType", doctype):
        frappe.throw(f"Required ERPNext DocType is missing: {doctype}")

    # SAFETY GUARD: only augment DocTypes already managed by Custom DocPerm.
    # Creating the first Custom DocPerm row for a DocType makes Frappe ignore its
    # standard DocPerms entirely, removing access for every other role.
    if not frappe.db.exists("Custom DocPerm", {"parent": doctype}):
        print(
            f"SKIP link-read {doctype}/{role}: DocType is not Custom-DocPerm-managed; "
            "refusing to create the first row (would replace standard perms)."
        )
        return

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

    for field, value in READ.items():
        setattr(doc, field, value)

    if existing:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)
