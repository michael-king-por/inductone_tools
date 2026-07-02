"""Hide the unused, orphaned Quality workspace.

The permission hardening retired the broad/legacy ``Builder`` role. The standard
``Quality`` Workspace was still role-restricted to ``Builder``, so after the
hardening it was visible to no curated internal role (orphaned). The owner
confirmed Plus One does not use the ERPNext Quality module, so the correct
disposition is to hide the workspace rather than grant it to internal roles.

Setting ``is_hidden = 1`` removes it from the sidebar for everyone without
deleting the workspace or its content, so it is fully reversible. This patch is
idempotent and re-applies on every migrate, so it converges even if a standard
workspace sync resets the flag.
"""

from __future__ import annotations

import frappe


QUALITY_WORKSPACE = "Quality"


def execute():
    if not frappe.db.exists("Workspace", QUALITY_WORKSPACE):
        return

    if int(frappe.db.get_value("Workspace", QUALITY_WORKSPACE, "is_hidden") or 0) == 1:
        return

    doc = frappe.get_doc("Workspace", QUALITY_WORKSPACE)
    doc.is_hidden = 1
    doc.save(ignore_permissions=True)
    frappe.clear_cache()
