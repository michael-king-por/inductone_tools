"""Make the Operations workspace visible to curated internal roles.

The permission hardening retired broad/legacy roles such as Operations Member.
The Operations workspace was still restricted to that legacy role, which made
the page disappear for curated internal roles even though their workflow/action
permissions were otherwise correct.
"""

from __future__ import annotations

import frappe


OPERATIONS_WORKSPACE = "Operations"

INTERNAL_WORKSPACE_ROLES = [
    "Operations Manager",
    "Operations Viewer",
    "Engineering User",
    "Procurement User",
    "Finance Viewer",
    "InductOne Manager",
    "InductOne Process Architect",
]


def execute():
    if not frappe.db.exists("Workspace", OPERATIONS_WORKSPACE):
        return

    doc = frappe.get_doc("Workspace", OPERATIONS_WORKSPACE)
    existing = {row.role for row in doc.get("roles")}
    desired = set(INTERNAL_WORKSPACE_ROLES)

    if existing == desired:
        return

    doc.set("roles", [])
    for role in INTERNAL_WORKSPACE_ROLES:
        if frappe.db.exists("Role", role):
            doc.append("roles", {"role": role})

    doc.save(ignore_permissions=True)
    frappe.clear_cache()
