"""Retired legacy Finance Viewer core-accounting report patch.

Finance Viewer has been folded into Global Viewer. The active report access is
now maintained by fixtures and the Global Viewer role model. This patch remains
registered only so existing patch manifests migrate cleanly; it must not create
or restore Finance Viewer grants.
"""

from __future__ import annotations

import frappe


FINANCE_VIEWER = "Finance Viewer"

REPORTS = [
    "Balance Sheet",
    "General Ledger",
    "Trial Balance",
]


def execute() -> None:
    frappe.logger().info(
        "Skipping finance core report access patch because %s is retired into Global Viewer.",
        FINANCE_VIEWER,
    )


def ensure_report_role(report_name: str, role: str) -> None:
    if not frappe.db.exists("Report", report_name):
        frappe.throw(f"Required ERPNext Report is missing: {report_name}")

    report = frappe.get_doc("Report", report_name)
    if any(row.role == role for row in report.get("roles", [])):
        return

    report.append("roles", {"role": role})
    report.save(ignore_permissions=True)
