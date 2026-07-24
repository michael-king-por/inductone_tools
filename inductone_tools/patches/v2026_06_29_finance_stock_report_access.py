"""Retired legacy Finance Viewer stock-report access patch.

Finance Viewer has been folded into Global Viewer. The active read/report
coverage is now fixture-owned by the permanent role model. This patch remains
registered only so old and restored sites migrate cleanly; it must not recreate
Finance Viewer Custom DocPerms or Report-role rows.
"""

from __future__ import annotations

import frappe


FINANCE_REPORT_ROLE = "Finance Viewer"

READ_ONLY_ROLES = (
    "Finance Viewer",
    "Operations Viewer",
)

FINANCE_REPORT_DEPENDENCY_DOCTYPES = (
    "Batch",
    "Company",
    "Currency",
    "Fiscal Year",
    "Serial and Batch Bundle",
    "Territory",
)

FINANCE_BUSINESS_REPORTS = (
    # Inventory valuation / stock audit reports used by finance.
    "Stock Balance",
    "Stock Ledger",
    "Warehouse Wise Stock Balance",
    "Warehouse wise Item Balance Age and Value",
    "Stock Ageing",
    "Stock and Account Value Comparison",
    "Batch-Wise Balance History",
    "Batch Item Expiry Status",
    "Available Batch Report",
    "Available Serial No",
    "Serial No Ledger",
    "Item Balance (Simple)",
    "Item Prices",

    # Sales/purchase/accounting audit reports consistent with Finance Viewer.
    "General Ledger",
    "Trial Balance",
    "Trial Balance (Simple)",
    "Trial Balance for Party",
    "Balance Sheet",
    "Payment Ledger",
    "General and Payment Ledger Comparison",
    "Voucher-wise Balance",
    "Customer Ledger Summary",
    "Supplier Ledger Summary",
    "Item-wise Purchase Register",
    "Item-wise Sales Register",
    "Item-wise Purchase History",
    "Item-wise Sales History",
    "Delivered Items To Be Billed",
    "Received Items To Be Billed",
    "Billed Items To Be Received",
)


def execute():
    frappe.logger().info(
        "Skipping finance stock report access patch because %s is retired into Global Viewer.",
        FINANCE_REPORT_ROLE,
    )


def ensure_read_only_docperm(doctype: str, role: str) -> None:
    if not frappe.db.exists("DocType", doctype):
        frappe.throw(f"Required ERPNext DocType is missing: {doctype}")

    existing = frappe.db.exists(
        "Custom DocPerm",
        {
            "parent": doctype,
            "role": role,
            "permlevel": 0,
        },
    )
    if existing:
        doc = frappe.get_doc("Custom DocPerm", existing)
    else:
        doc = frappe.get_doc(
            {
                "doctype": "Custom DocPerm",
                "parent": doctype,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": role,
                "permlevel": 0,
            }
        )

    for field, value in {
        "read": 1,
        "write": 0,
        "create": 0,
        "delete": 0,
        "submit": 0,
        "cancel": 0,
        "amend": 0,
        "report": 1,
        "export": 1,
        "print": 1,
        "email": 1,
        "share": 0,
        "select": 1,
    }.items():
        setattr(doc, field, value)

    if existing:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)


def ensure_finance_report_role(report_name: str) -> None:
    if not frappe.db.exists("Report", report_name):
        frappe.throw(f"Required ERPNext report is missing: {report_name}")

    if frappe.db.exists(
        "Has Role",
        {
            "parent": report_name,
            "parenttype": "Report",
            "parentfield": "roles",
            "role": FINANCE_REPORT_ROLE,
        },
    ):
        return

    max_idx = (
        frappe.db.sql(
            """
            select coalesce(max(idx), 0)
            from `tabHas Role`
            where parent = %s
              and parenttype = 'Report'
              and parentfield = 'roles'
            """,
            report_name,
        )[0][0]
        or 0
    )

    frappe.get_doc(
        {
            "doctype": "Has Role",
            "parent": report_name,
            "parenttype": "Report",
            "parentfield": "roles",
            "idx": int(max_idx) + 1,
            "role": FINANCE_REPORT_ROLE,
        }
    ).insert(ignore_permissions=True)
