"""Grant Operations Manager read/select on Account.

Operations Manager can create and submit Sales Orders, but Sales Order and
Sales Order Item validation can require selecting linked Account records
such as income accounts. ``Account`` is already Custom-DocPerm-managed by the
role-hardening fixtures for read-only viewer roles; once any Custom DocPerm
exists for a DocType, Frappe ignores that DocType's standard permissions for
other roles. This patch adds the missing least-privilege dependency row for
Operations Manager without restoring broad accounting roles.
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


def execute() -> None:
    if not frappe.db.exists("DocType", "Account"):
        return

    # Guard against the Custom DocPerm replace-trap: do not be the first patch
    # to Custom-manage Account on an environment that has not already adopted
    # the hardened fixture model.
    if not frappe.db.exists("Custom DocPerm", {"parent": "Account"}):
        frappe.logger().warning(
            "Skipping Operations Manager Account read grant because Account is not Custom-DocPerm-managed."
        )
        return

    ensure_custom_docperm("Account", "Operations Manager", **READ)
    frappe.clear_cache()


def ensure_custom_docperm(doctype: str, role: str, **bits: int) -> None:
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
