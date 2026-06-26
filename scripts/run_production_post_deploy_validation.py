#!/usr/bin/env python3
"""Production post-deploy validation for InductOne permission hardening.

This script is read-only. It validates the highest-risk post-deployment
permission outcomes and writes JSON evidence for the deployment record.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Host-neutral fallback. The deployment checklist's $EVIDENCE_DIR / --evidence-dir
# value is authoritative for production runs.
DEFAULT_EVIDENCE_DIR = "deployment-evidence"

LEGACY_ROLES = [
    "Builder",
    "InductOne Process Manager",
    "InductOne Architect",
    "Engineering Signoff Delegate",
    "Part Number Manager",
    "Engineering - Signoff",
    "OPS-INDUCTONE-GATEKEEP",
    "PRODUCT-INDUCTONE-GATEKEEP",
]

EXTERNAL_BUILDER_USERS = [
    ("motion", "motion.builder@plusonerobotics.com"),
    ("lam", "lam@plusonerobotics.com"),
]

frappe = None
has_permission = None


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _print_result(passed: bool, label: str, detail: str) -> None:
    print(f"{'PASS' if passed else 'FAIL'} {label}: {detail}")


def _record(results: list[dict[str, Any]], label: str, passed: bool, detail: str, **extra: Any) -> None:
    _print_result(passed, label, detail)
    row = {
        "label": label,
        "passed": passed,
        "detail": detail,
    }
    row.update(extra)
    results.append(row)


def _enabled_users_with_roles(roles: list[str]) -> list[dict[str, Any]]:
    if not roles:
        return []
    return frappe.db.sql(
        """
        select hr.parent as user, hr.role
        from `tabHas Role` hr
        inner join `tabUser` u on u.name = hr.parent
        where hr.parenttype = 'User'
          and u.enabled = 1
          and hr.role in %(roles)s
        order by hr.role asc, hr.parent asc
        """,
        {"roles": tuple(roles)},
        as_dict=True,
    )


def _enabled_users_with_super_profile() -> list[dict[str, Any]]:
    return frappe.get_all(
        "User",
        filters={"enabled": 1, "role_profile_name": "Super"},
        fields=["name", "role_profile_name"],
        order_by="name asc",
    )


def _list_check_as_user(doctype: str, user: str) -> dict[str, Any]:
    """Return whether the user can pull any records from a doctype list."""
    previous_user = frappe.session.user
    try:
        frappe.set_user(user)
        rows = frappe.get_list(doctype, fields=["name"], limit_page_length=1)
        return {
            "exception": None,
            "row_count": len(rows),
            "sample": rows[0].name if rows else None,
        }
    except BaseException as exc:  # noqa: BLE001 - evidence should capture exact exception
        return {
            "exception": exc.__class__.__name__,
            "message": str(exc),
            "row_count": 0,
            "sample": None,
        }
    finally:
        frappe.set_user(previous_user)


def _role_read_grants_for_doctype(doctype: str, roles: list[str]) -> list[dict[str, Any]]:
    if not frappe.db.exists("DocType", doctype):
        return [{"doctype": doctype, "error": "DocType does not exist"}]

    rows = []
    meta = frappe.get_meta(doctype)
    for perm in meta.permissions:
        if perm.role in roles and int(perm.permlevel or 0) == 0 and int(perm.read or 0):
            rows.append(
                {
                    "source": "DocPerm",
                    "role": perm.role,
                    "read": int(perm.read or 0),
                    "write": int(perm.write or 0),
                    "create": int(perm.create or 0),
                    "permlevel": int(perm.permlevel or 0),
                }
            )

    custom_rows = frappe.get_all(
        "Custom DocPerm",
        filters={"parent": doctype, "role": ["in", roles], "permlevel": 0},
        fields=["name", "role", "read", "write", "create", "permlevel"],
        order_by="role asc",
    )
    for row in custom_rows:
        if int(row.read or 0):
            row = dict(row)
            row["source"] = "Custom DocPerm"
            rows.append(row)

    return rows


def run(site: str, sites_path: str, evidence_dir: str) -> int:
    global frappe, has_permission
    import frappe as frappe_module
    from frappe.permissions import has_permission as has_permission_function

    frappe = frappe_module
    has_permission = has_permission_function

    frappe.init(site=site, sites_path=sites_path)
    frappe.connect()

    results: list[dict[str, Any]] = []

    legacy_holders = _enabled_users_with_roles(LEGACY_ROLES)
    _record(
        results,
        "legacy_role_absence",
        not legacy_holders,
        "No enabled users hold retired legacy roles." if not legacy_holders else "Enabled users still hold retired legacy roles.",
        legacy_roles=LEGACY_ROLES,
        holders=legacy_holders,
    )

    super_profile_users = _enabled_users_with_super_profile()
    _record(
        results,
        "super_profile_absence",
        not super_profile_users,
        "No enabled users hold Super Role Profile." if not super_profile_users else "Enabled users still hold Super Role Profile.",
        users=super_profile_users,
    )

    for user_key, user in EXTERNAL_BUILDER_USERS:
        for doctype in ["Item", "BOM"]:
            permission_result = bool(has_permission(doctype, ptype="read", user=user))
            list_result = _list_check_as_user(doctype, user)
            passed = (not permission_result) and list_result["row_count"] == 0
            _record(
                results,
                f"external_builder_{doctype.lower()}_denial_{user_key}",
                passed,
                (
                    f"{user} cannot read/list {doctype}."
                    if passed
                    else f"{user} can still read or list {doctype}."
                ),
                user=user,
                doctype=doctype,
                has_permission_read=permission_result,
                list_result=list_result,
            )

    fixture_export_roles = ["Operations Viewer", "Finance Viewer"]
    grants = _role_read_grants_for_doctype("Fixture Export Control", fixture_export_roles)
    passed = not grants
    _record(
        results,
        "fixture_export_control_viewer_finance_denial",
        passed,
        (
            "Operations Viewer and Finance Viewer have no read grant on Fixture Export Control."
            if passed
            else "Operations Viewer or Finance Viewer still has a read grant on Fixture Export Control."
        ),
        doctype="Fixture Export Control",
        roles=fixture_export_roles,
        grants=grants,
    )

    passed_count = sum(1 for row in results if row["passed"])
    failed_count = len(results) - passed_count
    payload = {
        "site": site,
        "sites_path": sites_path,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": len(results),
            "passed": passed_count,
            "failed": failed_count,
        },
        "results": results,
    }

    evidence_path = Path(evidence_dir) / f"production_post_deploy_validation_{_timestamp()}.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")

    print(f"SUMMARY {passed_count}/{len(results)} passed; evidence={evidence_path}")
    return 0 if failed_count == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument(
        "--evidence-dir",
        default=os.environ.get("VALIDATION_EVIDENCE_DIR", DEFAULT_EVIDENCE_DIR),
        help="Directory for JSON evidence output. In production, pass the checklist's $EVIDENCE_DIR explicitly. Defaults to VALIDATION_EVIDENCE_DIR or ./deployment-evidence.",
    )
    args = parser.parse_args()

    try:
        return run(args.site, args.sites_path, args.evidence_dir)
    finally:
        frappe.destroy()


if __name__ == "__main__":
    sys.exit(main())
