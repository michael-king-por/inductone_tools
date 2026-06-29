#!/usr/bin/env python3
"""Compare baseline vs candidate effective permissions for real enabled users.

Baseline is read-only reference. Candidate is the post-hardening target state.
The output is intentionally a review artifact: lost capabilities are grouped by
user and should be classified by the system owner before any grants are added.
"""

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

CAPABILITIES = ["read", "write", "create", "submit", "cancel", "delete"]
EXPECTED_LOSSES = {
    ("motion.builder@plusonerobotics.com", "Item"),
    ("motion.builder@plusonerobotics.com", "BOM"),
    ("lam@plusonerobotics.com", "Item"),
    ("lam@plusonerobotics.com", "BOM"),
}

EXPECTED_DISABLED_USERS = {
    "alyza.salinas@plusonerobotics.com",
    "quickbooks.integration@plusonerobotics.com",
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _is_real_enabled_user(user: dict[str, Any]) -> bool:
    name = user.get("name") or ""
    if name in {"Administrator", "Guest"}:
        return False
    if name.startswith("candidate.") or name.endswith("@example.invalid"):
        return False
    return bool(user.get("enabled")) and "@plusonerobotics.com" in name


def _collect(site: str, sites_path: str) -> dict[str, Any]:
    import frappe
    from frappe.permissions import has_permission

    # Standalone frappe.init() can configure site log paths relative to the
    # current bench process before connect() fully resolves the target bench.
    # Creating both possible log locations keeps this read-only audit from
    # failing on missing log directories.
    (Path(sites_path) / site / "logs").mkdir(parents=True, exist_ok=True)
    (Path.cwd() / site / "logs").mkdir(parents=True, exist_ok=True)

    frappe.init(site=site, sites_path=sites_path)
    frappe.connect()
    try:
        users = [
            dict(row)
            for row in frappe.get_all(
                "User",
                fields=["name", "enabled", "role_profile_name"],
                filters={"enabled": 1},
                order_by="name asc",
            )
            if _is_real_enabled_user(dict(row))
        ]
        doctypes = frappe.get_all("DocType", pluck="name", order_by="name asc")
        permissions: dict[str, dict[str, dict[str, Any]]] = {}
        errors: list[dict[str, str]] = []
        roles_by_user = {user["name"]: frappe.get_roles(user["name"]) for user in users}

        for user in users:
            user_name = user["name"]
            permissions[user_name] = {}
            for doctype in doctypes:
                permissions[user_name][doctype] = {}
                for capability in CAPABILITIES:
                    try:
                        permissions[user_name][doctype][capability] = bool(
                            has_permission(doctype, ptype=capability, user=user_name)
                        )
                    except BaseException as exc:  # noqa: BLE001 - evidence should capture exact failures
                        permissions[user_name][doctype][capability] = False
                        errors.append(
                            {
                                "site": site,
                                "user": user_name,
                                "doctype": doctype,
                                "capability": capability,
                                "exception": exc.__class__.__name__,
                                "message": str(exc),
                            }
                        )

        return {
            "site": site,
            "users": users,
            "roles_by_user": roles_by_user,
            "doctypes": doctypes,
            "permissions": permissions,
            "errors": errors,
        }
    finally:
        frappe.destroy()


def _loss_is_expected(user: str, doctype: str) -> bool:
    return (user, doctype) in EXPECTED_LOSSES


def run(
    baseline_site: str,
    baseline_sites_path: str,
    candidate_site: str,
    candidate_sites_path: str,
    evidence_dir: str,
) -> int:
    baseline = _collect(baseline_site, baseline_sites_path)
    candidate = _collect(candidate_site, candidate_sites_path)

    candidate_users = set(candidate["permissions"])
    losses_by_user: dict[str, list[dict[str, Any]]] = {}
    expected_losses: list[dict[str, Any]] = []
    missing_candidate_users: list[str] = []
    expected_disabled_candidate_users: list[str] = []

    for user in baseline["permissions"]:
        if user not in candidate_users:
            if user in EXPECTED_DISABLED_USERS:
                expected_disabled_candidate_users.append(user)
                continue
            missing_candidate_users.append(user)
            continue
        for doctype, baseline_caps in baseline["permissions"][user].items():
            candidate_caps = candidate["permissions"][user].get(doctype, {})
            for capability, had_before in baseline_caps.items():
                has_after = bool(candidate_caps.get(capability))
                if not had_before or has_after:
                    continue
                row = {
                    "user": user,
                    "doctype": doctype,
                    "capability": capability,
                    "baseline_roles": baseline["roles_by_user"].get(user, []),
                    "candidate_roles": candidate["roles_by_user"].get(user, []),
                }
                if _loss_is_expected(user, doctype):
                    row["expected_loss"] = True
                    expected_losses.append(row)
                else:
                    row["expected_loss"] = False
                    losses_by_user.setdefault(user, []).append(row)

    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "baseline": {
            "site": baseline_site,
            "sites_path": baseline_sites_path,
            "user_count": len(baseline["users"]),
            "error_count": len(baseline["errors"]),
        },
        "candidate": {
            "site": candidate_site,
            "sites_path": candidate_sites_path,
            "user_count": len(candidate["users"]),
            "error_count": len(candidate["errors"]),
        },
        "capabilities": CAPABILITIES,
        "summary": {
            "users_with_unexpected_losses": len(losses_by_user),
            "unexpected_loss_count": sum(len(rows) for rows in losses_by_user.values()),
            "expected_loss_count": len(expected_losses),
            "missing_candidate_users": len(missing_candidate_users),
            "expected_disabled_candidate_users": len(expected_disabled_candidate_users),
        },
        "losses_by_user": losses_by_user,
        "expected_losses": expected_losses,
        "missing_candidate_users": missing_candidate_users,
        "expected_disabled_candidate_users": expected_disabled_candidate_users,
        "collection_errors": {
            "baseline": baseline["errors"],
            "candidate": candidate["errors"],
        },
    }

    evidence_path = Path(evidence_dir) / f"effective_permission_regression_diff_{_timestamp()}.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")

    print(
        "SUMMARY "
        f"users_with_losses={payload['summary']['users_with_unexpected_losses']} "
        f"unexpected_losses={payload['summary']['unexpected_loss_count']} "
        f"expected_losses={payload['summary']['expected_loss_count']} "
        f"missing_candidate_users={payload['summary']['missing_candidate_users']} "
        f"expected_disabled_users={payload['summary']['expected_disabled_candidate_users']} "
        f"evidence={evidence_path}"
    )
    for user, rows in losses_by_user.items():
        print(f"USER {user} lost {len(rows)} capabilities")
        for row in rows[:40]:
            print(f"  LOST {row['doctype']}:{row['capability']}")
        if len(rows) > 40:
            print(f"  ... {len(rows) - 40} more in evidence JSON")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-site", required=True)
    parser.add_argument("--baseline-sites-path", required=True)
    parser.add_argument("--candidate-site", required=True)
    parser.add_argument("--candidate-sites-path", required=True)
    parser.add_argument("--evidence-dir", default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()
    return run(
        args.baseline_site,
        args.baseline_sites_path,
        args.candidate_site,
        args.candidate_sites_path,
        args.evidence_dir,
    )


if __name__ == "__main__":
    sys.exit(main())
