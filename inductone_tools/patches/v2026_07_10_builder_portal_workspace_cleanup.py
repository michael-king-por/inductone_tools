"""Align external-builder Desk access with the governed handoff model.

External builders receive generated package/snapshot-derived artifacts through
their assigned Configuration Order document index and completion workflow. They
do not need direct Desk/list access to internal BOM Export Package or Configured
BOM Snapshot records.
"""

from __future__ import annotations

import frappe


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
    remove_external_builder_internal_docperms()
    restrict_engineering_workspace()
    prune_builder_portal_shortcuts()
    frappe.clear_cache()


def remove_external_builder_internal_docperms():
    for doctype in ["BOM Export Package", "Configured BOM Snapshot"]:
        frappe.db.delete(
            "Custom DocPerm",
            {
                "parent": doctype,
                "role": "InductOne External Builder",
                "permlevel": 0,
            },
        )


def _set_workspace_roles(workspace, roles):
    workspace.set("roles", [])
    for role in roles:
        if frappe.db.exists("Role", role):
            workspace.append("roles", {"role": role})


def restrict_engineering_workspace():
    if not frappe.db.exists("Workspace", "Engineering"):
        return
    workspace = frappe.get_doc("Workspace", "Engineering")
    workspace.public = 1
    workspace.is_hidden = 0
    _set_workspace_roles(workspace, INTERNAL_WORKSPACE_ROLES)
    workspace.save(ignore_permissions=True)


def prune_builder_portal_shortcuts():
    if not frappe.db.exists("Workspace", "Builder Portal"):
        return
    workspace = frappe.get_doc("Workspace", "Builder Portal")
    allowed = {"Configuration Orders", "Build Completions"}

    kept_shortcuts = []
    for shortcut in workspace.shortcuts or []:
        if shortcut.label in allowed:
            kept_shortcuts.append(
                {
                    "type": shortcut.type,
                    "link_to": shortcut.link_to,
                    "url": shortcut.url,
                    "doc_view": shortcut.doc_view,
                    "kanban_board": shortcut.kanban_board,
                    "label": shortcut.label,
                    "icon": shortcut.icon,
                    "restrict_to_domain": shortcut.restrict_to_domain,
                    "report_ref_doctype": shortcut.report_ref_doctype,
                    "stats_filter": shortcut.stats_filter,
                    "color": shortcut.color,
                    "format": shortcut.format,
                }
            )
    workspace.set("shortcuts", [])
    for shortcut in kept_shortcuts:
        workspace.append("shortcuts", shortcut)

    try:
        import json

        content = json.loads(workspace.content or "[]")
        pruned = []
        inserted_task_header = False
        for block in content:
            if block.get("type") == "shortcut":
                shortcut_name = (block.get("data") or {}).get("shortcut_name")
                if shortcut_name not in allowed:
                    continue
            if block.get("type") == "header":
                text = ((block.get("data") or {}).get("text") or "").lower()
                if "reference" in text or "quick links" in text:
                    if not inserted_task_header:
                        pruned.append(
                            {
                                "id": "builder-task-links",
                                "type": "header",
                                "data": {
                                    "text": '<span class="h4"><b>Your Builder Tasks</b></span>',
                                    "col": 12,
                                },
                            }
                        )
                        inserted_task_header = True
                    continue
            pruned.append(block)
        workspace.content = json.dumps(pruned, separators=(",", ":"))
    except Exception:
        # Do not fail migrate for cosmetic JSON cleanup; the role/shortcut table
        # cleanup above is the critical safety behavior.
        pass

    workspace.public = 1
    workspace.is_hidden = 0
    _set_workspace_roles(workspace, ["InductOne External Builder"])
    workspace.save(ignore_permissions=True)

