#!/usr/bin/env python3
"""Close-out static/logic checks for balloon-scoped options.

Checks:
1. Client Script fixture parity against HEAD production basis.
2. Custom Field fixture exact expected row set.
3. Candidate option group/default/exclusivity logic.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_EVIDENCE_DIR = Path("/mnt/c/hub/frappe-sandbox/validation-evidence")
CLIENT_SCRIPT_FIXTURE = Path("inductone_tools/fixtures/client_script.json")
CUSTOM_FIELD_FIXTURE = Path("inductone_tools/fixtures/custom_field.json")
CONFIGURATION_OPTION_FIXTURE = Path("inductone_tools/fixtures/inductone_configuration_option.json")

EXPECTED_CUSTOM_FIELDS = {
    "BOM Item-custom_orientation",
    "BOM Item-custom_option_tagging",
    "BOM Item-custom_balloon_numbers",
    "BOM Item-custom_electrical_unit",
    "BOM Item-custom_source_electrical_bom_rev",
    "BOM Item-custom_user_notes",
    "InductOne Configuration Option Mapping-target_balloon",
    "Configured BOM Snapshot Structural Effect-target_balloon",
}

EXPECTED_GROUPS = {
    "Electrical Cable Baseline": ["DEV-BASELINE"],
    "MCP Panel Position": ["DEV-PANEL-MCP-STD", "DEV-PANEL-MCP"],
    "IPC Panel Position": ["DEV-PANEL-IPC-STD", "DEV-PANEL-IPC"],
    "HMI Position": ["DEV-COMP-HMI-STD", "DEV-COMP-HMI"],
    "Stacklight Position": ["DEV-COMP-STACK-STD", "DEV-COMP-STACK"],
    "Fortress Position": ["DEV-COMP-FORTRESS-STD", "DEV-COMP-FORTRESS"],
    "Maglock Position": ["DEV-COMP-MAGLOCK-STD", "DEV-COMP-MAGLOCK"],
}

EXPECTED_DEFAULT_SELECTION = {
    "DEV-BASELINE",
    "DEV-PANEL-MCP-STD",
    "DEV-PANEL-IPC-STD",
    "DEV-COMP-HMI-STD",
    "DEV-COMP-STACK-STD",
    "DEV-COMP-FORTRESS-STD",
    "DEV-COMP-MAGLOCK-STD",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    return parser.parse_args()


def norm_script(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # Normalize trailing whitespace only.
    return "\n".join(line.rstrip() for line in lines).rstrip()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = args.evidence_dir / f"balloon_closeout_static_checks_{timestamp}.json"

    import frappe
    from inductone_tools.balloon_scoped_options import catalog_specs, expected_resolution

    payload = {
        "generated_at_utc": timestamp,
        "site": args.site,
        "repo_root": str(repo_root),
        "client_script_parity": run_client_script_parity(repo_root),
        "custom_field_fixture": run_custom_field_check(repo_root),
        "option_fixture_parity": None,
        "group_logic": None,
    }

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        payload["option_fixture_parity"] = run_option_fixture_parity(frappe, repo_root, catalog_specs)
        payload["group_logic"] = run_group_logic(frappe, expected_resolution)
    finally:
        frappe.destroy()

    verdicts = [
        payload["client_script_parity"]["passed"],
        payload["custom_field_fixture"]["passed"],
        payload["option_fixture_parity"]["passed"],
        payload["group_logic"]["passed"],
    ]
    payload["passed"] = all(verdicts)
    evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print("Client Script parity:", "PASS" if payload["client_script_parity"]["passed"] else "BLOCKER")
    for row in payload["client_script_parity"]["table"]:
        status = "identical" if row["identical"] else row["note"]
        print(f"  {row['script_name']}: {status}")
    print("Custom Field fixture:", "PASS" if payload["custom_field_fixture"]["passed"] else "BLOCKER")
    print("Option fixture parity:", "PASS" if payload["option_fixture_parity"]["passed"] else "BLOCKER")
    for row in payload["option_fixture_parity"]["table"]:
        print(f"  {row['option_code']}: {row['status']}")
    print("Group logic:", "PASS" if payload["group_logic"]["passed"] else "BLOCKER")
    print(f"Evidence: {evidence_path}")
    return 0 if payload["passed"] else 1


def run_client_script_parity(repo_root: Path) -> dict:
    basis_raw = subprocess.check_output(
        ["git", "show", "HEAD:inductone_tools/fixtures/client_script.json"],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
    )
    repo_raw = (repo_root / CLIENT_SCRIPT_FIXTURE).read_text(encoding="utf-8")
    basis_rows = json.loads(basis_raw)
    repo_rows = json.loads(repo_raw)
    basis = {row["name"]: row for row in basis_rows}
    repo = {row["name"]: row for row in repo_rows}

    table = []
    differing = []
    for name in sorted(set(basis) | set(repo)):
        in_basis = name in basis
        in_repo = name in repo
        identical = False
        note = ""
        if in_basis and in_repo:
            bscript = norm_script(basis[name].get("script") or "")
            rscript = norm_script(repo[name].get("script") or "")
            identical = bscript == rscript
            if not identical:
                differing.append(name)
                if name == "InductOne Build Script":
                    note = classify_inductone_build_script_diff(bscript, rscript)
                else:
                    note = "DRIFT: script body differs from production basis"
        elif in_basis:
            note = "BLOCKER: missing from repo fixture"
        else:
            note = "BLOCKER: extra in repo fixture"
        table.append({
            "script_name": name,
            "in_basis": in_basis,
            "in_repo": in_repo,
            "identical": identical,
            "note": note,
        })

    build_script_note = next(row for row in table if row["script_name"] == "InductOne Build Script")["note"]
    expected_diff_from_pre_addendum_basis = (
        differing == ["InductOne Build Script"]
        and build_script_note == "PASS: only W1/W2 target_balloon carry-through additions"
    )
    already_merged_into_basis = differing == []
    passed = set(basis) == set(repo) and (expected_diff_from_pre_addendum_basis or already_merged_into_basis)
    return {
        "basis": "git HEAD:inductone_tools/fixtures/client_script.json",
        "repo": str(CLIENT_SCRIPT_FIXTURE),
        "basis_count": len(basis_rows),
        "repo_count": len(repo_rows),
        "basis_not_repo": sorted(set(basis) - set(repo)),
        "repo_not_basis": sorted(set(repo) - set(basis)),
        "differing_scripts": differing,
        "table": table,
        "passed": passed,
    }


def classify_inductone_build_script_diff(basis_script: str, repo_script: str) -> str:
    mr = "          target_balloon: mr.target_balloon || '',"
    se = "      target_balloon: se.target_balloon || '',"
    if repo_script.count(mr) != 4 or repo_script.count(se) != 1:
        return f"BLOCKER: unexpected target_balloon counts mr={repo_script.count(mr)} se={repo_script.count(se)}"
    stripped = "\n".join(
        line for line in repo_script.split("\n")
        if line not in {mr, se}
    ).rstrip()
    if stripped == basis_script:
        return "PASS: only W1/W2 target_balloon carry-through additions"
    return "BLOCKER: InductOne Build Script differs beyond W1/W2 target_balloon additions"


def run_custom_field_check(repo_root: Path) -> dict:
    rows = json.loads((repo_root / CUSTOM_FIELD_FIXTURE).read_text(encoding="utf-8"))
    names = {row.get("name") for row in rows}
    bom_item = sorted(name for name in names if name and name.startswith("BOM Item-"))
    target_balloon = sorted(name for name in names if name and name.endswith("-target_balloon"))
    return {
        "count": len(rows),
        "names": sorted(names),
        "bom_item_count": len(bom_item),
        "target_balloon_rows": target_balloon,
        "missing_expected": sorted(EXPECTED_CUSTOM_FIELDS - names),
        "extra_unexpected": sorted(names - EXPECTED_CUSTOM_FIELDS),
        "passed": names == EXPECTED_CUSTOM_FIELDS and len(rows) == 8,
    }


def run_option_fixture_parity(frappe, repo_root: Path, catalog_specs) -> dict:
    fixture_path = repo_root / CONFIGURATION_OPTION_FIXTURE
    fixture_rows = json.loads(fixture_path.read_text(encoding="utf-8")) if fixture_path.exists() else []
    fixture = {row.get("option_code"): normalize_option(row) for row in fixture_rows}

    db_rows = frappe.get_all(
        "InductOne Configuration Option",
        filters={"option_code": ["like", "DEV-%"]},
        fields=["name", "option_code"],
        order_by="option_code asc",
    )
    db = {}
    naming_table = []
    for row in db_rows:
        doc = frappe.get_doc("InductOne Configuration Option", row.name)
        db[row.option_code] = normalize_option(doc.as_dict())
        naming_table.append({
            "name": row.name,
            "option_code": row.option_code,
            "portable_parent_name": row.name == row.option_code,
        })

    oracle = {spec["option_code"]: normalize_option(spec) for spec in catalog_specs()}

    all_codes = sorted(set(fixture) | set(db) | set(oracle))
    table = []
    for code in all_codes:
        issues = []
        if code not in fixture:
            issues.append("missing_from_fixture")
        if code not in db:
            issues.append("missing_from_candidate_db")
        if code not in oracle:
            issues.append("unexpected_not_in_oracle")
        if code in fixture and code in db and fixture[code] != db[code]:
            issues.append("fixture_db_drift")
        if code in fixture and code in oracle and fixture[code] != oracle[code]:
            issues.append("fixture_oracle_drift")
        if code in db and code in oracle and db[code] != oracle[code]:
            issues.append("db_oracle_drift")
        table.append({
            "option_code": code,
            "status": "PASS" if not issues else "BLOCKER: " + ", ".join(issues),
            "mapping_count_fixture": len(fixture.get(code, {}).get("mappings_table", [])),
            "mapping_count_db": len(db.get(code, {}).get("mappings_table", [])),
            "mapping_count_oracle": len(oracle.get(code, {}).get("mappings_table", [])),
            "issues": issues,
            "diffs": diff_option_triplet(fixture.get(code), db.get(code), oracle.get(code)),
        })

    no_non_dev_leak = all((row.get("option_code") or "").startswith("DEV-") for row in fixture_rows)
    target_balloon_rows = [
        {
            "option_code": code,
            "row_order": row.get("row_order"),
            "action": row.get("action"),
            "target_item": row.get("target_item"),
            "target_balloon": row.get("target_balloon"),
            "replace_with_item": row.get("replace_with_item"),
        }
        for code, option in fixture.items()
        for row in option.get("mappings_table", [])
        if row.get("target_balloon")
    ]
    portability = {
        "parent_names_stable": all(row["portable_parent_name"] for row in naming_table) and len(naming_table) == 13,
        "naming_table": naming_table,
        "semantic_child_fields_only": all(
            "name" not in row
            for option in fixture_rows
            for row in option.get("mappings_table", [])
        ),
        "note": "Parent names are keyed by option_code. Exported child mappings omit child row names and use semantic fields such as item codes, balloons, action, replacement item, and quantity.",
    }

    return {
        "fixture": str(CONFIGURATION_OPTION_FIXTURE),
        "fixture_count": len(fixture_rows),
        "candidate_db_count": len(db_rows),
        "oracle_count": len(oracle),
        "option_codes": [row.get("option_code") for row in fixture_rows],
        "no_non_dev_leak": no_non_dev_leak,
        "target_balloon_row_count": len(target_balloon_rows),
        "target_balloon_rows": target_balloon_rows,
        "portability": portability,
        "table": table,
        "passed": len(fixture_rows) == 13
        and len(db_rows) == 13
        and len(oracle) == 13
        and no_non_dev_leak
        and portability["parent_names_stable"]
        and portability["semantic_child_fields_only"]
        and all(not row["issues"] for row in table),
    }


def normalize_option(row: dict) -> dict:
    return {
        "option_code": row.get("option_code") or "",
        "option_name": row.get("option_name") or "",
        "option_group": row.get("option_group") or "",
        "option_group_required": int(row.get("option_group_required") or 0),
        "is_default_selection": int(row.get("is_default_selection") or 0),
        "is_active": int(row.get("is_active") or 0),
        "status": row.get("status") or "",
        "mapping_status": row.get("mapping_status") or "",
        "owner_role": row.get("owner_role") or "",
        "sort_order": int(row.get("sort_order") or 0),
        "mappings_table": normalize_mappings(row.get("mappings_table") or []),
    }


def normalize_mappings(rows: list[dict]) -> list[dict]:
    normalized = []
    for row in rows:
        normalized.append({
            "action": row.get("action") or "",
            "target_item": row.get("target_item") or "",
            "target_balloon": row.get("target_balloon") or "",
            "replace_with_item": row.get("replace_with_item") or "",
            "qty_fixed": float(row.get("qty_fixed") or 0),
            "row_order": int(row.get("row_order") or 0),
        })
    return sorted(normalized, key=lambda r: (r["row_order"], r["action"], r["target_balloon"], r["target_item"], r["replace_with_item"]))


def diff_option_triplet(fixture: dict | None, db: dict | None, oracle: dict | None) -> dict:
    diffs = {}
    if fixture is not None and db is not None and fixture != db:
        diffs["fixture_vs_db"] = {"fixture": fixture, "db": db}
    if fixture is not None and oracle is not None and fixture != oracle:
        diffs["fixture_vs_oracle"] = {"fixture": fixture, "oracle": oracle}
    if db is not None and oracle is not None and db != oracle:
        diffs["db_vs_oracle"] = {"db": db, "oracle": oracle}
    return diffs


def run_group_logic(frappe, expected_resolution) -> dict:
    options = frappe.get_all(
        "InductOne Configuration Option",
        fields=[
            "name",
            "option_code",
            "option_name",
            "option_group",
            "option_group_required",
            "is_default_selection",
            "is_active",
            "status",
            "sort_order",
        ],
        filters={"is_active": 1, "status": ["in", ["Draft", "Released"]]},
        order_by="sort_order asc",
    )
    dev_options = [row for row in options if row.option_code in {code for codes in EXPECTED_GROUPS.values() for code in codes}]
    groups: dict[str, list[dict]] = {}
    for row in dev_options:
        groups.setdefault(row.option_group, []).append(dict(row))

    group_checks = []
    for group, expected_codes in EXPECTED_GROUPS.items():
        actual = groups.get(group, [])
        actual_codes = [row["option_code"] for row in actual]
        standard_defaults = [row["option_code"] for row in actual if row.get("is_default_selection")]
        group_checks.append({
            "group": group,
            "expected_codes": expected_codes,
            "actual_codes": actual_codes,
            "all_required": all(int(row.get("option_group_required") or 0) == 1 for row in actual),
            "defaults": standard_defaults,
            "passed": actual_codes == expected_codes
            and all(int(row.get("option_group_required") or 0) == 1 for row in actual)
            and len(standard_defaults) == 1,
        })

    default_selection = simulate_default_selection(dev_options)
    default_resolution = expected_resolution(default_selection, frappe)
    default_extensions_off = all(not default_resolution["by_balloon"][b] for b in ["143", "145", "149", "156"])
    default_all_standard = all(
        default_resolution["by_balloon"][balloon][0]["item_code"] == expected_item
        for balloon, expected_item in [
            ("137", "MCVP-19MFP-5M"),
            ("140", "1407378"),
            ("141", "1407485"),
            ("144", "1407362"),
            ("154", "1417891"),
            ("159", "WKC 8T-4-RSC 8T"),
            ("172", "11245"),
            ("173", "11283"),
            ("190", "1425016"),
            ("191", "1007-300-0002-02"),
            ("193", "1417902"),
        ]
    )

    selected = set(default_selection)
    selected = simulate_select(selected, dev_options, "DEV-PANEL-IPC")
    selected = simulate_select(selected, dev_options, "DEV-COMP-HMI")
    cross_group_ok = {"DEV-PANEL-IPC", "DEV-COMP-HMI"}.issubset(selected)

    selected2 = set(default_selection)
    selected2 = simulate_select(selected2, dev_options, "DEV-PANEL-IPC")
    same_group_ok = "DEV-PANEL-IPC" in selected2 and "DEV-PANEL-IPC-STD" not in selected2

    requirements_pass = validate_required_groups(selected2, dev_options)["ok"]
    missing_group = set(selected2)
    missing_group.discard("DEV-PANEL-MCP-STD")
    missing_group.discard("DEV-PANEL-MCP")
    requirements_fail = not validate_required_groups(missing_group, dev_options)["ok"]

    return {
        "loaded_count": len(dev_options),
        "loaded_options": dev_options,
        "group_count": len(groups),
        "group_checks": group_checks,
        "default_selection": sorted(default_selection),
        "default_selection_expected": sorted(EXPECTED_DEFAULT_SELECTION),
        "default_resolves_all_standard": default_all_standard,
        "default_extensions_off": default_extensions_off,
        "cross_group_multi_select_ok": cross_group_ok,
        "same_group_deselect_ok": same_group_ok,
        "requirements_pass_when_complete": requirements_pass,
        "requirements_fail_when_group_empty": requirements_fail,
        "passed": len(dev_options) == 13
        and len(groups) == 7
        and all(row["passed"] for row in group_checks)
        and set(default_selection) == EXPECTED_DEFAULT_SELECTION
        and default_all_standard
        and default_extensions_off
        and cross_group_ok
        and same_group_ok
        and requirements_pass
        and requirements_fail,
    }


def simulate_default_selection(options: list[dict]) -> set[str]:
    selected = set()
    seen_groups = set()
    for row in options:
        group = row.get("option_group") or ""
        if row.get("is_default_selection") and group not in seen_groups:
            selected.add(row["option_code"])
            seen_groups.add(group)
    return selected


def simulate_select(selected: set[str], options: list[dict], option_code: str) -> set[str]:
    by_code = {row["option_code"]: row for row in options}
    row = by_code[option_code]
    group = row.get("option_group") or ""
    if group:
        for other in options:
            if other["option_code"] != option_code and (other.get("option_group") or "") == group:
                selected.discard(other["option_code"])
    selected.add(option_code)
    return selected


def validate_required_groups(selected: set[str], options: list[dict]) -> dict:
    groups: dict[str, dict] = {}
    for row in options:
        group = row.get("option_group") or ""
        if not group:
            continue
        groups.setdefault(group, {"required": False, "selected": 0})
        if int(row.get("option_group_required") or 0):
            groups[group]["required"] = True
        if row["option_code"] in selected:
            groups[group]["selected"] += 1
    failures = [
        {"group": group, "selected": state["selected"]}
        for group, state in groups.items()
        if state["required"] and state["selected"] == 0
    ]
    return {"ok": not failures, "failures": failures}


if __name__ == "__main__":
    raise SystemExit(main())
