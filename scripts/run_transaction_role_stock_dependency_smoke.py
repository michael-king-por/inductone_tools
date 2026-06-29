#!/usr/bin/env python3
"""Candidate-only execution smoke for transaction-role stock dependencies.

This script intentionally mutates only the candidate sandbox. It creates
synthetic records inside one database transaction, executes the stock workflows
as curated roles, writes JSON evidence, and rolls the transaction back.

It is designed to catch the bug class where a role looks correct in Desk/list
views but fails inside ERPNext's submit-time serial/batch dependency chain.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


DEFAULT_EVIDENCE_DIR = os.environ.get(
    "VALIDATION_EVIDENCE_DIR",
    "/mnt/c/hub/frappe-sandbox/validation-evidence",
)

OPERATIONS_MANAGER_USER = "candidate.operations.manager@example.invalid"
INVENTORY_OPERATOR_USER = "candidate.inventory.operator@example.invalid"
GRIPPER_MANUFACTURER_USER = "candidate.gripper.manufacturer@example.invalid"
PROCUREMENT_USER = "candidate.procurement.user@example.invalid"


frappe = None


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _record(
    results: list[dict[str, Any]],
    label: str,
    passed: bool,
    detail: str,
    **extra: Any,
) -> None:
    print(f"{'PASS' if passed else 'FAIL'} {label}: {detail}")
    row = {
        "label": label,
        "passed": passed,
        "detail": detail,
    }
    row.update(extra)
    results.append(row)


def _exception_payload(exc: BaseException) -> dict[str, str]:
    return {
        "exception": exc.__class__.__name__,
        "message": str(exc),
    }


def _safe_call(fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        payload = fn()
        return {"passed": True, **payload}
    except BaseException as exc:  # noqa: BLE001 - exact exception is validation evidence
        return {"passed": False, **_exception_payload(exc)}


def _first_value(doctype: str, filters: dict[str, Any] | None = None, field: str = "name") -> str:
    rows = frappe.get_all(doctype, filters=filters or {}, pluck=field, limit=1)
    if not rows:
        raise RuntimeError(f"No {doctype} found for filters {filters or {}}")
    return rows[0]


def _ensure_exact_role_user(user: str, roles: list[str]) -> None:
    frappe.set_user("Administrator")
    if not frappe.db.exists("User", user):
        doc = frappe.get_doc(
            {
                "doctype": "User",
                "email": user,
                "first_name": "Candidate",
                "last_name": "Smoke",
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

    doc.set("roles", [])
    for role in roles:
        doc.append("roles", {"role": role})
    doc.save(ignore_permissions=True)
    frappe.clear_cache(user=user)


def _insert_item(
    item_code: str,
    *,
    item_group: str,
    warehouse: str,
    company: str,
    tracked: bool = False,
    include_in_manufacturing: bool = True,
) -> str:
    doc = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": item_code,
            "custom_item_code_display": item_code,
            "item_name": item_code,
            "description": item_code,
            "item_group": item_group,
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "is_purchase_item": 1,
            "is_sales_item": 1,
            "include_item_in_manufacturing": 1 if include_in_manufacturing else 0,
            "valuation_rate": 1,
            "standard_rate": 1,
            "has_batch_no": 1 if tracked else 0,
            "create_new_batch": 1 if tracked else 0,
            "batch_number_series": f"{item_code}-B-.#####" if tracked else None,
            "has_serial_no": 1 if tracked else 0,
            "serial_no_series": f"{item_code}-S-.#####" if tracked else None,
            "item_defaults": [
                {
                    "company": company,
                    "default_warehouse": warehouse,
                    "expense_account": _first_value(
                        "Account",
                        {"company": company, "is_group": 0, "root_type": "Expense"},
                    ),
                    "income_account": _first_value(
                        "Account",
                        {"company": company, "is_group": 0, "root_type": "Income"},
                    ),
                }
            ],
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _make_stock_entry(
    *,
    stock_entry_type: str,
    company: str,
    items: list[dict[str, Any]],
    work_order: str | None = None,
    bom_no: str | None = None,
    fg_completed_qty: float | None = None,
):
    purpose = frappe.db.get_value("Stock Entry Type", stock_entry_type, "purpose") or stock_entry_type
    doc = frappe.get_doc(
        {
            "doctype": "Stock Entry",
            "stock_entry_type": stock_entry_type,
            "purpose": purpose,
            "company": company,
            "work_order": work_order,
            "bom_no": bom_no,
            "fg_completed_qty": fg_completed_qty,
            "items": items,
        }
    )
    doc.set_stock_entry_type()
    if fg_completed_qty is not None:
        doc.fg_completed_qty = fg_completed_qty
    return doc


def _submitted_bundle_names_for_voucher(voucher_type: str, voucher_no: str) -> list[str]:
    return frappe.get_all(
        "Serial and Batch Bundle",
        filters={"voucher_type": voucher_type, "voucher_no": voucher_no, "docstatus": 1},
        pluck="name",
        order_by="creation asc",
    )


def _submitted_bundle_entries(bundle_name: str) -> list[dict[str, Any]]:
    return frappe.get_all(
        "Serial and Batch Entry",
        filters={"parent": bundle_name},
        fields=["serial_no", "batch_no", "qty", "warehouse"],
        order_by="idx asc",
    )


def _receive_tracked_stock_as_user(
    *,
    user: str,
    item_code: str,
    company: str,
    warehouse: str,
    qty: float,
) -> dict[str, Any]:
    previous_user = frappe.session.user
    try:
        frappe.set_user(user)
        doc = _make_stock_entry(
            stock_entry_type="Material Receipt",
            company=company,
            items=[
                {
                    "item_code": item_code,
                    "qty": qty,
                    "t_warehouse": warehouse,
                    "uom": "Nos",
                    "stock_uom": "Nos",
                    "conversion_factor": 1,
                    "basic_rate": 1,
                    "allow_zero_valuation_rate": 1,
                }
            ],
        )
        doc.insert()
        doc.submit()
        bundles = _submitted_bundle_names_for_voucher("Stock Entry", doc.name)
        if not bundles:
            raise AssertionError(f"No submitted Serial and Batch Bundle created for {doc.name}")
        return {
            "stock_entry": doc.name,
            "bundles": bundles,
            "entries": _submitted_bundle_entries(bundles[0]),
        }
    finally:
        frappe.set_user(previous_user)


def _operations_manager_smoke(context: dict[str, Any]) -> dict[str, Any]:
    previous_user = frappe.session.user
    try:
        frappe.set_user(OPERATIONS_MANAGER_USER)
        sales_order = frappe.get_doc(
            {
                "doctype": "Sales Order",
                "customer": context["customer"],
                "order_type": "Sales",
                "company": context["company"],
                "currency": "USD",
                "conversion_rate": 1,
                "selling_price_list": "Standard Selling",
                "price_list_currency": "USD",
                "plc_conversion_rate": 1,
                "custom_approval_from": "Invoice Generated",
                "items": [
                    {
                        "item_code": context["tracked_item"],
                        "delivery_date": frappe.utils.today(),
                        "qty": 1,
                        "uom": "Nos",
                        "stock_uom": "Nos",
                        "conversion_factor": 1,
                        "rate": 1,
                        "warehouse": context["stock_warehouse"],
                    }
                ],
            }
        )
        sales_order.insert()
        sales_order.submit()

        material_issue = _make_stock_entry(
            stock_entry_type="Material Issue",
            company=context["company"],
            items=[
                {
                    "item_code": context["tracked_item"],
                    "qty": 1,
                    "s_warehouse": context["stock_warehouse"],
                    "uom": "Nos",
                    "stock_uom": "Nos",
                    "conversion_factor": 1,
                    "basic_rate": 1,
                    "allow_zero_valuation_rate": 1,
                }
            ],
        )
        material_issue.insert()
        material_issue.submit()
        bundles = _submitted_bundle_names_for_voucher("Stock Entry", material_issue.name)
        if not bundles:
            raise AssertionError(
                f"No submitted Serial and Batch Bundle created for outbound {material_issue.name}"
            )
        return {
            "sales_order": sales_order.name,
            "stock_entry": material_issue.name,
            "bundles": bundles,
            "entries": _submitted_bundle_entries(bundles[0]),
        }
    finally:
        frappe.set_user(previous_user)


def _inventory_operator_smoke(context: dict[str, Any]) -> dict[str, Any]:
    return _receive_tracked_stock_as_user(
        user=INVENTORY_OPERATOR_USER,
        item_code=context["tracked_item"],
        company=context["company"],
        warehouse=context["stock_warehouse"],
        qty=2,
    )


def _gripper_manufacturer_smoke(context: dict[str, Any]) -> dict[str, Any]:
    previous_user = frappe.session.user
    try:
        frappe.set_user(GRIPPER_MANUFACTURER_USER)
        work_order = frappe.get_doc(
            {
                "doctype": "Work Order",
                "production_item": context["gripper_item"],
                "bom_no": context["bom"],
                "company": context["company"],
                "qty": 1,
                "source_warehouse": context["stock_warehouse"],
                "wip_warehouse": context["wip_warehouse"],
                "fg_warehouse": context["fg_warehouse"],
                "planned_start_date": frappe.utils.today(),
                "skip_transfer": 1,
            }
        )
        work_order.insert()
        work_order.submit()

        from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

        manufacture = frappe.get_doc(make_stock_entry(work_order.name, "Manufacture", 1))
        for item in manufacture.items:
            item.allow_zero_valuation_rate = 1
            if item.item_code == context["raw_item"]:
                item.basic_rate = item.basic_rate or 1
            if item.item_code == context["gripper_item"]:
                item.basic_rate = item.basic_rate or 1
        manufacture.insert()
        manufacture.submit()
        bundles = _submitted_bundle_names_for_voucher("Stock Entry", manufacture.name)
        if not bundles:
            raise AssertionError(
                f"No submitted Serial and Batch Bundle created for manufacture {manufacture.name}"
            )
        return {
            "work_order": work_order.name,
            "stock_entry": manufacture.name,
            "bundles": bundles,
            "entries": _submitted_bundle_entries(bundles[0]),
        }
    finally:
        frappe.set_user(previous_user)


def _procurement_user_smoke(context: dict[str, Any]) -> dict[str, Any]:
    previous_user = frappe.session.user
    try:
        frappe.set_user(PROCUREMENT_USER)
        price = frappe.get_doc(
            {
                "doctype": "Item Price",
                "item_code": context["raw_item"],
                "uom": "Nos",
                "price_list": "Standard Buying",
                "buying": 1,
                "currency": "USD",
                "price_list_rate": 7.25,
            }
        )
        price.insert()
        price.price_list_rate = 8.5
        price.save()
        purchase_orders = frappe.get_list("Purchase Order", fields=["name"], limit_page_length=1)
        return {
            "item_price": price.name,
            "purchase_order_list_rows": len(purchase_orders),
            "purchase_order_sample": purchase_orders[0].name if purchase_orders else None,
        }
    finally:
        frappe.set_user(previous_user)


def _prepare_context() -> dict[str, Any]:
    frappe.set_user("Administrator")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    company = _first_value("Company")
    stock_warehouse = "Spare Parts (InductOne) - POR"
    if not frappe.db.exists("Warehouse", stock_warehouse):
        stock_warehouse = _first_value("Warehouse", {"is_group": 0, "disabled": 0})
    fg_warehouse = "Gripper Inventory - POR"
    if not frappe.db.exists("Warehouse", fg_warehouse):
        fg_warehouse = stock_warehouse
    wip_warehouse = "Gripper In-Progress Inventory - POR"
    if not frappe.db.exists("Warehouse", wip_warehouse):
        wip_warehouse = stock_warehouse

    item_group = "Spares" if frappe.db.exists("Item Group", "Spares") else _first_value("Item Group")
    raw_item = _insert_item(
        f"PERM-SMOKE-RAW-{stamp}",
        item_group=item_group,
        warehouse=stock_warehouse,
        company=company,
    )
    tracked_item = _insert_item(
        f"PERM-SMOKE-TRACKED-{stamp}",
        item_group=item_group,
        warehouse=stock_warehouse,
        company=company,
        tracked=True,
    )
    gripper_item = _insert_item(
        f"PERM-SMOKE-GRIPPER-{stamp}",
        item_group=item_group,
        warehouse=fg_warehouse,
        company=company,
        tracked=True,
    )

    bom = frappe.get_doc(
        {
            "doctype": "BOM",
            "item": gripper_item,
            "company": company,
            "currency": "USD",
            "conversion_rate": 1,
            "quantity": 1,
            "is_active": 1,
            "is_default": 1,
            "items": [
                {
                    "item_code": raw_item,
                    "qty": 1,
                    "uom": "Nos",
                    "stock_uom": "Nos",
                    "conversion_factor": 1,
                    "rate": 1,
                    "source_warehouse": stock_warehouse,
                }
            ],
        }
    )
    bom.insert(ignore_permissions=True)
    bom.submit()

    # Seed raw stock as Administrator so the gripper role test only evaluates
    # Work Order + Manufacture permissions, not inventory-receipt permissions.
    raw_receipt = _make_stock_entry(
        stock_entry_type="Material Receipt",
        company=company,
        items=[
            {
                "item_code": raw_item,
                "qty": 2,
                "t_warehouse": stock_warehouse,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1,
                "basic_rate": 1,
                "allow_zero_valuation_rate": 1,
            }
        ],
    )
    raw_receipt.insert(ignore_permissions=True)
    raw_receipt.submit()

    _ensure_exact_role_user(OPERATIONS_MANAGER_USER, ["Operations Manager"])

    return {
        "company": company,
        "stock_warehouse": stock_warehouse,
        "fg_warehouse": fg_warehouse,
        "wip_warehouse": wip_warehouse,
        "customer": _first_value("Customer"),
        "raw_item": raw_item,
        "tracked_item": tracked_item,
        "gripper_item": gripper_item,
        "bom": bom.name,
        "raw_receipt": raw_receipt.name,
    }


def run(site: str, sites_path: str, evidence_dir: str) -> int:
    global frappe
    import frappe as frappe_module

    frappe = frappe_module
    frappe.init(site=site, sites_path=sites_path)
    frappe.connect()

    results: list[dict[str, Any]] = []
    context: dict[str, Any] = {}
    try:
        context = _prepare_context()
        _record(results, "setup", True, "Synthetic candidate setup completed.", context=context)

        for label, fn in [
            ("inventory_operator_material_receipt", lambda: _inventory_operator_smoke(context)),
            ("operations_manager_sales_order_and_stock_issue", lambda: _operations_manager_smoke(context)),
            ("gripper_manufacturer_work_order_and_manufacture", lambda: _gripper_manufacturer_smoke(context)),
            ("procurement_user_item_price_and_po_view", lambda: _procurement_user_smoke(context)),
        ]:
            payload = _safe_call(fn)
            _record(
                results,
                label,
                bool(payload.pop("passed")),
                (
                    "Workflow executed without PermissionError."
                    if "exception" not in payload
                    else f"Workflow failed with {payload.get('exception')}."
                ),
                **payload,
            )
    finally:
        # Candidate-only smoke should leave no synthetic stock or master data.
        frappe.db.rollback()
        frappe.set_user("Administrator")
        frappe.destroy()

    passed_count = sum(1 for row in results if row["passed"])
    failed_count = len(results) - passed_count
    payload = {
        "site": site,
        "sites_path": sites_path,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "context": context,
        "summary": {"total": len(results), "passed": passed_count, "failed": failed_count},
        "results": results,
    }
    evidence_path = (
        Path(evidence_dir)
        / f"transaction_role_stock_dependency_smoke_{_timestamp()}.json"
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")

    print(f"SUMMARY {passed_count}/{len(results)} passed; evidence={evidence_path}")
    return 0 if failed_count == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--evidence-dir", default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()
    return run(args.site, args.sites_path, args.evidence_dir)


if __name__ == "__main__":
    sys.exit(main())
