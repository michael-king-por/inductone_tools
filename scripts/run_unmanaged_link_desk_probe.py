"""Probe Desk link-picker behavior for unmanaged link dependency DocTypes.

This is intentionally not a raw insert smoke test. Frappe's Python insert path
can validate Link values without checking whether the logged-in user can read
the linked DocType. The Desk link picker does check read access, which is the
regression class being validated here.
"""

from __future__ import annotations

import argparse
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

import frappe
from frappe.desk.search import search_widget
from frappe.permissions import has_permission


DEFAULT_EVIDENCE_DIR = Path("/mnt/c/hub/frappe-sandbox/validation-evidence")

CHECKS = [
    {
        "label": "stock_entry_type_operations_manager",
        "user": "patty.gomez@plusonerobotics.com",
        "target_doctype": "Stock Entry Type",
        "reference_doctype": "Stock Entry",
        "expected_blocked_before_fix": True,
    },
    {
        "label": "stock_entry_type_gripper_manufacturer",
        "user": "nathaniel.pantuso@plusonerobotics.com",
        "target_doctype": "Stock Entry Type",
        "reference_doctype": "Stock Entry",
        "expected_blocked_before_fix": True,
    },
    {
        "label": "stock_entry_type_inventory_operator",
        "user": "candidate.inventory.operator@example.invalid",
        "target_doctype": "Stock Entry Type",
        "reference_doctype": "Stock Entry",
        "expected_blocked_before_fix": True,
    },
    {
        "label": "country_procurement_user",
        "user": "matthew.mcmillan@plusonerobotics.com",
        "target_doctype": "Country",
        "reference_doctype": "Address",
        "expected_blocked_before_fix": False,
    },
    {
        "label": "reserved_by_engineering_user",
        "user": "shaun.edwards@plusonerobotics.com",
        "target_doctype": "User",
        "reference_doctype": "Part Number Assignment",
        "expected_blocked_before_fix": False,
    },
]


def run_check(check: dict) -> dict:
    frappe.set_user(check["user"])
    record = {
        **check,
        "roles": frappe.get_roles(check["user"]),
        "has_read": bool(
            has_permission(
                check["target_doctype"],
                ptype="read",
                user=check["user"],
            )
        ),
    }
    try:
        rows = search_widget(
            check["target_doctype"],
            txt="",
            start=0,
            page_length=10,
            reference_doctype=check["reference_doctype"],
            ignore_user_permissions=False,
        )
        row_count = len(rows or [])
        record.update(
            {
                "search_exception": None,
                "row_count": row_count,
                "sample_rows": rows[:3] if isinstance(rows, list) else str(rows)[:300],
                "blocked": row_count == 0 and not record["has_read"],
            }
        )
    except Exception as exc:  # noqa: BLE001 - evidence should preserve exact Frappe exception.
        record.update(
            {
                "search_exception": {
                    "class": type(exc).__name__,
                    "message": str(exc),
                },
                "traceback": traceback.format_exc(limit=3),
                "row_count": None,
                "sample_rows": [],
                "blocked": True,
            }
        )
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument(
        "--phase",
        default="probe",
        help="Evidence filename label, e.g. before_stock_entry_type_fix or after_stock_entry_type_fix.",
    )
    args = parser.parse_args()

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        results = [run_check(check) for check in CHECKS]
        summary = {
            "site": args.site,
            "phase": args.phase,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "checks": results,
            "blocked": [r["label"] for r in results if r["blocked"]],
            "not_blocked": [r["label"] for r in results if not r["blocked"]],
        }
    finally:
        frappe.destroy()

    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.evidence_dir / f"unmanaged_link_desk_probe_{args.phase}_{stamp}.json"
    out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    for result in results:
        state = "BLOCKED" if result["blocked"] else "NOT_BLOCKED"
        exc = result.get("search_exception")
        exc_label = f" exception={exc['class']}" if exc else ""
        print(f"{state} {result['label']} rows={result.get('row_count')}{exc_label}")
    print(f"Evidence: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
