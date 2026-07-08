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
    from inductone_tools.balloon_scoped_options import expected_resolution

    payload = {
        "generated_at_utc": timestamp,
        "site": args.site,
        "repo_root": str(repo_root),
        "client_script_parity": run_client_script_parity(repo_root),
        "custom_field_fixture": run_custom_field_check(repo_root),
        "group_logic": None,
    }

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        payload["group_logic"] = run_group_logic(frappe, expected_resolution)
    finally:
        frappe.destroy()

    verdicts = [
        payload["client_script_parity"]["passed"],
        payload["custom_field_fixture"]["passed"],
        payload["group_logic"]["passed"],
    ]
    payload["passed"] = all(verdicts)
    evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print("Client Script parity:", "PASS" if payload["client_script_parity"]["passed"] else "BLOCKER")
    for row in payload["client_script_parity"]["table"]:
        status = "identical" if row["identical"] else row["note"]
        print(f"  {row['script_name']}: {status}")
    print("Custom Field fixture:", "PASS" if payload["custom_field_fixture"]["passed"] else "BLOCKER")
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

    passed = (
        set(basis) == set(repo)
        and differing == ["InductOne Build Script"]
        and next(row for row in table if row["script_name"] == "InductOne Build Script")["note"] == "PASS: only W1/W2 target_balloon carry-through additions"
    )
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
        filters={"is_active": 1, "status": ["in", ["Defined-Ops", "Released"]]},
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

