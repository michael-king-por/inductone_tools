"""Version and repair the Electrical Balloon Callouts report access.

The report was originally a GUI-created Query Report under the ERPNext
Manufacturing module. Its role table referenced retired roles
(`Manufacturing User`, `Manufacturing Manager`, `Operations Member`, `Builder`),
so the hardened current roles could not execute it.

This patch:

- moves the report under the InductOne Tools module;
- replaces report roles with the current internal read roles only;
- grants Engineering User read/report access to BOM so the BOM-backed Query
  Report passes Frappe's ref_doctype permission check.

The BOM Custom DocPerm update is guarded so it only augments an already-managed
DocType and cannot trigger Frappe's "first Custom DocPerm replaces standard
DocPerms" trap.
"""

from __future__ import annotations

import frappe


REPORT_NAME = "Electrical Balloon Callouts"

REPORT_ROLES = [
    "System Manager",
    "Operations Manager",
    "Operations Viewer",
    "Inventory Operator",
    "Gripper Manufacturer",
    "Engineering User",
    "Finance Viewer",
    "Procurement User",
    "InductOne Manager",
    "InductOne Process Architect",
]

REPORT_QUERY = """SELECT
    bi.parent AS "BOM:Link/BOM:220",
    bi.custom_balloon_numbers AS "Balloon #:Data:90",
    bi.item_code AS "Component:Link/Item:140",
    bi.item_name AS "Component Name:Data:240",
    bi.qty AS "Qty:Float:80",
    bi.uom AS "UOM:Data:60",
    bi.custom_electrical_unit AS "Electrical Unit:Data:110",
    bi.custom_source_electrical_bom_rev AS "Source Rev:Data:80"
FROM `tabBOM Item` bi
INNER JOIN `tabBOM` b ON b.name = bi.parent
WHERE
    b.docstatus = 1
    AND b.is_active = 1
    AND IFNULL(bi.custom_balloon_numbers, '') != ''
ORDER BY
    bi.parent,
    CAST(bi.custom_balloon_numbers AS UNSIGNED)"""

READ = {
    "read": 1,
    "write": 0,
    "create": 0,
    "delete": 0,
    "submit": 0,
    "cancel": 0,
    "amend": 0,
    "report": 1,
    "export": 1,
    "import": 0,
    "print": 1,
    "email": 0,
    "share": 0,
    "select": 1,
}


def execute():
    ensure_engineering_user_bom_read()
    ensure_balloon_report()
    frappe.clear_cache()


def ensure_engineering_user_bom_read() -> None:
    doctype = "BOM"
    role = "Engineering User"

    if not frappe.db.exists("DocType", doctype):
        frappe.throw(f"Required ERPNext DocType is missing: {doctype}")

    if not frappe.db.exists("Custom DocPerm", {"parent": doctype}):
        print(
            f"SKIP {doctype}/{role}: DocType is not Custom-DocPerm-managed; "
            "refusing to create the first row."
        )
        return

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

    for field, value in READ.items():
        setattr(doc, field, value)

    if existing:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)


def ensure_balloon_report() -> None:
    if frappe.db.exists("Report", REPORT_NAME):
        report = frappe.get_doc("Report", REPORT_NAME)
    else:
        report = frappe.new_doc("Report")
        report.report_name = REPORT_NAME
        report.ref_doctype = "BOM"
        report.report_type = "Query Report"
        report.is_standard = "No"

    report.module = "InductOne Tools"
    report.ref_doctype = "BOM"
    report.report_type = "Query Report"
    report.is_standard = "No"
    report.disabled = 0
    report.prepared_report = 0
    report.query = REPORT_QUERY
    report.roles = []
    for role in REPORT_ROLES:
        report.append("roles", {"role": role})

    report.save(ignore_permissions=True)
