#!/usr/bin/env python3
"""Validate the Electrical Balloon Callouts report.

This is a read-only validation script. It checks that:

- the report is versioned with the expected current role set;
- the underlying query has data on the target site;
- representative internal users can execute the Query Report;
- external builder users cannot execute it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_NAME = "Electrical Balloon Callouts"

EXPECTED_REPORT_ROLES = {
    "System Manager",
    "Operations Manager",
    "Operations Viewer",
    "Inventory Operator",
    "Gripper Manufacturer",
    "Engineering User",
    "Global Viewer",
    "Procurement User",
    "InductOne Manager",
    "InductOne Process Architect",
}

INTERNAL_USER_CHECKS = {
    "system_manager": "michael.king@plusonerobotics.com",
    "operations_manager": "patty.gomez@plusonerobotics.com",
    "operations_viewer": "zohair.naqvi@plusonerobotics.com",
    "gripper_manufacturer": "nathaniel.pantuso@plusonerobotics.com",
    "engineering_user": "shaun.edwards@plusonerobotics.com",
    "global_viewer": "matt.speer@plusonerobotics.com",
    "procurement_user": "matthew.mcmillan@plusonerobotics.com",
    "inductone_manager": "jim.haws@plusonerobotics.com",
    "inductone_process_architect": "michael.king@plusonerobotics.com",
}

EXTERNAL_BUILDER_USERS = [
    "motion.builder@plusonerobotics.com",
    "lam@plusonerobotics.com",
]


def run_report_as(frappe: Any, user: str) -> dict[str, Any]:
    from frappe.desk.query_report import run as run_query_report

    if not frappe.db.exists("User", user):
        return {
            "user": user,
            "exists": False,
            "ok": False,
            "exception": "MissingUser",
            "message": "User does not exist on this site.",
        }

    frappe.set_user(user)
    try:
        result = run_query_report(REPORT_NAME)
        rows = result.get("result") or []
        return {
            "user": user,
            "exists": True,
            "ok": True,
            "row_count": len(rows),
            "first_row": rows[0] if rows else None,
        }
    except Exception as exc:  # noqa: BLE001 - evidence wants exact exception
        return {
            "user": user,
            "exists": True,
            "ok": False,
            "exception": type(exc).__name__,
            "message": str(exc),
        }
    finally:
        frappe.set_user("Administrator")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Electrical Balloon Callouts report access and data.")
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--min-rows", default=1, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = args.evidence_dir / f"balloon_report_validation_{timestamp}.json"

    import frappe

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    failures: list[str] = []
    try:
        if not frappe.db.exists("Report", REPORT_NAME):
            payload = {
                "site": args.site,
                "generated_at_utc": timestamp,
                "report": REPORT_NAME,
                "checks": [],
                "failures": [f"Report {REPORT_NAME!r} does not exist."],
            }
            evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            print(f"FAIL report_exists: {REPORT_NAME} not found")
            print(f"Evidence written: {evidence_path}")
            return 1

        report = frappe.get_doc("Report", REPORT_NAME)
        report_roles = {row.role for row in report.roles}
        direct_rows = frappe.db.sql(
            """
            SELECT
                bi.parent AS bom,
                bi.custom_balloon_numbers AS balloon_number,
                bi.item_code,
                bi.item_name,
                bi.qty,
                bi.uom,
                bi.custom_electrical_unit AS electrical_unit,
                bi.custom_source_electrical_bom_rev AS source_rev
            FROM `tabBOM Item` bi
            INNER JOIN `tabBOM` b ON b.name = bi.parent
            WHERE
                b.docstatus = 1
                AND b.is_active = 1
                AND IFNULL(bi.custom_balloon_numbers, '') != ''
            ORDER BY
                bi.parent,
                CAST(bi.custom_balloon_numbers AS UNSIGNED)
            """,
            as_dict=True,
        )

        checks: list[dict[str, Any]] = []

        missing_roles = sorted(EXPECTED_REPORT_ROLES - report_roles)
        unexpected_roles = sorted(report_roles - EXPECTED_REPORT_ROLES)
        roles_ok = not missing_roles and not unexpected_roles
        checks.append(
            {
                "label": "report_roles",
                "ok": roles_ok,
                "module": report.module,
                "report_type": report.report_type,
                "roles": sorted(report_roles),
                "missing_roles": missing_roles,
                "unexpected_roles": unexpected_roles,
            }
        )
        if not roles_ok:
            failures.append("Report roles do not match the expected current role set.")

        data_ok = len(direct_rows) >= args.min_rows
        checks.append(
            {
                "label": "direct_query_data",
                "ok": data_ok,
                "row_count": len(direct_rows),
                "min_rows": args.min_rows,
                "first_row": direct_rows[0] if direct_rows else None,
            }
        )
        if not data_ok:
            failures.append(f"Underlying balloon query returned {len(direct_rows)} rows; expected at least {args.min_rows}.")

        for label, user in INTERNAL_USER_CHECKS.items():
            result = run_report_as(frappe, user)
            ok = result["ok"] and result.get("row_count", 0) >= args.min_rows
            result.update({"label": f"internal_access_{label}", "ok": ok})
            checks.append(result)
            if not ok:
                failures.append(f"Internal user check failed: {label} / {user}")

        for user in EXTERNAL_BUILDER_USERS:
            result = run_report_as(frappe, user)
            ok = result["exists"] and not result["ok"] and result.get("exception") == "PermissionError"
            result.update(
                {
                    "label": "external_builder_denial_" + user.split("@", 1)[0].replace(".", "_"),
                    "ok": ok,
                    "expected": "PermissionError",
                }
            )
            checks.append(result)
            if not ok:
                failures.append(f"External builder was not denied as expected: {user}")

        payload = {
            "site": args.site,
            "generated_at_utc": timestamp,
            "report": REPORT_NAME,
            "checks": checks,
            "failures": failures,
        }
        evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    finally:
        frappe.destroy()

    for check in checks:
        status = "PASS" if check["ok"] else "FAIL"
        detail = ""
        if "row_count" in check:
            detail = f" rows={check['row_count']}"
        elif "user" in check:
            detail = f" user={check['user']}"
        print(f"{status} {check['label']}{detail}")
    print(f"SUMMARY {len(checks) - len([c for c in checks if not c['ok']])}/{len(checks)} passed")
    print(f"Evidence written: {evidence_path}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
