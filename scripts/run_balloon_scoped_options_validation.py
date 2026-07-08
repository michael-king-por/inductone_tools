#!/usr/bin/env python3
"""Candidate validation for balloon-scoped electrical options.

This script intentionally runs only on a non-production candidate site. It
creates synthetic Configured BOM Snapshots for the reviewed option matrix,
resolves them through ``bom_export.build_configured_rows``, materializes the
snapshot hierarchy/workbook, and writes JSON evidence.
"""

from __future__ import annotations

import argparse
import json
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


DEFAULT_EVIDENCE_DIR = Path("/mnt/c/hub/frappe-sandbox/validation-evidence")
DEFAULT_BUILD = "SAL-ORD-2026-00054-BLD-0225"
EXPECTED_SCRIPT_LENGTH_BEFORE_BRANCH = 63230


@dataclass(frozen=True)
class MatrixCase:
    case_id: int
    label: str
    moved_options: tuple[str, ...]


MATRIX: tuple[MatrixCase, ...] = (
    MatrixCase(1, "baseline_only", ()),
    MatrixCase(2, "mcp", ("DEV-PANEL-MCP",)),
    MatrixCase(3, "ipc", ("DEV-PANEL-IPC",)),
    MatrixCase(4, "hmi", ("DEV-COMP-HMI",)),
    MatrixCase(5, "stack", ("DEV-COMP-STACK",)),
    MatrixCase(6, "fortress", ("DEV-COMP-FORTRESS",)),
    MatrixCase(7, "maglock", ("DEV-COMP-MAGLOCK",)),
    MatrixCase(8, "mcp_ipc", ("DEV-PANEL-MCP", "DEV-PANEL-IPC")),
    MatrixCase(9, "mcp_fortress", ("DEV-PANEL-MCP", "DEV-COMP-FORTRESS")),
    MatrixCase(10, "ipc_hmi", ("DEV-PANEL-IPC", "DEV-COMP-HMI")),
    MatrixCase(11, "everything_moved", ("DEV-PANEL-MCP", "DEV-PANEL-IPC", "DEV-COMP-HMI", "DEV-COMP-STACK", "DEV-COMP-FORTRESS", "DEV-COMP-MAGLOCK")),
    MatrixCase(12, "ipc_maglock", ("DEV-PANEL-IPC", "DEV-COMP-MAGLOCK")),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--build", default=DEFAULT_BUILD)
    parser.add_argument("--load-options", action="store_true", help="Upsert the reviewed option catalog before validation.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = args.evidence_dir / f"balloon_scoped_options_validation_{timestamp}.json"

    import frappe
    from inductone_tools.balloon_scoped_options import (
        COLLISION_REFERENCE_BOM,
        EXTENSIONS,
        MASTER_ELECTRICAL_BOM,
        SUBSTITUTIONS,
        catalog_specs,
        expected_resolution,
        upsert_catalog,
    )
    from inductone_tools.bom_export import build_configured_rows, explode_bom_tree_structured
    from inductone_tools.snapshot.hierarchy import generate_hierarchy_workbook, populate_snapshot_hierarchy

    payload: dict = {
        "site": args.site,
        "build": args.build,
        "generated_at_utc": timestamp,
        "preconditions": {},
        "option_loader": None,
        "cases": [],
    }
    failures: list[str] = []

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        if args.load_options:
            payload["option_loader"] = upsert_catalog(frappe)

        preconditions = run_preconditions(frappe, args.build, MASTER_ELECTRICAL_BOM, COLLISION_REFERENCE_BOM)
        payload["preconditions"] = preconditions
        for check in preconditions["checks"]:
            print(("PASS" if check["passed"] else "FAIL"), check["label"], check.get("details", ""))
            if not check["passed"]:
                failures.append(f"precondition:{check['label']}")

        if failures:
            payload["failures"] = failures
            evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            return 1

        build = frappe.get_doc("InductOne Build", args.build)
        baseline_rows = explode_bom_tree_structured(
            root_bom=build.top_bom,
            explosion_mode="Follow Explicit Child BOM Links",
            include_qty=True,
        )

        for case in MATRIX:
            case_result = run_case(
                frappe=frappe,
                case=case,
                build=build,
                baseline_rows=baseline_rows,
                catalog_specs=catalog_specs(),
                expected_resolution=expected_resolution,
                build_configured_rows=build_configured_rows,
                populate_snapshot_hierarchy=populate_snapshot_hierarchy,
                generate_hierarchy_workbook=generate_hierarchy_workbook,
            )
            payload["cases"].append(case_result)
            status = "PASS" if case_result["passed"] else "FAIL"
            print(status, f"case {case.case_id} {case.label}", case_result.get("summary", ""))
            if not case_result["passed"]:
                failures.append(f"case:{case.case_id}:{case.label}")

        payload["failures"] = failures
        evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    finally:
        frappe.destroy()

    print(f"Evidence: {evidence_path}")
    return 1 if failures else 0


def run_preconditions(frappe, build_name: str, master_bom: str, collision_bom: str) -> dict:
    from inductone_tools.balloon_scoped_options import EXTENSIONS, SUBSTITUTIONS

    checks = []
    build_exists = frappe.db.exists("InductOne Build", build_name)
    checks.append({"label": "BLD-0225 exists", "passed": bool(build_exists), "details": build_name})

    bom = frappe.db.get_value("BOM", master_bom, ["docstatus", "is_active"], as_dict=True)
    checks.append({
        "label": "REV E master active submitted",
        "passed": bool(bom and int(bom.docstatus or 0) == 1 and int(bom.is_active or 0) == 1),
        "details": bom,
    })

    configurable_rows = []
    for sub in SUBSTITUTIONS:
        configurable_rows.append((sub.balloon, sub.standard_item))
        configurable_rows.extend((sub.balloon, item) for item in sub.option_items)
    configurable_rows.extend((ext.balloon, ext.item) for ext in EXTENSIONS)
    found = 0
    missing = []
    for balloon, item in configurable_rows:
        exists = frappe.db.exists(
            "BOM Item",
            {"parent": master_bom, "custom_balloon_numbers": balloon, "item_code": item},
        )
        if exists:
            found += 1
        else:
            missing.append({"balloon": balloon, "item_code": item})
    checks.append({
        "label": "REV E configurable balloon fingerprint",
        "passed": found == 26 and not missing,
        "details": {"found": found, "expected": 26, "missing": missing},
    })

    collision = frappe.get_all(
        "BOM Item",
        filters={"parent": collision_bom, "custom_balloon_numbers": "315", "item_code": "1417891"},
        fields=["name", "idx", "qty"],
    )
    checks.append({
        "label": "0921 fixed 1417891 balloon 315 present",
        "passed": len(collision) == 1 and float(collision[0].qty or 0) == 3.0,
        "details": collision,
    })

    script_len = frappe.db.get_value("Client Script", "InductOne Build Script", "script")
    script_len = len(script_len or "")
    checks.append({
        "label": "InductOne Build Script has balloon carry-through",
        "passed": script_len >= EXPECTED_SCRIPT_LENGTH_BEFORE_BRANCH,
        "details": {"length": script_len, "pre_branch_length": EXPECTED_SCRIPT_LENGTH_BEFORE_BRANCH},
    })

    field_rows = frappe.get_all(
        "Custom Field",
        filters={"fieldname": "target_balloon", "dt": ["in", ["InductOne Configuration Option Mapping", "Configured BOM Snapshot Structural Effect"]]},
        fields=["name", "dt", "insert_after"],
    )
    checks.append({
        "label": "target_balloon fields fixture-managed on candidate",
        "passed": len(field_rows) == 2,
        "details": field_rows,
    })

    return {"checks": checks}


def run_case(
    frappe,
    case: MatrixCase,
    build,
    baseline_rows: list[dict],
    catalog_specs: list[dict],
    expected_resolution,
    build_configured_rows,
    populate_snapshot_hierarchy,
    generate_hierarchy_workbook,
) -> dict:
    result = {
        "case_id": case.case_id,
        "label": case.label,
        "moved_options": list(case.moved_options),
        "checks": [],
        "passed": False,
    }
    try:
        selected_codes = ["DEV-BASELINE", *case.moved_options]
        structural_effects = structural_effects_for(selected_codes, catalog_specs)
        snap = create_validation_snapshot(frappe, build, baseline_rows, structural_effects, case)
        pkg = SimpleNamespace(
            inductone_build=build.name,
            configured_snapshot=snap.name,
            bom=build.top_bom,
            explosion_mode="Follow Explicit Child BOM Links",
            max_depth=None,
            include_qty=1,
            preserve_duplicate_occurrences=1,
        )
        rows = build_configured_rows(pkg)
        expected = expected_resolution(selected_codes, frappe)

        add_check(result, "snapshot_effects_carry_target_balloon", assert_effects_have_balloons(snap, structural_effects))
        add_check(result, "resolved_balloons_match_oracle", assert_balloon_rows(rows, expected["by_balloon"]))
        add_check(result, "collision_flat_quantities_match_oracle", assert_collision_flat(rows, expected["flat"]))

        hierarchy_result = populate_snapshot_hierarchy(snap.name)
        add_check(result, "hierarchy_populated", bool(hierarchy_result and hierarchy_result.get("ok", True)), hierarchy_result)
        workbook_result = generate_hierarchy_workbook(snap.name)
        add_check(result, "hierarchy_workbook_generated", bool(workbook_result), workbook_result)

        result["snapshot"] = snap.name
        result["summary"] = f"{len(structural_effects)} effects; {len(rows)} resolved rows"
        result["passed"] = all(check["passed"] for check in result["checks"])
    except Exception as exc:  # noqa: BLE001 - evidence wants exact exception
        result["exception"] = {
            "type": exc.__class__.__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        result["passed"] = False
    return result


def structural_effects_for(selected_codes: list[str], catalog_specs: list[dict]) -> list[dict]:
    specs = {spec["option_code"]: spec for spec in catalog_specs}
    effects = []
    for code in selected_codes:
        for mapping in specs[code]["mappings_table"]:
            effect_mode = mapping.get("structural_effect_mode") or "NO_STRUCTURAL_CHANGE"
            if effect_mode == "AUTO":
                action = mapping.get("action") or ""
                expand_mode = mapping.get("expand_mode") or "AS_ITEM_ONLY"
                if action == "REPLACE" and expand_mode == "AS_ITEM_ONLY":
                    effect_mode = "REPLACE_TARGET_NODE"
                elif action == "REPLACE":
                    effect_mode = "REPLACE_TARGET_BRANCH"
                elif action == "REMOVE" and expand_mode == "AS_ITEM_ONLY":
                    effect_mode = "SUPPRESS_TARGET_NODE"
                elif action == "REMOVE":
                    effect_mode = "SUPPRESS_TARGET_BRANCH"
                elif action == "ADD" and expand_mode == "AS_ITEM_ONLY":
                    effect_mode = "INCREMENT_NODE_QTY"
                elif action == "ADD":
                    effect_mode = "ADD_BRANCH"
                elif action == "QTY_OVERRIDE":
                    effect_mode = "OVERRIDE_NODE_QTY"
            effects.append({
                "action": mapping.get("action") or "",
                "effect_mode": effect_mode,
                "effect_qty": float(mapping.get("qty_fixed") or 1),
                "target_item": mapping.get("target_item") or "",
                "target_balloon": mapping.get("target_balloon") or "",
                "target_bom": mapping.get("target_bom") or "",
                "resolved_target_bom": "",
                "replace_with_item": mapping.get("replace_with_item") or "",
                "replace_scope": mapping.get("replace_scope") or "ALL_OCCURRENCES",
                "replace_count": int(mapping.get("replace_count") or 1),
                "replace_with_bom": mapping.get("replace_with_bom") or "",
                "resolved_replace_with_bom": "",
                "source_option_code": code,
                "expand_mode": mapping.get("expand_mode") or "AS_ITEM_ONLY",
                "row_order": int(mapping.get("row_order") or 100),
                "reason": f"Balloon validation effect from {code}",
            })
    return effects


def create_validation_snapshot(frappe, build, baseline_rows: list[dict], structural_effects: list[dict], case: MatrixCase):
    leaf_codes = sorted({row.get("item_code") for row in baseline_rows if row.get("is_leaf") and row.get("item_code")})
    doc = frappe.get_doc({
        "doctype": "Configured BOM Snapshot",
        "sales_order": build.sales_order,
        "inductone_build": build.name,
        "top_item": build.top_item,
        "top_bom": build.top_bom,
        "orientation": build.orientation,
        "snapshot_rev": 9000 + case.case_id,
        "generated_at": frappe.utils.now_datetime(),
        "lines": [
            {
                "item_code": item_code,
                "qty": 1,
                "included": 1,
                "rule_reason": "Validation baseline include set",
            }
            for item_code in leaf_codes
        ],
        "structural_effects": structural_effects,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc


def assert_effects_have_balloons(snap, structural_effects: list[dict]) -> tuple[bool, dict]:
    expected = sorted(
        (e["source_option_code"], e["action"], e["target_item"], e["target_balloon"])
        for e in structural_effects
        if e.get("target_balloon")
    )
    actual = sorted(
        (row.source_option_code, row.action, row.target_item, getattr(row, "target_balloon", "") or "")
        for row in snap.structural_effects
        if getattr(row, "target_balloon", "") or ""
    )
    return expected == actual, {"expected": expected, "actual": actual}


def assert_balloon_rows(rows: list[dict], expected_by_balloon: dict[str, list[dict]]) -> tuple[bool, dict]:
    from inductone_tools.balloon_scoped_options import EXTENSIONS, SUBSTITUTIONS

    managed_items_by_balloon: dict[str, set[str]] = {}
    for sub in SUBSTITUTIONS:
        managed_items_by_balloon.setdefault(sub.balloon, set()).add(sub.standard_item)
        managed_items_by_balloon[sub.balloon].update(sub.option_items)
    for ext in EXTENSIONS:
        managed_items_by_balloon.setdefault(ext.balloon, set()).add(ext.item)

    failures = []
    observed = {}
    leaf_rows = [row for row in rows if row.get("is_leaf")]
    for balloon, expected_rows in expected_by_balloon.items():
        managed_items = managed_items_by_balloon.get(balloon, set())
        actual_rows = [
            {"item_code": row.get("item_code"), "qty": float(row.get("qty") or 0)}
            for row in leaf_rows
            if (row.get("balloon_numbers") or "").strip() == balloon
            and row.get("item_code") in managed_items
        ]
        actual_rows = sorted(actual_rows, key=lambda r: (r["item_code"], r["qty"]))
        expected_sorted = sorted(
            [{"item_code": row["item_code"], "qty": float(row["qty"] or 0)} for row in expected_rows],
            key=lambda r: (r["item_code"], r["qty"]),
        )
        observed[balloon] = actual_rows
        if actual_rows != expected_sorted:
            failures.append({"balloon": balloon, "expected": expected_sorted, "actual": actual_rows})
    return not failures, {"failures": failures, "observed": observed}


def assert_collision_flat(rows: list[dict], expected_flat: dict[str, float]) -> tuple[bool, dict]:
    collision_items = ["11283", "11245", "11351", "1417902", "1417903", "1417891", "1417892"]
    actual = {}
    for row in rows:
        if not row.get("is_leaf"):
            continue
        item = row.get("item_code")
        if item in collision_items:
            actual[item] = actual.get(item, 0.0) + float(row.get("qty") or 0)
    expected = {item: float(expected_flat.get(item, 0.0)) for item in collision_items if expected_flat.get(item, 0.0)}
    # Keep zero-expected items explicit if they appear in actual output.
    for item in actual:
        expected.setdefault(item, 0.0)
    failures = {
        item: {"expected": expected.get(item, 0.0), "actual": actual.get(item, 0.0)}
        for item in sorted(set(expected) | set(actual))
        if abs(float(expected.get(item, 0.0)) - float(actual.get(item, 0.0))) > 1e-9
    }
    return not failures, {"expected": expected, "actual": actual, "failures": failures}


def add_check(result: dict, label: str, outcome, details=None) -> None:
    if isinstance(outcome, tuple):
        passed, tuple_details = outcome
        details = tuple_details
    else:
        passed = bool(outcome)
    result["checks"].append({"label": label, "passed": bool(passed), "details": details})


if __name__ == "__main__":
    raise SystemExit(main())
