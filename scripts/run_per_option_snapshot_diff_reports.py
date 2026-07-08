#!/usr/bin/env python3
"""Generate per-option Configured BOM Snapshot Diff evidence.

This tool is intentionally headless orchestration around existing InductOne
machinery:

* snapshot structural effects are frozen from ``InductOne Configuration Option``
  mappings using the same effect-mode resolution exercised by the balloon
  validation suite;
* configured rows and materialized hierarchy are produced by the existing
  ``bom_export`` and ``snapshot.hierarchy`` code paths;
* XLSX output is produced by the existing Snapshot Diff report machinery; and
* oracle checks come from ``inductone_tools.balloon_scoped_options``.

Production caveat: running this tool against a real site creates real
``Configured BOM Snapshot`` records attached to the requested build. For the
engineering deliverable, the owner must decide whether to run against the real
sales-order build or a scratch/throwaway build.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run_balloon_scoped_options_validation import (  # noqa: E402
    create_validation_snapshot,
    load_hierarchy_rows,
    managed_rows_by_balloon,
    run_preconditions,
    structural_effects_for,
)


DEFAULT_EVIDENCE_DIR = Path("/mnt/c/hub/frappe-sandbox/validation-evidence")
DEFAULT_BUILD = "SAL-ORD-2026-00054-BLD-0225"
DEFAULT_TOP_BOM = "BOM-1611 027 0020-002"

ELECTRICAL_STANDARD_CODES = [
    "DEV-PANEL-MCP-STD",
    "DEV-PANEL-IPC-STD",
    "DEV-COMP-HMI-STD",
    "DEV-COMP-STACK-STD",
    "DEV-COMP-FORTRESS-STD",
    "DEV-COMP-MAGLOCK-STD",
]

STANDARD_BY_DEVIATION = {
    "DEV-PANEL-MCP": "DEV-PANEL-MCP-STD",
    "DEV-PANEL-IPC": "DEV-PANEL-IPC-STD",
    "DEV-COMP-HMI": "DEV-COMP-HMI-STD",
    "DEV-COMP-STACK": "DEV-COMP-STACK-STD",
    "DEV-COMP-FORTRESS": "DEV-COMP-FORTRESS-STD",
    "DEV-COMP-MAGLOCK": "DEV-COMP-MAGLOCK-STD",
}

DEFAULT_STABLE_OPTION_CODES = [
    "JB3-ADD",
    "5G-REMOVE",
    "STCK-2-REMOVE",
    "ROB-PEN-REMOVE",
    # The implementation catalog spells this RISER; accept the brief's RIZER
    # spelling through OPTION_ALIASES below.
    "RIZER-MEZ-30.5",
]

OPTION_ALIASES = {
    "RIZER-MEZ-30.5": "RISER-MEZ-30.5",
}

DEFAULT_DEVIATIONS = [
    {"label": "mcp_relocated", "moved_options": ["DEV-PANEL-MCP"]},
    {"label": "ipc_relocated", "moved_options": ["DEV-PANEL-IPC"]},
    {"label": "hmi_relocated", "moved_options": ["DEV-COMP-HMI"]},
    {"label": "stacklight_relocated", "moved_options": ["DEV-COMP-STACK"]},
    {"label": "fortress_relocated", "moved_options": ["DEV-COMP-FORTRESS"]},
    {"label": "maglock_relocated", "moved_options": ["DEV-COMP-MAGLOCK"]},
    {
        "label": "everything_moved",
        "moved_options": [
            "DEV-PANEL-MCP",
            "DEV-PANEL-IPC",
            "DEV-COMP-HMI",
            "DEV-COMP-STACK",
            "DEV-COMP-FORTRESS",
            "DEV-COMP-MAGLOCK",
        ],
    },
]

MAPPING_FIELDS = [
    "action",
    "target_item",
    "target_balloon",
    "target_bom",
    "replace_with_item",
    "replace_scope",
    "replace_count",
    "replace_with_bom",
    "structural_effect_mode",
    "expand_mode",
    "qty_fixed",
    "row_order",
]


@dataclass(frozen=True)
class SnapshotCase:
    case_id: int
    label: str
    moved_options: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate baseline-vs-option Snapshot Diff XLSX/JSON evidence."
    )
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--build", default=DEFAULT_BUILD)
    parser.add_argument("--top-bom", default=DEFAULT_TOP_BOM)
    parser.add_argument(
        "--deviation-spec",
        type=Path,
        help=(
            "Optional JSON list of {'label': str, 'moved_options': [codes]} objects. "
            "Defaults to the seven engineering-review deviations."
        ),
    )
    parser.add_argument(
        "--include-unchanged",
        action="store_true",
        help="Include unchanged rows in the structured Snapshot Diff JSON/report views.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)

    import frappe
    from inductone_tools.balloon_scoped_options import (
        COLLISION_REFERENCE_BOM,
        MASTER_ELECTRICAL_BOM,
        expected_resolution,
    )
    from inductone_tools.bom_export import build_configured_rows, explode_bom_tree_structured
    from inductone_tools.snapshot.hierarchy import populate_snapshot_hierarchy
    from inductone_tools.snapshot_diff.loader import (
        get_diff,
        get_report_data,
        save_report_workbook,
    )

    summary_path = args.evidence_dir / f"per_option_snapshot_diff_index_{timestamp}.json"
    manifest_path = args.evidence_dir / f"per_option_snapshot_diff_manifest_{timestamp}.md"
    payload = {
        "site": args.site,
        "build": args.build,
        "top_bom_expected": args.top_bom,
        "generated_at_utc": timestamp,
        "production_caveat": (
            "Running this tool creates real Configured BOM Snapshot records attached "
            "to the requested build. Confirm whether the production deliverable should "
            "run on the real sales-order build or a scratch build."
        ),
        "baseline": {},
        "deviations": [],
        "outputs": {
            "summary_json": str(summary_path),
            "manifest": str(manifest_path),
        },
        "failures": [],
    }

    failures: list[str] = []

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        preconditions = run_preconditions(
            frappe,
            args.build,
            MASTER_ELECTRICAL_BOM,
            COLLISION_REFERENCE_BOM,
        )
        payload["preconditions"] = preconditions
        for check in preconditions["checks"]:
            print(("PASS" if check["passed"] else "FAIL"), check["label"], check.get("details", ""), flush=True)
            if not check["passed"]:
                failures.append(f"precondition:{check['label']}")

        if failures:
            payload["failures"] = failures
            write_outputs(payload, summary_path, manifest_path)
            return 1

        build = frappe.get_doc("InductOne Build", args.build)
        if (build.top_bom or "") != args.top_bom:
            failures.append("top_bom_mismatch")
            payload["top_bom_actual"] = build.top_bom
            payload["failures"] = failures
            write_outputs(payload, summary_path, manifest_path)
            print("FAIL top BOM mismatch", {"expected": args.top_bom, "actual": build.top_bom}, flush=True)
            return 1

        stable_codes = resolve_option_codes(frappe, DEFAULT_STABLE_OPTION_CODES)
        deviations = load_deviation_spec(args.deviation_spec)
        baseline_codes = selected_codes_for(())
        baseline_selected = resolve_option_codes(frappe, [*stable_codes, *baseline_codes])

        baseline_rows = explode_bom_tree_structured(
            root_bom=build.top_bom,
            explosion_mode="Follow Explicit Child BOM Links",
            include_qty=True,
        )

        baseline_snapshot = generate_snapshot(
            frappe=frappe,
            build=build,
            baseline_rows=baseline_rows,
            selected_codes=baseline_selected,
            case=SnapshotCase(9700, "per_option_baseline", ()),
            populate_snapshot_hierarchy=populate_snapshot_hierarchy,
            build_configured_rows=build_configured_rows,
        )
        baseline_hierarchy = load_hierarchy_rows(frappe, baseline_snapshot["snapshot"])
        baseline_observed = normalize_by_balloon(managed_rows_by_balloon(baseline_hierarchy))
        baseline_expected = normalize_by_balloon(expected_resolution(baseline_selected, frappe)["by_balloon"])
        baseline_check = {
            "passed": baseline_observed == baseline_expected,
            "expected": baseline_expected,
            "observed": baseline_observed,
        }
        payload["baseline"] = {
            **baseline_snapshot,
            "selected_options": baseline_selected,
            "oracle_check": baseline_check,
        }
        print(
            "PASS" if baseline_check["passed"] else "FAIL",
            "baseline oracle match",
            baseline_snapshot["snapshot"],
            flush=True,
        )
        if not baseline_check["passed"]:
            failures.append("baseline_oracle_check")

        for idx, spec in enumerate(deviations, start=1):
            label = spec["label"]
            moved = tuple(spec["moved_options"])
            selected = resolve_option_codes(frappe, [*stable_codes, *selected_codes_for(moved)])
            print(f"RUN deviation {label}", selected, flush=True)
            try:
                deviation_snapshot = generate_snapshot(
                    frappe=frappe,
                    build=build,
                    baseline_rows=baseline_rows,
                    selected_codes=selected,
                    case=SnapshotCase(9700 + idx, f"per_option_{label}", moved),
                    populate_snapshot_hierarchy=populate_snapshot_hierarchy,
                    build_configured_rows=build_configured_rows,
                )
                xlsx_path = args.evidence_dir / report_filename(
                    args.build,
                    f"baseline_vs_{label}",
                    timestamp,
                    "xlsx",
                )
                workbook_result = save_report_workbook(
                    payload["baseline"]["snapshot"],
                    deviation_snapshot["snapshot"],
                    xlsx_path,
                    context_mode="Show full list" if args.include_unchanged else "Changes only",
                )
                structured_diff = get_diff(
                    payload["baseline"]["snapshot"],
                    deviation_snapshot["snapshot"],
                    include_unchanged=1 if args.include_unchanged else 0,
                )
                hierarchy_rows = load_hierarchy_rows(frappe, deviation_snapshot["snapshot"])
                observed = normalize_by_balloon(managed_rows_by_balloon(hierarchy_rows))
                expected = normalize_by_balloon(expected_resolution(selected, frappe)["by_balloon"])
                oracle = compare_to_oracle(
                    baseline_expected=baseline_expected,
                    deviation_expected=expected,
                    baseline_observed=baseline_observed,
                    deviation_observed=observed,
                    moved_options=moved,
                )
                diff_json = {
                    "site": args.site,
                    "build": args.build,
                    "label": label,
                    "generated_at_utc": timestamp,
                    "baseline_snapshot": payload["baseline"]["snapshot"],
                    "deviation_snapshot": deviation_snapshot["snapshot"],
                    "selected_options": selected,
                    "moved_options": list(moved),
                    "snapshot_diff": structured_diff,
                    "report_views": {
                        "hierarchical": get_report_data(
                            payload["baseline"]["snapshot"],
                            deviation_snapshot["snapshot"],
                            view_mode="Hierarchical",
                            context_mode="Show full list" if args.include_unchanged else "Changes only",
                        ),
                        "flat_procurement": get_report_data(
                            payload["baseline"]["snapshot"],
                            deviation_snapshot["snapshot"],
                            view_mode="Flat Procurement",
                            context_mode="Show full list" if args.include_unchanged else "Changes only",
                        ),
                    },
                    "balloon_delta": oracle["observed_delta"],
                    "expected_balloon_delta": oracle["expected_delta"],
                    "oracle_check": oracle,
                    "workbook": workbook_result,
                }
                json_path = args.evidence_dir / report_filename(
                    args.build,
                    f"baseline_vs_{label}",
                    timestamp,
                    "json",
                )
                json_path.write_text(json.dumps(diff_json, indent=2, default=str), encoding="utf-8")

                result = {
                    **deviation_snapshot,
                    "label": label,
                    "moved_options": list(moved),
                    "selected_options": selected,
                    "xlsx": str(xlsx_path),
                    "json": str(json_path),
                    "oracle_passed": oracle["passed"],
                    "sentinel_checks": oracle["sentinel_checks"],
                    "snapshot_diff_summary": structured_diff["summary"],
                }
                payload["deviations"].append(result)
                print(
                    "PASS" if oracle["passed"] else "FAIL",
                    f"{label} oracle delta",
                    json.dumps({
                        "changed_balloons": sorted(oracle["observed_delta"].get("changed", {})),
                        "xlsx": str(xlsx_path),
                        "json": str(json_path),
                    }),
                    flush=True,
                )
                if not oracle["passed"]:
                    failures.append(f"oracle:{label}")
            except Exception as exc:  # noqa: BLE001 - evidence wants exact exception
                failures.append(f"deviation:{label}")
                payload["deviations"].append({
                    "label": label,
                    "moved_options": list(moved),
                    "exception": {
                        "type": exc.__class__.__name__,
                        "message": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                })
                print("FAIL", label, exc.__class__.__name__, str(exc), flush=True)

        payload["failures"] = failures
        write_outputs(payload, summary_path, manifest_path)
    finally:
        frappe.destroy()

    print(f"Summary JSON: {summary_path}", flush=True)
    print(f"Manifest: {manifest_path}", flush=True)
    return 1 if failures else 0


def load_deviation_spec(path: Path | None) -> list[dict]:
    if not path:
        return DEFAULT_DEVIATIONS
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("--deviation-spec must be a JSON list")
    normalized = []
    for idx, row in enumerate(data, start=1):
        label = row.get("label")
        moved = row.get("moved_options") or []
        if not label or not isinstance(moved, list):
            raise ValueError(f"Invalid deviation spec row {idx}: {row!r}")
        normalized.append({"label": str(label), "moved_options": [str(code) for code in moved]})
    return normalized


def selected_codes_for(moved_options: Iterable[str]) -> list[str]:
    moved = set(moved_options)
    selected = ["DEV-BASELINE"]
    for deviation_code, std_code in STANDARD_BY_DEVIATION.items():
        selected.append(deviation_code if deviation_code in moved else std_code)
    return selected


def resolve_option_codes(frappe, requested_codes: Iterable[str]) -> list[str]:
    resolved = []
    seen = set()
    for raw_code in requested_codes:
        code = OPTION_ALIASES.get(raw_code, raw_code)
        if code in seen:
            continue
        exists = frappe.db.exists("InductOne Configuration Option", {"option_code": code})
        if not exists:
            raise ValueError(f"InductOne Configuration Option not found for option_code={raw_code!r} resolved={code!r}")
        resolved.append(code)
        seen.add(code)
    return resolved


def load_site_catalog_specs(frappe, selected_codes: list[str]) -> list[dict]:
    specs = []
    for code in selected_codes:
        name = frappe.db.get_value("InductOne Configuration Option", {"option_code": code}, "name")
        if not name:
            raise ValueError(f"Missing InductOne Configuration Option for {code}")
        doc = frappe.get_doc("InductOne Configuration Option", name)
        specs.append({
            "option_code": doc.option_code,
            "mappings_table": [
                {field: row.get(field) for field in MAPPING_FIELDS}
                for row in (doc.get("mappings_table") or [])
            ],
        })
    return specs


def generate_snapshot(
    frappe,
    build,
    baseline_rows: list[dict],
    selected_codes: list[str],
    case: SnapshotCase,
    populate_snapshot_hierarchy,
    build_configured_rows,
) -> dict:
    catalog_specs = load_site_catalog_specs(frappe, selected_codes)
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
    resolved_rows = build_configured_rows(pkg)
    hierarchy_result = populate_snapshot_hierarchy(snap.name)
    hierarchy_count = frappe.db.count(
        "Configured BOM Snapshot Hierarchy",
        {"parent": snap.name, "parenttype": "Configured BOM Snapshot"},
    )
    return {
        "snapshot": snap.name,
        "snapshot_rev": snap.snapshot_rev,
        "structural_effect_count": len(structural_effects),
        "resolved_row_count": len(resolved_rows),
        "hierarchy_count": hierarchy_count,
        "hierarchy_result": hierarchy_result,
    }


def normalize_by_balloon(payload: dict[str, list[dict]]) -> dict[str, list[dict]]:
    normalized = {}
    for balloon, rows in payload.items():
        normalized[str(balloon)] = sorted(
            [
                {
                    "item_code": str(row.get("item_code") or ""),
                    "qty": float(row.get("qty") or 0),
                }
                for row in rows
            ],
            key=lambda row: (row["item_code"], row["qty"]),
        )
    return dict(sorted(normalized.items()))


def delta_by_balloon(before: dict[str, list[dict]], after: dict[str, list[dict]]) -> dict:
    changed = {}
    unchanged = []
    for balloon in sorted(set(before) | set(after), key=natural_key):
        before_rows = before.get(balloon, [])
        after_rows = after.get(balloon, [])
        if before_rows == after_rows:
            unchanged.append(balloon)
        else:
            changed[balloon] = {"from": before_rows, "to": after_rows}
    return {"changed": changed, "unchanged": unchanged}


def compare_to_oracle(
    baseline_expected: dict[str, list[dict]],
    deviation_expected: dict[str, list[dict]],
    baseline_observed: dict[str, list[dict]],
    deviation_observed: dict[str, list[dict]],
    moved_options: tuple[str, ...],
) -> dict:
    expected_delta = delta_by_balloon(baseline_expected, deviation_expected)
    observed_delta = delta_by_balloon(baseline_observed, deviation_observed)
    baseline_matches = baseline_expected == baseline_observed
    deviation_matches = deviation_expected == deviation_observed
    changed_sets_match = sorted(expected_delta["changed"], key=natural_key) == sorted(
        observed_delta["changed"], key=natural_key
    )
    changed_payloads_match = expected_delta["changed"] == observed_delta["changed"]
    sentinel_checks = sentinel_checks_for(moved_options, observed_delta)
    return {
        "passed": all([
            baseline_matches,
            deviation_matches,
            changed_sets_match,
            changed_payloads_match,
            all(check["passed"] for check in sentinel_checks),
        ]),
        "baseline_matches_oracle": baseline_matches,
        "deviation_matches_oracle": deviation_matches,
        "changed_sets_match": changed_sets_match,
        "changed_payloads_match": changed_payloads_match,
        "expected_delta": expected_delta,
        "observed_delta": observed_delta,
        "sentinel_checks": sentinel_checks,
    }


def sentinel_checks_for(moved_options: tuple[str, ...], observed_delta: dict) -> list[dict]:
    checks = []
    if "DEV-PANEL-IPC" in moved_options:
        for balloon, from_item, to_item in [
            ("172", "11245", "11283"),
            ("173", "11283", "11351"),
        ]:
            delta = (observed_delta.get("changed") or {}).get(balloon) or {}
            from_items = [row["item_code"] for row in delta.get("from", [])]
            to_items = [row["item_code"] for row in delta.get("to", [])]
            checks.append({
                "label": f"IPC sentinel {balloon}: {from_item}->{to_item}",
                "passed": from_item in from_items and to_item in to_items,
                "details": {"from": delta.get("from", []), "to": delta.get("to", [])},
            })
    return checks


def report_filename(build: str, label: str, timestamp: str, ext: str) -> str:
    return f"snapshot_diff_{safe_name(build)}_{safe_name(label)}_{timestamp}.{ext}"


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def natural_key(value: str):
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", str(value))]


def write_outputs(payload: dict, summary_path: Path, manifest_path: Path) -> None:
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    manifest_path.write_text(render_manifest(payload), encoding="utf-8")


def render_manifest(payload: dict) -> str:
    lines = [
        "# Per-option Snapshot Diff Manifest",
        "",
        f"- Site: `{payload.get('site')}`",
        f"- Build: `{payload.get('build')}`",
        f"- Generated UTC: `{payload.get('generated_at_utc')}`",
        f"- Baseline snapshot: `{(payload.get('baseline') or {}).get('snapshot')}`",
        "",
        "Production caveat: running this tool creates real Configured BOM Snapshot records attached to the requested build. Confirm whether to run on the real build or a scratch build.",
        "",
        "## Reports",
        "",
    ]
    for row in payload.get("deviations") or []:
        status = "PASS" if row.get("oracle_passed") else "FAIL"
        lines.extend([
            f"### {row.get('label')} — {status}",
            "",
            f"- Snapshot: `{row.get('snapshot')}`",
            f"- XLSX: `{row.get('xlsx')}`",
            f"- JSON: `{row.get('json')}`",
            f"- Moved options: `{', '.join(row.get('moved_options') or [])}`",
            "",
        ])
    if payload.get("failures"):
        lines.extend(["## Failures", "", *[f"- `{failure}`" for failure in payload["failures"]], ""])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
