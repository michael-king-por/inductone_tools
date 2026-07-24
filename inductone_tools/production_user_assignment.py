"""Approved production user assignment helper for the hardening deployment.

This module is intentionally not whitelisted. It is meant to be called by the
system owner through `bench execute` during the production deployment runbook.
"""

from __future__ import annotations

import frappe
from frappe import _


CONFIRMATION_TOKEN = "APPLY_PRODUCTION_USER_ASSIGNMENT_PLAN"

USERS_TO_DISABLE = [
    "alyza.salinas@plusonerobotics.com",
    "quickbooks.integration@plusonerobotics.com",
]

TARGET_USER_ROLES = {
    "ian.deliz@plusonerobotics.com": ["System Manager"],
    "matt.speer@plusonerobotics.com": ["Global Viewer"],
    "matthew.mcmillan@plusonerobotics.com": ["Procurement User"],
    "nathaniel.pantuso@plusonerobotics.com": [
        "Operations Manager",
        "Inventory Operator",
        "Gripper Manufacturer",
    ],
    "patty.gomez@plusonerobotics.com": ["Operations Manager", "Inventory Operator"],
}


def _require_confirmation(confirm: str | None) -> None:
    if confirm != CONFIRMATION_TOKEN:
        frappe.throw(
            _(
                "Refusing to apply production user assignments without confirmation token {0}."
            ).format(CONFIRMATION_TOKEN)
        )


def _ensure_user_exists(user_name: str) -> None:
    if not frappe.db.exists("User", user_name):
        frappe.throw(_("Required user does not exist: {0}").format(user_name))


def _ensure_roles_exist(roles: list[str]) -> None:
    missing = [role for role in roles if not frappe.db.exists("Role", role)]
    if missing:
        frappe.throw(_("Required roles do not exist: {0}").format(", ".join(missing)))


def apply_approved_user_assignments(confirm: str | None = None) -> dict:
    """Apply the signed production user assignment plan.

    This intentionally replaces target users' role rows with the approved role
    set after clearing `role_profile_name`, because the purpose of this cleanup
    is to remove broad Role Profile inheritance and accumulated role sprawl.
    """

    _require_confirmation(confirm)
    _ensure_roles_exist(sorted({role for roles in TARGET_USER_ROLES.values() for role in roles}))

    actions = []

    for user_name in USERS_TO_DISABLE:
        _ensure_user_exists(user_name)
        user = frappe.get_doc("User", user_name)
        user.enabled = 0
        user.save(ignore_permissions=True)
        frappe.clear_cache(user=user_name)
        message = f"DISABLED {user_name}"
        print(message)
        actions.append(message)

    for user_name, roles in TARGET_USER_ROLES.items():
        _ensure_user_exists(user_name)
        user = frappe.get_doc("User", user_name)
        user.role_profile_name = ""
        user.set("roles", [])
        for role in roles:
            user.append("roles", {"role": role})
        user.save(ignore_permissions=True)
        frappe.clear_cache(user=user_name)
        message = f"ASSIGNED {user_name}: role_profile_name cleared; roles={', '.join(roles)}"
        print(message)
        actions.append(message)

    frappe.db.commit()
    print(f"SUMMARY applied_actions={len(actions)}")
    return {
        "ok": True,
        "actions": actions,
    }
