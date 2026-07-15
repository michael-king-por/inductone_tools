#!/usr/bin/env python3
"""Generate read-only release evidence for InductOne Configuration Options.

The output is intended for Engineering Change review: it records each option's
released state, approved Engineering Signoff, mapping rows, and the concrete
target/replacement BOM/Item records those mappings reference. It does not create
snapshots or mutate ERPNext.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frappe


OPTION_DOCTYPE = "InductOne Configuration Option"
SIGNOFF_DOCTYPE = "Engineering Signoff"

OPTION_FIELDS = [
    "name",
    "option_code",
    "option_name",
    "option_category",
    "option_group",
    "option_group_required",
    "is_default_selection",
    "is_active",
    "sort_order",
    "status",
    "mapping_status",
    "effective_date",
    "deprecated_date",
    "owner_role",
    "requires_ops_approval",
    "builder_description",
    "internal_notes",
    "modified",
    "modified_by",
]

MAPPING_FIELDS = [
    "idx",
    "action",
    "target_item",
    "replace_with_item",
    "replace_scope",
    "replace_count",
    "replace_with_bom",
    "structural_effect_mode",
    "preserve_target_item_identity",
    "expand_mode",
    "target_bom",
    "qty_source",
    "qty_fixed",
    "parameter_key",
    "required_for_release",
    "row_order",
]

SIGNOFF_FIELDS = [
    "name",
    "target_doctype",
    "target_docname",
    "target_description",
    "target_revision_id",
    "is_current",
    "status",
    "notes",
    "requested_at",
    "requested_by",
    "reviewed_at",
    "reviewed_by",
    "modified",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--evidence-dir", default="/tmp")
    parser.add_argument(
        "--option",
        action="append",
        required=True,
        help="Option code/name to include. Repeat for each option.",
    )
    parser.add_argument(
        "--expected-signoff",
        action="append",
        default=[],
        help="Expected CODE=SIGNOFF mapping. Repeat for each known signoff.",
    )
    return parser.parse_args()


def _clean(value: Any) -> Any:
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return value


def _row_dict(row: Any, fields: list[str]) -> dict[str, Any]:
    return {field: _clean(getattr(row, field, None)) for field in fields}


def _expected_signoff_map(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"--expected-signoff must be CODE=SIGNOFF, got {value!r}")
        code, signoff = value.split("=", 1)
        result[code.strip()] = signoff.strip()
    return result


def _find_option(option_code_or_name: str):
    name = frappe.db.get_value(OPTION_DOCTYPE, {"option_code": option_code_or_name}, "name")
    if not name and frappe.db.exists(OPTION_DOCTYPE, option_code_or_name):
        name = option_code_or_name
    if not name:
        return None
    return frappe.get_doc(OPTION_DOCTYPE, name)


def _item_summary(item_code: str | None) -> dict[str, Any] | None:
    if not item_code:
        return None
    if not frappe.db.exists("Item", item_code):
        return {"name": item_code, "exists": False}
    fields = [
        "name",
        "item_name",
        "item_group",
        "stock_uom",
        "disabled",
        "is_stock_item",
        "has_serial_no",
        "has_batch_no",
        "default_bom",
        "modified",
    ]
    data = frappe.db.get_value("Item", item_code, fields, as_dict=True) or {}
    data["exists"] = True
    return dict(data)


def _bom_summary(bom_name: str | None) -> dict[str, Any] | None:
    if not bom_name:
        return None
    if not frappe.db.exists("BOM", bom_name):
        return {"name": bom_name, "exists": False}
    fields = [
        "name",
        "item",
        "item_name",
        "quantity",
        "uom",
        "is_active",
        "is_default",
        "docstatus",
        "modified",
    ]
    data = frappe.db.get_value("BOM", bom_name, fields, as_dict=True) or {}
    data = dict(data)
    data["exists"] = True
    data["item_summary"] = _item_summary(data.get("item"))
    data["bom_item_count"] = frappe.db.count("BOM Item", {"parent": bom_name})
    return data


def _bom_item_occurrences(*, target_item: str | None = None, target_bom: str | None = None) -> list[dict[str, Any]]:
    filters = {}
    if target_item:
        filters["item_code"] = target_item
    if target_bom:
        filters["bom_no"] = target_bom
    if not filters:
        return []
    rows = frappe.get_all(
        "BOM Item",
        filters=filters,
        fields=[
            "parent",
            "idx",
            "item_code",
            "item_name",
            "qty",
            "uom",
            "bom_no",
            "custom_balloon_numbers",
            "custom_electrical_unit",
            "custom_source_electrical_bom_rev",
        ],
        limit_page_length=100,
        order_by="parent asc, idx asc",
    )
    return [dict(row) for row in rows]


def _signoffs_for(option_name: str, option_code: str | None = None) -> list[dict[str, Any]]:
    target_names = [option_name]
    if option_code and option_code not in target_names:
        target_names.append(option_code)
    rows = frappe.get_all(
        SIGNOFF_DOCTYPE,
        filters={"target_doctype": OPTION_DOCTYPE, "target_docname": ["in", target_names]},
        fields=SIGNOFF_FIELDS,
        limit_page_length=0,
        order_by="creation asc",
    )
    return [dict(row) for row in rows]


def _mapping_summary(mapping: dict[str, Any]) -> str:
    action = mapping.get("action")
    target_item = mapping.get("target_item")
    target_bom = mapping.get("target_bom")
    replacement = mapping.get("replace_with_item") or mapping.get("replace_with_bom")
    qty = mapping.get("qty_fixed")
    mode = mapping.get("structural_effect_mode")

    if action == "ADD":
        target = target_bom or target_item
        return f"ADD {target} ({mode})"
    if action == "REMOVE":
        target = target_bom or target_item
        return f"REMOVE {target} ({mode})"
    if action in {"REPLACE", "REPLACE_TARGET_NODE"}:
        return f"{action} {target_item or target_bom} -> {replacement} ({mode})"
    if action == "QTY_OVERRIDE":
        return f"QTY_OVERRIDE {target_item or target_bom} -> {qty}"
    return f"{action or 'UNKNOWN'} target={target_item or target_bom or '-'}"


def _evidence_for_option(option_code_or_name: str, expected_signoffs: dict[str, str]) -> dict[str, Any]:
    doc = _find_option(option_code_or_name)
    if not doc:
        return {
            "input": option_code_or_name,
            "found": False,
            "status": "MISSING",
            "checks": [{"name": "option exists", "pass": False}],
        }

    option = {field: _clean(getattr(doc, field, None)) for field in OPTION_FIELDS}
    mappings = []
    for child in doc.get("mappings_table") or []:
        mapping = _row_dict(child, MAPPING_FIELDS)
        mapping["summary"] = _mapping_summary(mapping)
        mapping["target_item_summary"] = _item_summary(mapping.get("target_item"))
        mapping["replace_with_item_summary"] = _item_summary(mapping.get("replace_with_item"))
        mapping["target_bom_summary"] = _bom_summary(mapping.get("target_bom"))
        mapping["replace_with_bom_summary"] = _bom_summary(mapping.get("replace_with_bom"))
        mapping["target_item_occurrences"] = _bom_item_occurrences(target_item=mapping.get("target_item"))
        mapping["target_bom_occurrences"] = _bom_item_occurrences(target_bom=mapping.get("target_bom"))
        mappings.append(mapping)

    signoffs = _signoffs_for(doc.name, doc.option_code)
    expected_signoff = expected_signoffs.get(doc.option_code) or expected_signoffs.get(doc.name)
    approved_current_signoffs = [
        row for row in signoffs if row.get("status") == "Approved" and int(row.get("is_current") or 0)
    ]

    checks = [
        {"name": "option exists", "pass": True},
        {"name": "option is active", "pass": bool(option.get("is_active"))},
        {"name": "option status is Released", "pass": option.get("status") == "Released", "actual": option.get("status")},
        {
            "name": "mapping status is Complete",
            "pass": option.get("mapping_status") == "Complete",
            "actual": option.get("mapping_status"),
        },
        {"name": "has mapping rows", "pass": bool(mappings), "count": len(mappings)},
        {
            "name": "has current approved signoff",
            "pass": bool(approved_current_signoffs),
            "approved_current_signoffs": [row["name"] for row in approved_current_signoffs],
        },
    ]
    if expected_signoff:
        checks.append(
            {
                "name": "expected signoff found",
                "pass": any(row["name"] == expected_signoff for row in signoffs),
                "expected": expected_signoff,
            }
        )
        checks.append(
            {
                "name": "expected signoff approved/current",
                "pass": any(
                    row["name"] == expected_signoff
                    and row.get("status") == "Approved"
                    and int(row.get("is_current") or 0)
                    for row in signoffs
                ),
                "expected": expected_signoff,
            }
        )

    return {
        "input": option_code_or_name,
        "found": True,
        "option": option,
        "expected_signoff": expected_signoff,
        "signoffs": signoffs,
        "mappings": mappings,
        "effect_summary": [mapping["summary"] for mapping in mappings],
        "checks": checks,
        "pass": all(check["pass"] for check in checks),
    }


def run(args: argparse.Namespace) -> int:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_dir = Path(args.evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / f"configuration_option_release_evidence_{timestamp}.json"

    expected_signoffs = _expected_signoff_map(args.expected_signoff)

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        options = [_evidence_for_option(option, expected_signoffs) for option in args.option]
        payload = {
            "site": args.site,
            "generated_at_utc": timestamp,
            "requested_options": args.option,
            "evidence_type": "InductOne Configuration Option release evidence",
            "options": options,
            "summary": {
                "total": len(options),
                "pass": sum(1 for option in options if option.get("pass")),
                "fail": sum(1 for option in options if not option.get("pass")),
                "missing": sum(1 for option in options if not option.get("found")),
            },
        }
        evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    finally:
        frappe.destroy()

    print(f"Evidence: {evidence_path}")
    print(json.dumps(payload["summary"], indent=2))
    for option in payload["options"]:
        code = option.get("option", {}).get("option_code") or option.get("input")
        print(("PASS" if option.get("pass") else "FAIL"), code)
        for check in option.get("checks", []):
            print("  ", "PASS" if check["pass"] else "FAIL", check["name"])
        for effect in option.get("effect_summary", []):
            print("    -", effect)

    return 0 if payload["summary"]["fail"] == 0 else 1


def main() -> int:
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
