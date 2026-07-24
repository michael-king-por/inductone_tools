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

GLOBAL_REPORT_ROLE = "Global Viewer"
GLOBAL_REPORT_USER = "matt.speer@plusonerobotics.com"
GLOBAL_REPORT_DEPENDENCY_DOCTYPES = [
    "Batch",
    "Company",
    "Currency",
    "Fiscal Year",
    "Serial and Batch Bundle",
    "Territory",
]
GLOBAL_BUSINESS_REPORTS = [
    "Available Batch Report",
    "Available Serial No",
    "Balance Sheet",
    "Batch Item Expiry Status",
    "Batch-Wise Balance History",
    "Billed Items To Be Received",
    "Customer Ledger Summary",
    "Delivered Items To Be Billed",
    "General Ledger",
    "General and Payment Ledger Comparison",
    "Item Balance (Simple)",
    "Item Prices",
    "Item-wise Purchase History",
    "Item-wise Purchase Register",
    "Item-wise Sales History",
    "Item-wise Sales Register",
    "Payment Ledger",
    "Received Items To Be Billed",
    "Serial No Ledger",
    "Stock Balance",
    "Stock Ageing",
    "Stock and Account Value Comparison",
    "Stock Ledger",
    "Supplier Ledger Summary",
    "Trial Balance",
    "Trial Balance (Simple)",
    "Trial Balance for Party",
    "Voucher-wise Balance",
    "Warehouse Wise Stock Balance",
    "Warehouse wise Item Balance Age and Value",
]
GLOBAL_EXECUTION_REPORTS = [
    "Stock Balance",
    "Stock Ledger",
]

TRANSACTION_ROLE_DEPENDENCIES = {
    "Operations Manager": {
        "Serial and Batch Bundle": {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "amend": 1, "delete": 0},
        "Batch": {"read": 1, "write": 1, "create": 1},
        "Serial No": {"read": 1, "write": 1, "create": 1},
        "Company": {"read": 1},
        "Currency": {"read": 1},
        "Fiscal Year": {"read": 1},
        "Account": {"read": 1, "select": 1, "write": 0, "create": 0},
        "Stock Entry Type": {"read": 1},
        "Territory": {"read": 1},
    },
    "Inventory Operator": {
        "Serial and Batch Bundle": {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "amend": 1, "delete": 0},
        "Batch": {"read": 1, "write": 1, "create": 1},
        "Serial No": {"read": 1, "write": 1, "create": 1},
        "Company": {"read": 1},
        "Currency": {"read": 1},
        "Fiscal Year": {"read": 1},
        "Stock Entry Type": {"read": 1},
        "Territory": {"read": 1},
    },
    "Gripper Manufacturer": {
        "Serial and Batch Bundle": {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "amend": 1, "delete": 0},
        "Batch": {"read": 1, "write": 1, "create": 1},
        "Serial No": {"read": 1, "write": 1, "create": 1},
        "Company": {"read": 1},
        "Currency": {"read": 1},
        "Fiscal Year": {"read": 1},
        "Stock Entry Type": {"read": 1},
        "Territory": {"read": 1},
    },
}

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


def _role_permission_rows_for_doctype(doctype: str, role: str) -> list[dict[str, Any]]:
    if not frappe.db.exists("DocType", doctype):
        return [{"doctype": doctype, "role": role, "error": "DocType does not exist"}]

    fields = [
        "permlevel",
        "read",
        "write",
        "create",
        "submit",
        "cancel",
        "delete",
        "amend",
        "report",
        "export",
        "print",
        "select",
    ]
    rows: list[dict[str, Any]] = []
    for table in ["DocPerm", "Custom DocPerm"]:
        for row in frappe.get_all(
            table,
            filters={"parent": doctype, "role": role, "permlevel": 0},
            fields=fields,
            order_by="name asc",
        ):
            row = dict(row)
            row["source"] = table
            rows.append(row)
    return rows


def _permission_rows_satisfy(rows: list[dict[str, Any]], expected_bits: dict[str, int]) -> bool:
    for row in rows:
        if row.get("error"):
            continue
        if all(int(row.get(field) or 0) == int(value) for field, value in expected_bits.items()):
            return True
    return False


def _report_roles(report_name: str) -> list[str]:
    if not frappe.db.exists("Report", report_name):
        return []

    return frappe.get_all(
        "Has Role",
        filters={"parent": report_name, "parenttype": "Report", "parentfield": "roles"},
        pluck="role",
        order_by="idx asc",
    )


def _report_access_as_user(report_name: str, user: str) -> dict[str, Any]:
    previous_user = frappe.session.user
    try:
        if not frappe.db.exists("User", user):
            return {"user_exists": False, "permitted": False, "exception": None}

        frappe.set_user(user)
        report = frappe.get_doc("Report", report_name)
        return {
            "user_exists": True,
            "permitted": bool(report.is_permitted()),
            "exception": None,
        }
    except BaseException as exc:  # noqa: BLE001 - evidence should capture exact exception
        return {
            "user_exists": True,
            "permitted": False,
            "exception": exc.__class__.__name__,
            "message": str(exc),
        }
    finally:
        frappe.set_user(previous_user)


def _read_access_as_user(doctype: str, user: str) -> dict[str, Any]:
    try:
        return {
            "doctype_exists": bool(frappe.db.exists("DocType", doctype)),
            "has_read": bool(has_permission(doctype, ptype="read", user=user)),
            "exception": None,
        }
    except BaseException as exc:  # noqa: BLE001 - evidence should capture exact exception
        return {
            "doctype_exists": bool(frappe.db.exists("DocType", doctype)),
            "has_read": False,
            "exception": exc.__class__.__name__,
            "message": str(exc),
        }


def _finance_execution_filters() -> dict[str, Any]:
    company = frappe.db.get_single_value("Global Defaults", "default_company")
    if not company:
        company = frappe.get_all("Company", pluck="name", limit=1)[0]

    fiscal_year = frappe.get_all(
        "Fiscal Year",
        fields=["name", "year_start_date", "year_end_date"],
        order_by="year_start_date desc",
        limit=1,
    )[0]

    return {
        "company": company,
        "from_date": str(fiscal_year.year_start_date),
        "to_date": str(fiscal_year.year_end_date),
    }


def _execute_report_as_user(report_name: str, user: str) -> dict[str, Any]:
    from frappe.desk.query_report import run as run_report

    previous_user = frappe.session.user
    try:
        filters = _finance_execution_filters()
        frappe.set_user(user)
        result = run_report(
            report_name,
            filters=frappe._dict(filters),
            ignore_prepared_report=True,
            are_default_filters=False,
        )
        return {
            "executed": True,
            "exception": None,
            "filters": filters,
            "row_count": len(result.get("result") or []) if isinstance(result, dict) else None,
        }
    except BaseException as exc:  # noqa: BLE001 - evidence should capture exact exception
        return {
            "executed": False,
            "exception": exc.__class__.__name__,
            "message": str(exc),
        }
    finally:
        frappe.set_user(previous_user)


def run(site: str, sites_path: str, evidence_dir: str, global_report_user: str) -> int:
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
        for doctype in ["Item", "BOM", "BOM Export Package", "Configured BOM Snapshot"]:
            permission_result = bool(has_permission(doctype, ptype="read", user=user))
            list_result = _list_check_as_user(doctype, user)
            passed = (not permission_result) and list_result["row_count"] == 0
            label_doctype = doctype.lower().replace(" ", "_")
            _record(
                results,
                f"external_builder_{label_doctype}_denial_{user_key}",
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

    fixture_export_roles = ["Operations Viewer", "Global Viewer"]
    grants = _role_read_grants_for_doctype("Fixture Export Control", fixture_export_roles)
    passed = not grants
    _record(
        results,
        "fixture_export_control_viewer_finance_denial",
        passed,
        (
            "Operations Viewer and Global Viewer have no read grant on Fixture Export Control."
            if passed
            else "Operations Viewer or Global Viewer still has a read grant on Fixture Export Control."
        ),
        doctype="Fixture Export Control",
        roles=fixture_export_roles,
        grants=grants,
    )

    dependency_results = []
    for doctype in GLOBAL_REPORT_DEPENDENCY_DOCTYPES:
        access_result = _read_access_as_user(doctype, global_report_user)
        dependency_results.append({"doctype": doctype, **access_result})

    missing_dependencies = [row for row in dependency_results if not row["doctype_exists"] or not row["has_read"]]
    _record(
        results,
        "global_viewer_report_dependency_read_access",
        not missing_dependencies,
        (
            f"{GLOBAL_REPORT_ROLE} can read all finance report dependency DocTypes as {global_report_user}."
            if not missing_dependencies
            else f"{GLOBAL_REPORT_ROLE} is missing read access to one or more finance report dependency DocTypes."
        ),
        dependencies=dependency_results,
        missing=missing_dependencies,
    )

    global_report_results = []
    for report_name in GLOBAL_BUSINESS_REPORTS:
        roles = _report_roles(report_name)
        role_grant_present = GLOBAL_REPORT_ROLE in roles
        access_result = _report_access_as_user(report_name, global_report_user)
        passed = role_grant_present and access_result["permitted"]
        global_report_results.append(
            {
                "report": report_name,
                "passed": passed,
                "required_role": GLOBAL_REPORT_ROLE,
                "report_roles": roles,
                "global_report_user": global_report_user,
                "access_result": access_result,
            }
        )

    missing_global_reports = [row for row in global_report_results if not row["passed"]]
    _record(
        results,
        "global_viewer_business_report_access",
        not missing_global_reports,
        (
            f"{GLOBAL_REPORT_ROLE} can access all curated business/audit reports as {global_report_user}."
            if not missing_global_reports
            else f"{GLOBAL_REPORT_ROLE} is missing access to one or more curated business/audit reports."
        ),
        reports=global_report_results,
        missing=missing_global_reports,
    )

    execution_results = []
    for report_name in GLOBAL_EXECUTION_REPORTS:
        execution_result = _execute_report_as_user(report_name, global_report_user)
        execution_results.append({"report": report_name, **execution_result})

    failed_executions = [row for row in execution_results if not row["executed"]]
    _record(
        results,
        "global_viewer_critical_stock_report_execution",
        not failed_executions,
        (
            f"{GLOBAL_REPORT_ROLE} can execute Stock Balance and Stock Ledger as {global_report_user}."
            if not failed_executions
            else f"{GLOBAL_REPORT_ROLE} cannot execute one or more critical stock reports."
        ),
        executions=execution_results,
        failed=failed_executions,
    )

    transaction_dependency_results = []
    for role, doctype_expectations in TRANSACTION_ROLE_DEPENDENCIES.items():
        for doctype, expected_bits in doctype_expectations.items():
            rows = _role_permission_rows_for_doctype(doctype, role)
            transaction_dependency_results.append(
                {
                    "role": role,
                    "doctype": doctype,
                    "expected_bits": expected_bits,
                    "rows": rows,
                    "passed": _permission_rows_satisfy(rows, expected_bits),
                }
            )

    missing_transaction_dependencies = [
        row for row in transaction_dependency_results if not row["passed"]
    ]
    _record(
        results,
        "transaction_role_stock_dependency_permissions",
        not missing_transaction_dependencies,
        (
            "Transaction roles have required stock dependency DocPerm bits."
            if not missing_transaction_dependencies
            else "One or more transaction roles are missing required stock dependency DocPerm bits."
        ),
        dependencies=transaction_dependency_results,
        missing=missing_transaction_dependencies,
    )

    passed_count = sum(1 for row in results if row["passed"])
    failed_count = len(results) - passed_count
    payload = {
        "site": site,
        "sites_path": sites_path,
        "global_report_user": global_report_user,
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
    parser.add_argument(
        "--global-report-user",
        default=os.environ.get("GLOBAL_REPORT_USER", GLOBAL_REPORT_USER),
        help=f"Global Viewer user used to verify curated business/audit report access. Defaults to {GLOBAL_REPORT_USER}.",
    )
    parser.add_argument(
        "--finance-report-user",
        default=None,
        help="Deprecated alias for --global-report-user, retained so older checklist commands fail less sharply.",
    )
    args = parser.parse_args()
    global_report_user = args.finance_report_user or args.global_report_user

    try:
        return run(args.site, args.sites_path, args.evidence_dir, global_report_user)
    finally:
        frappe.destroy()


if __name__ == "__main__":
    sys.exit(main())
