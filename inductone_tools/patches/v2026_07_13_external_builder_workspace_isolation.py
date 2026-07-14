"""Hide all non-builder workspaces from external builders.

Workspace visibility is driven by Workspace role child rows in Desk, not by
plain DocType permission checks. Several standard ERPNext workspaces are public
with no role rows, which makes them visible to every Desk user, including
supplier builder accounts. External builders should land in Builder Portal only.

This patch keeps Builder Portal visible to ``InductOne External Builder`` and
converts any other visible public/no-role workspace to the curated internal
workspace roles. It intentionally does not fixture-manage the whole standard
workspace catalog; the patch is the safety net for restored production data and
future candidate refreshes.
"""

from __future__ import annotations

import frappe


BUILDER_WORKSPACE = "Builder Portal"
EXTERNAL_BUILDER_ROLE = "InductOne External Builder"

INTERNAL_WORKSPACE_ROLES = [
    "Operations Manager",
    "Operations Viewer",
    "Engineering User",
    "Procurement User",
    "Finance Viewer",
    "InductOne Manager",
    "InductOne Process Architect",
]


def execute() -> None:
    if not frappe.db.exists("DocType", "Workspace"):
        return

    ensure_builder_portal_only_for_external_builders()
    frappe.clear_cache()


def _existing_roles() -> set[str]:
    return {row.name for row in frappe.get_all("Role", fields=["name"])}


def _set_workspace_roles(workspace, roles: list[str], existing_roles: set[str]) -> bool:
    desired = [role for role in roles if role in existing_roles]
    current = [row.role for row in workspace.get("roles")]
    if current == desired:
        return False

    workspace.set("roles", [])
    for role in desired:
        workspace.append("roles", {"role": role})
    return True


def ensure_builder_portal_only_for_external_builders() -> None:
    existing_roles = _existing_roles()

    for row in frappe.get_all(
        "Workspace",
        fields=["name", "public", "is_hidden"],
        order_by="name",
    ):
        if row.name == BUILDER_WORKSPACE:
            continue
        if row.is_hidden:
            continue

        workspace = frappe.get_doc("Workspace", row.name)
        roles = [role_row.role for role_row in workspace.get("roles")]

        # Empty role rows mean "visible to all Desk users". Explicit external
        # builder rows on any non-builder workspace are also not allowed.
        if roles and EXTERNAL_BUILDER_ROLE not in roles:
            continue

        changed = _set_workspace_roles(workspace, INTERNAL_WORKSPACE_ROLES, existing_roles)
        if changed:
            workspace.save(ignore_permissions=True)

