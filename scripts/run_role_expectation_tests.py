#!/usr/bin/env python3
"""Validate the locked InductOne permission model by role/persona.

This is intentionally data-driven: the role model below is the test charter.
Changing role expectations should be a data edit with review, not new test
logic. The script is candidate-safe and evidence-first:

- asserts expected allow/deny ptypes through Frappe's permission engine;
- runs critical Global Viewer reports;
- checks external-builder list denials, not just DocPerm rows;
- writes JSON evidence and exits non-zero on any failed expectation.
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

PERMISSION_PTYPES = ["read", "write", "create", "submit", "cancel", "delete"]

ROLE_EXPECTATIONS: list[dict[str, Any]] = [
    {
        "role": "System Manager",
        "persona": "ian.deliz@plusonerobotics.com",
        "can": [
            {"kind": "permission", "doctype": "DocType", "ptype": "read"},
            {"kind": "permission", "doctype": "Custom DocPerm", "ptype": "read"},
            {"kind": "permission", "doctype": "Custom DocPerm", "ptype": "write"},
            {"kind": "permission", "doctype": "Fixture Export Control", "ptype": "read"},
        ],
        "cannot": [],
    },
    {
        "role": "InductOne Process Architect",
        "persona": "michael.king@plusonerobotics.com",
        "can": [
            {"kind": "permission", "doctype": "InductOne Configuration Option", "ptype": "write"},
            {"kind": "permission", "doctype": "Part Number Assignment", "ptype": "create"},
            {"kind": "permission", "doctype": "Engineering Signoff", "ptype": "write"},
            {"kind": "permission", "doctype": "Fixture Export Control", "ptype": "read"},
        ],
        "cannot": [],
    },
    {
        "role": "InductOne Manager",
        "persona": "jim.haws@plusonerobotics.com",
        "can": [
            {"kind": "permission", "doctype": "InductOne Build", "ptype": "create"},
            {"kind": "permission", "doctype": "InductOne Configuration Order", "ptype": "write"},
            {"kind": "permission", "doctype": "InductOne Build Completion", "ptype": "write"},
            {"kind": "permission", "doctype": "InductOne As-Built Record", "ptype": "create"},
        ],
        "cannot": [
            {"kind": "permission", "doctype": "Fixture Export Control", "ptype": "read"},
            {"kind": "permission", "doctype": "Custom DocPerm", "ptype": "read"},
        ],
    },
    {
        "role": "Engineering User",
        "persona": "shaun.edwards@plusonerobotics.com",
        "can": [
            {"kind": "permission", "doctype": "Engineering Signoff", "ptype": "write"},
            {"kind": "permission", "doctype": "Part Number Assignment", "ptype": "create"},
            {"kind": "permission", "doctype": "InductOne Options Catalog", "ptype": "read"},
            {"kind": "permission", "doctype": "BOM", "ptype": "read"},
        ],
        "cannot": [
            {"kind": "permission", "doctype": "InductOne Build", "ptype": "create"},
            {"kind": "permission", "doctype": "Fixture Export Control", "ptype": "read"},
            {"kind": "permission", "doctype": "Custom DocPerm", "ptype": "read"},
        ],
    },
    {
        "role": "Operations Manager",
        "persona": "patty.gomez@plusonerobotics.com",
        "can": [
            {"kind": "permission", "doctype": "Item", "ptype": "write"},
            {"kind": "permission", "doctype": "BOM", "ptype": "write"},
            {"kind": "permission", "doctype": "Sales Order", "ptype": "submit"},
            {"kind": "permission", "doctype": "Delivery Note", "ptype": "submit"},
            {"kind": "permission", "doctype": "Stock Entry", "ptype": "submit"},
        ],
        "cannot": [
            {"kind": "permission", "doctype": "InductOne Configuration Option", "ptype": "write"},
            {"kind": "permission", "doctype": "Fixture Export Control", "ptype": "read"},
            {"kind": "permission", "doctype": "Custom DocPerm", "ptype": "read"},
        ],
    },
    {
        "role": "Operations Viewer",
        "persona": "zohair.naqvi@plusonerobotics.com",
        "can": [
            {"kind": "permission", "doctype": "Item", "ptype": "read"},
            {"kind": "permission", "doctype": "BOM", "ptype": "read"},
            {"kind": "permission", "doctype": "Sales Order", "ptype": "read"},
            {"kind": "permission", "doctype": "Stock Entry", "ptype": "read"},
            {"kind": "permission", "doctype": "InductOne Field Change", "ptype": "read"},
        ],
        "cannot": [
            {"kind": "permission", "doctype": "Item", "ptype": "write"},
            {"kind": "permission", "doctype": "Sales Order", "ptype": "create"},
            {"kind": "permission", "doctype": "Stock Entry", "ptype": "submit"},
            {"kind": "permission", "doctype": "Fixture Export Control", "ptype": "read"},
            {"kind": "permission", "doctype": "Custom DocPerm", "ptype": "read"},
        ],
    },
    {
        "role": "Inventory Operator",
        "persona": "candidate.inventory.operator@example.invalid",
        "candidate_roles": ["Inventory Operator"],
        "can": [
            {"kind": "permission", "doctype": "Stock Entry", "ptype": "submit"},
            {"kind": "permission", "doctype": "Purchase Receipt", "ptype": "submit"},
            {"kind": "permission", "doctype": "Serial and Batch Bundle", "ptype": "submit"},
            {"kind": "permission", "doctype": "Batch", "ptype": "create"},
        ],
        "cannot": [
            {"kind": "permission", "doctype": "Sales Order", "ptype": "create"},
            {"kind": "permission", "doctype": "InductOne Field Change", "ptype": "create"},
            {"kind": "permission", "doctype": "Custom DocPerm", "ptype": "read"},
        ],
    },
    {
        "role": "Gripper Manufacturer",
        "persona": "candidate.gripper.manufacturer@example.invalid",
        "candidate_roles": ["Gripper Manufacturer"],
        "can": [
            {"kind": "permission", "doctype": "Work Order", "ptype": "submit"},
            {"kind": "permission", "doctype": "Stock Entry", "ptype": "submit"},
            {"kind": "permission", "doctype": "Pick List", "ptype": "submit"},
            {"kind": "permission", "doctype": "Serial and Batch Bundle", "ptype": "submit"},
        ],
        "cannot": [
            {"kind": "permission", "doctype": "Sales Order", "ptype": "create"},
            {"kind": "permission", "doctype": "InductOne Build", "ptype": "create"},
            {"kind": "permission", "doctype": "Custom DocPerm", "ptype": "read"},
        ],
    },
    {
        "role": "Procurement User",
        "persona": "matthew.mcmillan@plusonerobotics.com",
        "can": [
            {"kind": "permission", "doctype": "Item Price", "ptype": "write"},
            {"kind": "permission", "doctype": "Item Price", "ptype": "create"},
            {"kind": "permission", "doctype": "Purchase Order", "ptype": "create"},
            {"kind": "permission", "doctype": "Purchase Order", "ptype": "read"},
            {"kind": "permission", "doctype": "Supplier", "ptype": "read"},
        ],
        "cannot": [
            {"kind": "permission", "doctype": "Purchase Order", "ptype": "submit"},
            {"kind": "permission", "doctype": "BOM", "ptype": "write"},
            {"kind": "permission", "doctype": "Custom DocPerm", "ptype": "read"},
        ],
    },
    {
        "role": "Global Viewer",
        "persona": "matt.speer@plusonerobotics.com",
        "can": [
            {"kind": "permission", "doctype": "Item", "ptype": "read"},
            {"kind": "permission", "doctype": "BOM", "ptype": "read"},
            {"kind": "permission", "doctype": "Sales Order", "ptype": "read"},
            {"kind": "permission", "doctype": "Stock Entry", "ptype": "read"},
            {"kind": "permission", "doctype": "GL Entry", "ptype": "read"},
            {"kind": "permission", "doctype": "User", "ptype": "read"},
            {"kind": "permission", "doctype": "Report", "ptype": "read"},
            {"kind": "permission", "doctype": "Item", "ptype": "export"},
            {"kind": "report_access", "report": "Balance Sheet"},
            {"kind": "report_access", "report": "General Ledger"},
            {"kind": "report_access", "report": "Trial Balance"},
            {"kind": "report_access", "report": "Stock Balance"},
            {"kind": "report_access", "report": "Stock Ledger"},
            {"kind": "report_access", "report": "Electrical Balloon Callouts"},
            {"kind": "report_execution", "report": "Balance Sheet"},
            {"kind": "report_execution", "report": "General Ledger"},
            {"kind": "report_execution", "report": "Trial Balance"},
            {"kind": "report_execution", "report": "Stock Balance"},
            {"kind": "report_execution", "report": "Electrical Balloon Callouts"},
        ],
        "cannot": [
            {"kind": "permission", "doctype": "Item", "ptype": "write"},
            {"kind": "permission", "doctype": "Sales Order", "ptype": "create"},
            {"kind": "permission", "doctype": "Stock Entry", "ptype": "submit"},
            {"kind": "permission", "doctype": "DocType", "ptype": "read", "expected_denial": "framework_metadata_carveout"},
            {"kind": "permission", "doctype": "Custom DocPerm", "ptype": "read", "expected_denial": "framework_metadata_carveout"},
        ],
    },
    {
        "role": "InductOne External Builder",
        "persona": "motion.builder@plusonerobotics.com",
        "also_check_personas": ["lam@plusonerobotics.com"],
        "can": [
            {"kind": "workspace_visible", "workspace": "Builder Portal"},
            {"kind": "permission", "doctype": "InductOne Configuration Order", "ptype": "read"},
            {"kind": "permission", "doctype": "InductOne Build Completion", "ptype": "create"},
        ],
        "cannot": [
            {"kind": "list_denial", "doctype": "Item"},
            {"kind": "list_denial", "doctype": "BOM"},
            {"kind": "list_denial", "doctype": "BOM Export Package"},
            {"kind": "list_denial", "doctype": "Configured BOM Snapshot"},
            {"kind": "list_denial", "doctype": "InductOne Field Change"},
            {"kind": "list_denial", "doctype": "InductOne Field Change Request"},
            {"kind": "workspace_visible", "workspace": "Home"},
            {"kind": "workspace_visible", "workspace": "Stock"},
            {"kind": "workspace_visible", "workspace": "Engineering"},
            {"kind": "workspace_visible", "workspace": "Operations"},
        ],
    },
]


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run role/persona expectation tests.")
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--evidence-dir", default=DEFAULT_EVIDENCE_DIR)
    return parser.parse_args()


def init_frappe(site: str, sites_path: str):
    import frappe

    (Path(sites_path) / site / "logs").mkdir(parents=True, exist_ok=True)
    (Path.cwd() / site / "logs").mkdir(parents=True, exist_ok=True)
    frappe.init(site=site, sites_path=sites_path)
    frappe.connect()
    return frappe


def ensure_candidate_persona(frappe, site: str, user: str, roles: list[str]) -> dict[str, Any]:
    if "candidate" not in site:
        return {"created_or_updated": False, "reason": "non-candidate site"}
    if not user.startswith("candidate.") or not user.endswith("@example.invalid"):
        return {"created_or_updated": False, "reason": "not a synthetic candidate persona"}

    if frappe.db.exists("User", user):
        doc = frappe.get_doc("User", user)
    else:
        doc = frappe.get_doc(
            {
                "doctype": "User",
                "email": user,
                "first_name": user.split("@", 1)[0],
                "user_type": "System User",
                "enabled": 1,
                "send_welcome_email": 0,
            }
        )
        doc.insert(ignore_permissions=True)

    doc.enabled = 1
    doc.user_type = "System User"
    doc.role_profile_name = ""
    doc.set("roles", [])
    for role in roles:
        doc.append("roles", {"role": role})
    doc.save(ignore_permissions=True)
    frappe.clear_cache(user=user)
    return {"created_or_updated": True, "roles": roles}


def check_permission(frappe, user: str, doctype: str, ptype: str, expected: bool) -> dict[str, Any]:
    from frappe.permissions import has_permission

    try:
        actual = bool(has_permission(doctype, ptype=ptype, user=user))
        return {
            "kind": "permission",
            "user": user,
            "doctype": doctype,
            "ptype": ptype,
            "expected": expected,
            "actual": actual,
            "passed": actual is expected,
            "exception": None,
        }
    except BaseException as exc:  # noqa: BLE001 - evidence wants exact exception
        return {
            "kind": "permission",
            "user": user,
            "doctype": doctype,
            "ptype": ptype,
            "expected": expected,
            "actual": False,
            "passed": (not expected),
            "exception": exc.__class__.__name__,
            "message": str(exc),
        }


def check_list_denial(frappe, user: str, doctype: str) -> dict[str, Any]:
    previous = frappe.session.user
    try:
        frappe.set_user(user)
        rows = frappe.get_list(doctype, fields=["name"], limit_page_length=1)
        row_count = len(rows)
        return {
            "kind": "list_denial",
            "user": user,
            "doctype": doctype,
            "expected": "no rows readable",
            "row_count": row_count,
            "sample": rows[0].name if rows else None,
            "passed": row_count == 0,
            "exception": None,
        }
    except BaseException as exc:  # noqa: BLE001
        return {
            "kind": "list_denial",
            "user": user,
            "doctype": doctype,
            "expected": "permission denial or empty list",
            "row_count": 0,
            "passed": True,
            "exception": exc.__class__.__name__,
            "message": str(exc),
        }
    finally:
        frappe.set_user(previous)


def workspace_visible(frappe, user: str, workspace: str) -> dict[str, Any]:
    if not frappe.db.exists("Workspace", workspace):
        return {
            "kind": "workspace_visible",
            "user": user,
            "workspace": workspace,
            "visible": False,
            "roles": [],
            "exception": "MissingWorkspace",
        }

    roles = set(frappe.get_roles(user))
    ws = frappe.get_doc("Workspace", workspace)
    workspace_roles = {row.role for row in ws.get("roles", []) if row.role}
    is_hidden = bool(getattr(ws, "is_hidden", 0))
    visible = (not is_hidden) and (not workspace_roles or bool(roles & workspace_roles))
    return {
        "kind": "workspace_visible",
        "user": user,
        "workspace": workspace,
        "visible": visible,
        "user_roles": sorted(roles),
        "workspace_roles": sorted(workspace_roles),
        "is_hidden": is_hidden,
        "exception": None,
    }


def check_workspace(frappe, user: str, workspace: str, expected: bool) -> dict[str, Any]:
    result = workspace_visible(frappe, user, workspace)
    result["expected"] = expected
    result["passed"] = bool(result.get("visible")) is expected
    return result


def report_access(frappe, user: str, report_name: str) -> dict[str, Any]:
    previous = frappe.session.user
    try:
        if not frappe.db.exists("Report", report_name):
            return {
                "kind": "report_access",
                "user": user,
                "report": report_name,
                "passed": False,
                "exception": "MissingReport",
            }
        frappe.set_user(user)
        report = frappe.get_doc("Report", report_name)
        return {
            "kind": "report_access",
            "user": user,
            "report": report_name,
            "permitted": bool(report.is_permitted()),
            "report_roles": [row.role for row in report.get("roles", [])],
            "passed": bool(report.is_permitted()),
            "exception": None,
        }
    except BaseException as exc:  # noqa: BLE001
        return {
            "kind": "report_access",
            "user": user,
            "report": report_name,
            "permitted": False,
            "passed": False,
            "exception": exc.__class__.__name__,
            "message": str(exc),
        }
    finally:
        frappe.set_user(previous)


def _first_company_and_fiscal_year(frappe) -> tuple[str | None, dict[str, Any] | None]:
    company = frappe.db.get_value("Company", {}, "name", order_by="creation asc")
    fiscal_year = frappe.get_all(
        "Fiscal Year",
        fields=["name", "year_start_date", "year_end_date"],
        order_by="year_start_date desc",
        limit=1,
    )
    return company, (fiscal_year[0] if fiscal_year else None)


def report_filters(frappe, report_name: str) -> dict[str, Any]:
    company, fiscal_year = _first_company_and_fiscal_year(frappe)
    start = fiscal_year.year_start_date if fiscal_year else None
    end = fiscal_year.year_end_date if fiscal_year else None
    fy = fiscal_year.name if fiscal_year else None

    if report_name == "Balance Sheet":
        return {
            "company": company,
            "filter_based_on": "Fiscal Year",
            "period_start_date": start,
            "period_end_date": end,
            "from_fiscal_year": fy,
            "to_fiscal_year": fy,
            "periodicity": "Yearly",
            "accumulated_values": 1,
        }
    if report_name == "General Ledger":
        return {
            "company": company,
            "from_date": start,
            "to_date": end,
            "group_by": "Group by Voucher (Consolidated)",
        }
    if report_name == "Trial Balance":
        return {
            "company": company,
            "fiscal_year": fy,
            "period_start_date": start,
            "period_end_date": end,
            "show_zero_values": 0,
        }
    if report_name == "Stock Balance":
        return {
            "company": company,
            "from_date": start,
            "to_date": end,
        }
    if report_name == "Stock Ledger":
        return {
            "company": company,
            "from_date": start,
            "to_date": end,
        }
    return {}


def report_execution(frappe, user: str, report_name: str) -> dict[str, Any]:
    previous = frappe.session.user
    try:
        if not frappe.db.exists("Report", report_name):
            return {
                "kind": "report_execution",
                "user": user,
                "report": report_name,
                "passed": False,
                "exception": "MissingReport",
            }
        frappe.set_user(user)
        from frappe.desk.query_report import run as run_query_report

        filters = report_filters(frappe, report_name)
        result = run_query_report(report_name, filters=filters, ignore_prepared_report=True)
        columns = result.get("columns") if isinstance(result, dict) else None
        rows = result.get("result") if isinstance(result, dict) else result
        return {
            "kind": "report_execution",
            "user": user,
            "report": report_name,
            "filters": filters,
            "row_count": len(rows or []),
            "column_count": len(columns or []),
            "passed": True,
            "exception": None,
        }
    except BaseException as exc:  # noqa: BLE001
        return {
            "kind": "report_execution",
            "user": user,
            "report": report_name,
            "passed": False,
            "exception": exc.__class__.__name__,
            "message": str(exc),
            "filters": report_filters(frappe, report_name),
        }
    finally:
        frappe.set_user(previous)


def run_expectation(frappe, user: str, row: dict[str, Any], expected: bool) -> dict[str, Any]:
    kind = row["kind"]
    if kind == "permission":
        result = check_permission(frappe, user, row["doctype"], row["ptype"], expected)
    elif kind == "list_denial":
        result = check_list_denial(frappe, user, row["doctype"])
        result["expected"] = False
    elif kind == "workspace_visible":
        result = check_workspace(frappe, user, row["workspace"], expected)
    elif kind == "report_access":
        result = report_access(frappe, user, row["report"])
        result["expected"] = expected
    elif kind == "report_execution":
        result = report_execution(frappe, user, row["report"])
        result["expected"] = expected
    else:
        result = {
            "kind": kind,
            "user": user,
            "passed": False,
            "exception": "UnknownExpectationKind",
            "expectation": row,
        }

    if row.get("expected_denial"):
        result["expected_denial"] = row["expected_denial"]
    return result


def run(site: str, sites_path: str, evidence_dir: str) -> int:
    frappe = init_frappe(site, sites_path)
    evidence_path = Path(evidence_dir) / f"role_expectation_tests_{timestamp()}.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    persona_setup: list[dict[str, Any]] = []
    try:
        for role_block in ROLE_EXPECTATIONS:
            persona = role_block["persona"]
            if role_block.get("candidate_roles"):
                persona_setup.append(
                    {
                        "persona": persona,
                        **ensure_candidate_persona(
                            frappe, site, persona, role_block["candidate_roles"]
                        ),
                    }
                )

            users = [persona, *role_block.get("also_check_personas", [])]
            for user in users:
                if not frappe.db.exists("User", user):
                    results.append(
                        {
                            "role": role_block["role"],
                            "user": user,
                            "kind": "persona_exists",
                            "passed": False,
                            "exception": "MissingUser",
                        }
                    )
                    continue

                for expectation in role_block.get("can", []):
                    result = run_expectation(frappe, user, expectation, True)
                    result["role"] = role_block["role"]
                    result["sense"] = "can"
                    results.append(result)

                for expectation in role_block.get("cannot", []):
                    result = run_expectation(frappe, user, expectation, False)
                    result["role"] = role_block["role"]
                    result["sense"] = "cannot"
                    results.append(result)

        passed = sum(1 for row in results if row.get("passed"))
        failed = len(results) - passed
        payload = {
            "site": site,
            "sites_path": sites_path,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total": len(results),
                "passed": passed,
                "failed": failed,
            },
            "persona_setup": persona_setup,
            "expectation_table": ROLE_EXPECTATIONS,
            "results": results,
        }
        evidence_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
    finally:
        frappe.destroy()

    for row in results:
        status = "PASS" if row.get("passed") else "FAIL"
        label = row.get("kind")
        target = row.get("doctype") or row.get("workspace") or row.get("report") or ""
        detail = row.get("ptype") or row.get("expected_denial") or ""
        print(f"{status} {row.get('role')} {row.get('sense')} {label} {target} {detail}".rstrip())
        if not row.get("passed"):
            print(f"  detail={json.dumps(row, default=str)}")
    print(f"SUMMARY {passed}/{len(results)} passed; evidence={evidence_path}")
    return 0 if failed == 0 else 1


def main() -> int:
    args = parse_args()
    return run(args.site, args.sites_path, args.evidence_dir)


if __name__ == "__main__":
    sys.exit(main())
