#!/usr/bin/env python3
"""Candidate validation for Operations workspace visibility."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_EVIDENCE_DIR = os.environ.get(
    "VALIDATION_EVIDENCE_DIR",
    "/mnt/c/hub/frappe-sandbox/validation-evidence",
)

WORKSPACE_NAME = "Operations"
INTERNAL_ROLE_USERS = {
    "Operations Manager": "candidate.operations.manager@example.invalid",
    "Operations Viewer": "candidate.operations.viewer@example.invalid",
    "Engineering User": "candidate.engineering.user@example.invalid",
    "Procurement User": "candidate.procurement.user@example.invalid",
    "Finance Viewer": "candidate.finance.viewer@example.invalid",
    "InductOne Manager": "candidate.inductone.manager@example.invalid",
    "InductOne Process Architect": "candidate.inductone.process.architect@example.invalid",
}
EXTERNAL_BUILDER_USER = "motion.builder@plusonerobotics.com"

frappe = None


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _record(results: list[dict[str, Any]], label: str, passed: bool, detail: str, **extra: Any) -> None:
    print(f"{'PASS' if passed else 'FAIL'} {label}: {detail}")
    row = {"label": label, "passed": passed, "detail": detail}
    row.update(extra)
    results.append(row)


def _ensure_exact_role_user(user: str, role: str) -> None:
    frappe.set_user("Administrator")
    if not frappe.db.exists("User", user):
        doc = frappe.get_doc(
            {
                "doctype": "User",
                "email": user,
                "first_name": "Candidate",
                "last_name": role.replace(" ", ""),
                "enabled": 1,
                "send_welcome_email": 0,
                "user_type": "System User",
            }
        )
        doc.insert(ignore_permissions=True)
    else:
        doc = frappe.get_doc("User", user)
        doc.enabled = 1
        doc.user_type = "System User"
    doc.role_profile_name = ""
    doc.set("roles", [])
    doc.append("roles", {"role": role})
    doc.save(ignore_permissions=True)
    frappe.clear_cache(user=user)


def _visible_workspaces_for_user(user: str) -> list[str]:
    from frappe.desk.desktop import get_workspace_sidebar_items

    previous_user = frappe.session.user
    try:
        frappe.set_user(user)
        pages = get_workspace_sidebar_items().get("pages") or []
        return [page.get("name") for page in pages]
    finally:
        frappe.set_user(previous_user)


def run(site: str, sites_path: str, evidence_dir: str) -> int:
    global frappe
    import frappe as frappe_module

    frappe = frappe_module
    frappe.init(site=site, sites_path=sites_path)
    frappe.connect()

    results: list[dict[str, Any]] = []
    workspace_doc = frappe.get_doc("Workspace", WORKSPACE_NAME)
    current_roles = [row.role for row in workspace_doc.get("roles")]

    try:
        for role, user in INTERNAL_ROLE_USERS.items():
            _ensure_exact_role_user(user, role)
            visible = _visible_workspaces_for_user(user)
            _record(
                results,
                f"operations_workspace_visible_{role.lower().replace(' ', '_')}",
                WORKSPACE_NAME in visible,
                (
                    f"{WORKSPACE_NAME} visible for {role}."
                    if WORKSPACE_NAME in visible
                    else f"{WORKSPACE_NAME} not visible for {role}."
                ),
                user=user,
                role=role,
                visible_workspaces=visible,
            )

        visible = _visible_workspaces_for_user(EXTERNAL_BUILDER_USER)
        _record(
            results,
            "operations_workspace_hidden_external_builder",
            WORKSPACE_NAME not in visible,
            (
                f"{WORKSPACE_NAME} hidden for external builder."
                if WORKSPACE_NAME not in visible
                else f"{WORKSPACE_NAME} visible for external builder."
            ),
            user=EXTERNAL_BUILDER_USER,
            role="InductOne External Builder",
            visible_workspaces=visible,
        )

        frappe.db.commit()
    finally:
        frappe.destroy()

    passed_count = sum(1 for row in results if row["passed"])
    payload = {
        "site": site,
        "workspace": WORKSPACE_NAME,
        "workspace_roles": current_roles,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {"total": len(results), "passed": passed_count, "failed": len(results) - passed_count},
        "results": results,
    }
    evidence_path = Path(evidence_dir) / f"operations_workspace_visibility_{_timestamp()}.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"SUMMARY {passed_count}/{len(results)} passed; evidence={evidence_path}")
    return 0 if passed_count == len(results) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--evidence-dir", default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()
    return run(args.site, args.sites_path, args.evidence_dir)


if __name__ == "__main__":
    sys.exit(main())
