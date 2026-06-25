#!/usr/bin/env python3
"""Candidate workflow transition permission smoke test.

This test verifies that the intended internal operator persona can reach the
release and acceptance server actions after the role hardening.  The synthetic
records are deliberately minimal; the actions may still stop on business/domain
preconditions, but they must not stop on permissions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import frappe


EVIDENCE_DIR = "/mnt/c/hub/frappe-sandbox/validation-evidence"
TEST_USER = "christina.gt@plusonerobotics.com"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _exception_payload(exc: BaseException | None) -> dict[str, Any] | None:
    if exc is None:
        return None
    return {
        "class": exc.__class__.__name__,
        "module": exc.__class__.__module__,
        "message": str(exc),
    }


def _is_domain_error(exc: BaseException) -> bool:
    """Domain errors are acceptable for this smoke; permission errors are not."""
    if isinstance(exc, frappe.PermissionError):
        return False
    return exc.__class__.__module__.startswith("frappe") or isinstance(exc, frappe.ValidationError)


def _record_step(results: list[dict[str, Any]], step: str, passed: bool, detail: str, exc: BaseException | None = None, **extra: Any) -> None:
    status = "PASS" if passed else "FAIL"
    exc_name = exc.__class__.__name__ if exc else "NO_EXCEPTION"
    print(f"{status} {step}: {detail} ({exc_name})")
    row = {
        "step": step,
        "passed": passed,
        "detail": detail,
        "exception": _exception_payload(exc),
    }
    row.update(extra)
    results.append(row)


def _one_value(doctype: str, filters: dict[str, Any], fieldname: str = "name") -> Any:
    value = frappe.db.get_value(doctype, filters, fieldname)
    if not value:
        frappe.throw(f"Required fixture lookup failed for {doctype}: {filters}")
    return value


def _lookup_seed_data() -> dict[str, Any]:
    bom = frappe.db.sql(
        """
        select name, item
        from `tabBOM`
        where docstatus = 1 and ifnull(is_active, 0) = 1
        order by modified desc
        limit 1
        """,
        as_dict=True,
    )
    if not bom:
        frappe.throw("No submitted active BOM found for workflow smoke seed data.")

    so_item = frappe.db.sql(
        """
        select soi.parent as sales_order, soi.idx as sales_order_item_idx
        from `tabSales Order Item` soi
        inner join `tabSales Order` so on so.name = soi.parent
        where so.docstatus < 2
        order by so.modified desc, soi.idx asc
        limit 1
        """,
        as_dict=True,
    )
    if not so_item:
        frappe.throw("No Sales Order Item found for workflow smoke seed data.")

    supplier = (
        frappe.db.get_value("Supplier", {"supplier_name": "Motion Controls"}, "name")
        or frappe.db.get_value("Supplier", {"name": "Motion Controls"}, "name")
        or _one_value("Supplier", {}, "name")
    )

    return {
        "sales_order": so_item[0].sales_order,
        "sales_order_item_idx": so_item[0].sales_order_item_idx,
        "top_item": bom[0].item,
        "top_bom": bom[0].name,
        "builder_supplier": supplier,
    }


def _cleanup(created: dict[str, str | None]) -> None:
    frappe.db.rollback()
    frappe.set_user("Administrator")
    for doctype, key in [
        ("InductOne Build Completion", "completion"),
        ("InductOne Configuration Order", "configuration_order"),
        ("InductOne Build", "build"),
    ]:
        name = created.get(key)
        if name and frappe.db.exists(doctype, name):
            frappe.delete_doc(doctype, name, force=1, ignore_permissions=True)
    frappe.db.commit()


def run(site: str, sites_path: str) -> int:
    frappe.init(site=site, sites_path=sites_path)
    frappe.connect()

    from inductone_tools.builder_release import release_to_builder_now
    from inductone_tools.build_completion_accept import accept_completion_create_as_built

    results: list[dict[str, Any]] = []
    created: dict[str, str | None] = {"build": None, "configuration_order": None, "completion": None}
    seed_data: dict[str, Any] = {}

    try:
        frappe.set_user(TEST_USER)
        frappe.session.user = TEST_USER

        try:
            seed_data = _lookup_seed_data()
            _record_step(results, "lookup_seed_data", True, "Found existing Sales Order, BOM, Item, and Supplier seed data.", seed_data=seed_data)
        except BaseException as exc:  # noqa: BLE001
            _record_step(results, "lookup_seed_data", False, "Could not locate seed data for synthetic workflow records.", exc)
            raise

        try:
            build = frappe.new_doc("InductOne Build")
            build.sales_order = seed_data["sales_order"]
            build.sales_order_item_idx = seed_data["sales_order_item_idx"]
            build.top_item = seed_data["top_item"]
            build.top_bom = seed_data["top_bom"]
            build.orientation = "Right-Hand"
            build.builder_supplier = seed_data["builder_supplier"]
            build.build_status = "DRAFT"
            build.insert()
            created["build"] = build.name
            _record_step(results, "create_inductone_build", True, "Created minimal synthetic InductOne Build.", name=build.name)
        except BaseException as exc:  # noqa: BLE001
            _record_step(results, "create_inductone_build", False, "Synthetic InductOne Build creation failed.", exc)
            raise

        try:
            co = frappe.new_doc("InductOne Configuration Order")
            co.inductone_build = created["build"]
            co.co_status = "Draft"
            co.config_order_rev = 1
            co.generated_at = frappe.utils.now_datetime()
            co.generated_by = TEST_USER
            co.builder_supplier = seed_data["builder_supplier"]
            co.sales_order = seed_data["sales_order"]
            co.sales_order_item_idx = seed_data["sales_order_item_idx"]
            co.top_item = seed_data["top_item"]
            co.top_bom = seed_data["top_bom"]
            co.orientation = "Right-Hand"
            co.insert()
            created["configuration_order"] = co.name

            build = frappe.get_doc("InductOne Build", created["build"])
            build.latest_config_order = co.name
            build.config_order_rev = 1
            build.save()
            _record_step(results, "create_configuration_order", True, "Created minimal linked Configuration Order.", name=co.name)
        except BaseException as exc:  # noqa: BLE001
            _record_step(results, "create_configuration_order", False, "Synthetic Configuration Order creation/linking failed.", exc)
            raise

        try:
            release_to_builder_now(created["build"])
            _record_step(results, "release_to_builder_now", True, "Action reached and completed without permission denial.", build=created["build"])
        except BaseException as exc:  # noqa: BLE001
            passed = _is_domain_error(exc)
            detail = "Action reached domain validation without permission denial." if passed else "Action failed with a non-domain or permission error."
            _record_step(results, "release_to_builder_now", passed, detail, exc, build=created["build"])

        try:
            completion = frappe.new_doc("InductOne Build Completion")
            completion.inductone_build = created["build"]
            completion.configuration_order = created["configuration_order"]
            completion.builder_supplier = seed_data["builder_supplier"]
            completion.status = "Submitted"
            completion.insert()
            created["completion"] = completion.name
            _record_step(results, "create_build_completion", True, "Created minimal linked Build Completion.", name=completion.name)
        except BaseException as exc:  # noqa: BLE001
            _record_step(results, "create_build_completion", False, "Synthetic Build Completion creation failed.", exc)
            raise

        try:
            accept_completion_create_as_built(created["completion"], as_built_notes="workflow transition smoke")
            _record_step(results, "accept_completion_create_as_built", True, "Action reached and completed without permission denial.", completion=created["completion"])
        except BaseException as exc:  # noqa: BLE001
            passed = _is_domain_error(exc)
            detail = "Action reached domain validation without permission denial." if passed else "Action failed with a non-domain or permission error."
            _record_step(results, "accept_completion_create_as_built", passed, detail, exc, completion=created["completion"])

    finally:
        _cleanup(created)

    passed = sum(1 for row in results if row["passed"])
    failed = len(results) - passed
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    evidence_path = os.path.join(EVIDENCE_DIR, f"workflow_transition_smoke_{_timestamp()}.json")
    payload = {
        "site": site,
        "sites_path": sites_path,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "test_user": TEST_USER,
        "created_records": created,
        "summary": {"total": len(results), "passed": passed, "failed": failed},
        "results": results,
    }
    with open(evidence_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)

    print(f"SUMMARY {passed}/{len(results)} passed; evidence={evidence_path}")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    args = parser.parse_args()

    try:
        return run(args.site, args.sites_path)
    finally:
        frappe.destroy()


if __name__ == "__main__":
    sys.exit(main())
