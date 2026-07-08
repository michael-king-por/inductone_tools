#!/usr/bin/env python3
"""Close-out validation for balloon-scoped export package artifacts.

This is intentionally a candidate-only validation script.

The hierarchy workbook is a snapshot artifact, not a BOM Export Package ZIP
artifact.  Its per-configuration variance is therefore referenced from the
stage-4 snapshot validation evidence instead of being re-derived from the ZIP.

The ZIP assertion here is narrower: classify every ZIP entry and assert that
the part-documentation document identity set is stable across cable-only option
sets.  Package/configuration-derived files (for example manifest.txt) are
reported but are allowed to vary.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


DEFAULT_EVIDENCE_DIR = Path("/mnt/c/hub/frappe-sandbox/validation-evidence")
DEFAULT_BUILD = "SAL-ORD-2026-00054-BLD-0225"
ZIP_CASE_IDS = {1, 3, 11}  # baseline_only, ipc, everything_moved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--build", default=DEFAULT_BUILD)
    parser.add_argument(
        "--stage4-evidence",
        type=Path,
        default=None,
        help="Optional stage-4 balloon_scoped_options_validation_*.json evidence to reference for hierarchy workbook proof.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = args.evidence_dir / f"balloon_export_zip_closeout_{timestamp}.json"

    import frappe
    from inductone_tools.balloon_scoped_options import catalog_specs, expected_resolution
    from inductone_tools.bom_export import (
        build_zip_bytes,
        build_configured_rows,
        collect_attachments_for_rows,
        explode_bom_tree_structured,
        generate_now,
        resolve_file_path,
    )
    from inductone_tools.snapshot.hierarchy import generate_hierarchy_workbook, populate_snapshot_hierarchy
    from run_balloon_scoped_options_validation import (
        MATRIX,
        assert_balloon_rows,
        assert_collision_flat,
        create_validation_snapshot,
        structural_effects_for,
    )

    payload: dict = {
        "site": args.site,
        "build": args.build,
        "generated_at_utc": timestamp,
        "semantic_correction": {
            "hierarchy_workbook": "snapshot artifact; expected to vary per configuration; referenced from stage-4 validation evidence",
            "bom_export_zip": "part-documentation document identity set should remain stable for cable-only option sets; package/configuration-derived entries may vary",
            "collision_assertions": "checked against resolved configured hierarchy/flat rows, not ZIP contents",
        },
        "stage4_hierarchy_reference": {},
        "cases": [],
        "comparisons": [],
        "warnings": [],
        "failures": [],
    }

    try:
        payload["stage4_hierarchy_reference"] = load_stage4_hierarchy_reference(args.evidence_dir, args.stage4_evidence)
    except Exception as exc:  # noqa: BLE001 - report but do not block ZIP semantics
        payload["warnings"].append({
            "label": "stage4_hierarchy_reference_unavailable",
            "exception": exc.__class__.__name__,
            "message": str(exc),
        })

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        build = frappe.get_doc("InductOne Build", args.build)
        configuration_order = resolve_configuration_order(frappe, build)
        baseline_rows = explode_bom_tree_structured(
            root_bom=build.top_bom,
            explosion_mode="Follow Explicit Child BOM Links",
            include_qty=True,
        )
        specs = catalog_specs()
        case_lookup = {case.case_id: case for case in MATRIX}

        for case_id in sorted(ZIP_CASE_IDS):
            case = case_lookup[case_id]
            result = run_zip_case(
                frappe=frappe,
                build=build,
                configuration_order=configuration_order,
                baseline_rows=baseline_rows,
                case=case,
                catalog_specs=specs,
                expected_resolution=expected_resolution,
                structural_effects_for=structural_effects_for,
                create_validation_snapshot=create_validation_snapshot,
                build_configured_rows=build_configured_rows,
                assert_balloon_rows=assert_balloon_rows,
                assert_collision_flat=assert_collision_flat,
                populate_snapshot_hierarchy=populate_snapshot_hierarchy,
                generate_hierarchy_workbook=generate_hierarchy_workbook,
                generate_now=generate_now,
                resolve_file_path=resolve_file_path,
                collect_attachments_for_rows=collect_attachments_for_rows,
                build_zip_bytes=build_zip_bytes,
            )
            payload["cases"].append(result)
            status = "PASS" if result["passed"] else "FAIL"
            print(status, f"{case.label}: part-doc entries={result.get('part_documentation_count')}; zip={result.get('zip_file_url')}")
            if not result["passed"]:
                payload["failures"].append(f"case:{case.label}")

        comparisons = compare_part_documentation(payload["cases"])
        payload["comparisons"] = comparisons
        for comparison in comparisons:
            status = "PASS" if comparison["passed"] else "FINDING"
            print(status, comparison["label"], comparison["summary"])
            if not comparison["passed"]:
                payload["failures"].append(f"comparison:{comparison['label']}")

        for case_result in payload["cases"]:
            if case_result.get("part_documentation_count", 0) == 0:
                payload["warnings"].append({
                    "label": "empty_part_documentation_payload",
                    "case": case_result.get("label"),
                    "detail": "ZIP contained no PDF/STL/DXF/STEP entries; stability is vacuously true but package contents should be reviewed.",
                })

    except Exception as exc:  # noqa: BLE001 - evidence wants exact exception
        payload["failures"].append("script_exception")
        payload["exception"] = {
            "type": exc.__class__.__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    finally:
        frappe.destroy()

    payload["passed"] = not payload["failures"]
    evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Evidence: {evidence_path}")
    return 0 if payload["passed"] else 1


def load_stage4_hierarchy_reference(evidence_dir: Path, explicit_path: Path | None) -> dict:
    path = explicit_path
    if path is None:
        candidates = sorted(evidence_dir.glob("balloon_scoped_options_validation_*.json"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            return {
                "status": "missing",
                "note": "No balloon_scoped_options_validation_*.json file found; hierarchy workbook proof must be supplied separately.",
            }
        path = candidates[-1]

    data = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for case in data.get("cases", []):
        if case.get("case_id") not in ZIP_CASE_IDS:
            continue
        checks = {check.get("label"): check for check in case.get("checks", [])}
        cases.append({
            "case_id": case.get("case_id"),
            "label": case.get("label"),
            "snapshot": case.get("snapshot"),
            "hierarchy_populated": bool(checks.get("hierarchy_populated", {}).get("passed")),
            "hierarchy_workbook_generated": bool(checks.get("hierarchy_workbook_generated", {}).get("passed")),
            "workbook_details": checks.get("hierarchy_workbook_generated", {}).get("details"),
        })
    return {
        "status": "loaded",
        "path": str(path),
        "note": "Hierarchy workbook differs per configuration at snapshot generation; this ZIP close-out does not re-test it inside the archive.",
        "cases": cases,
    }


def resolve_configuration_order(frappe, build) -> str:
    for fieldname in ("configuration_order", "inductone_configuration_order"):
        value = getattr(build, fieldname, None)
        if value and frappe.db.exists("InductOne Configuration Order", value):
            return value

    existing = frappe.db.get_value(
        "InductOne Configuration Order",
        {"inductone_build": build.name},
        "name",
        order_by="modified desc",
    )
    if existing:
        return existing

    doc = frappe.get_doc({
        "doctype": "InductOne Configuration Order",
        "inductone_build": build.name,
        "sales_order": getattr(build, "sales_order", None),
        "top_item": getattr(build, "top_item", None),
        "top_bom": getattr(build, "top_bom", None),
        "builder_supplier": getattr(build, "builder_supplier", None),
        "co_status": "Draft",
    })
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    frappe.db.commit()
    return doc.name


def run_zip_case(
    *,
    frappe,
    build,
    configuration_order: str,
    baseline_rows: list[dict],
    case,
    catalog_specs: list[dict],
    expected_resolution,
    structural_effects_for,
    create_validation_snapshot,
    build_configured_rows,
    assert_balloon_rows,
    assert_collision_flat,
    populate_snapshot_hierarchy,
    generate_hierarchy_workbook,
    generate_now,
    resolve_file_path,
    collect_attachments_for_rows,
    build_zip_bytes,
) -> dict:
    result: dict = {
        "case_id": case.case_id,
        "label": case.label,
        "moved_options": list(case.moved_options),
        "checks": [],
        "passed": False,
    }
    try:
        selected_codes = ["DEV-BASELINE", *case.moved_options]
        effects = structural_effects_for(selected_codes, catalog_specs)
        snap = create_validation_snapshot(frappe, build, baseline_rows, effects, case)
        pkg_context = SimpleNamespace(
            inductone_build=build.name,
            configured_snapshot=snap.name,
            bom=build.top_bom,
            explosion_mode="Follow Explicit Child BOM Links",
            max_depth=None,
            include_qty=1,
            preserve_duplicate_occurrences=1,
        )
        rows = build_configured_rows(pkg_context)
        expected = expected_resolution(selected_codes, frappe)

        add_check(result, "resolved_balloons_match_oracle", assert_balloon_rows(rows, expected["by_balloon"]))
        add_check(result, "collision_flat_quantities_match_oracle", assert_collision_flat(rows, expected["flat"]))

        # Generate the snapshot artifact so the evidence records the separate
        # workbook path, but do not assert workbook contents from inside the ZIP.
        hierarchy_result = populate_snapshot_hierarchy(snap.name)
        workbook_result = generate_hierarchy_workbook(snap.name)
        add_check(result, "snapshot_hierarchy_populated_for_reference", bool(hierarchy_result and hierarchy_result.get("ok", True)), hierarchy_result)
        add_check(result, "snapshot_hierarchy_workbook_generated_for_reference", bool(workbook_result), workbook_result)

        package_name = create_package(frappe, build, configuration_order, snap.name, case.label)
        package = frappe.get_doc("BOM Export Package", package_name)
        manifest = []
        zip_path = None
        generate_result = None
        direct_zip_result = None

        try:
            generate_result = generate_now(package_name)
            package = frappe.get_doc("BOM Export Package", package_name)
            zip_path = resolve_file_path(package.output_zip)
            add_check(result, "zip_attached", bool(package.output_zip and zip_path and Path(zip_path).exists()), {
                "file_url": package.output_zip,
                "path": zip_path,
                "generate_result": generate_result,
            })
            manifest = inspect_zip(Path(zip_path)) if zip_path else []
        except Exception as exc:  # noqa: BLE001 - fallback only for attachment-size ceiling
            if exc.__class__.__name__ != "MaxFileSizeReachedError":
                raise
            direct_zip_result = build_direct_zip_bytes(
                package=package,
                rows=rows,
                collect_attachments_for_rows=collect_attachments_for_rows,
                build_zip_bytes=build_zip_bytes,
            )
            manifest = inspect_zip_bytes(direct_zip_result["zip_bytes"])
            add_check(result, "zip_generated_direct_after_attach_size_limit", True, {
                "blocked_exception": exc.__class__.__name__,
                "blocked_message": str(exc),
                "zip_name": direct_zip_result["zip_name"],
                "zip_size_bytes": len(direct_zip_result["zip_bytes"]),
                "note": "Candidate attachment save is limited to 10 MB; direct bytes use the same package ZIP builder for manifest validation.",
            })
        part_entries = [entry for entry in manifest if entry["classification"] == "part-documentation"]
        config_entries = [entry for entry in manifest if entry["classification"] == "configuration-derived"]

        result.update({
            "snapshot": snap.name,
            "package": package_name,
            "zip_file_url": package.output_zip,
            "zip_path": zip_path,
            "direct_zip": None if not direct_zip_result else {
                "zip_name": direct_zip_result["zip_name"],
                "zip_size_bytes": len(direct_zip_result["zip_bytes"]),
            },
            "zip_manifest": manifest,
            "part_documentation_count": len(part_entries),
            "configuration_derived_count": len(config_entries),
            "part_documentation_identity_set": sorted(entry["document_identity"] for entry in part_entries),
            "part_documentation_raw_path_set": sorted(entry["path"] for entry in part_entries),
        })
        result["passed"] = all(check["passed"] for check in result["checks"])
    except Exception as exc:  # noqa: BLE001 - evidence wants exact exception
        result["exception"] = {
            "type": exc.__class__.__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        result["passed"] = False
    return result


def create_package(frappe, build, configuration_order: str, snapshot_name: str, label: str) -> str:
    package = frappe.get_doc({
        "doctype": "BOM Export Package",
        "bom": build.top_bom,
        "source_mode": "Configured Build",
        "inductone_build": build.name,
        "configuration_order": configuration_order,
        "configured_snapshot": snapshot_name,
        "builder_supplier": getattr(build, "builder_supplier", None),
        "include_pdf": 1,
        "include_stl": 0,
        "include_dxf": 1,
        "include_step": 0,
        "include_qty": 1,
        "include_item_attachments": 1,
        "include_bom_attachments": 1,
        "explosion_mode": "Follow Explicit Child BOM Links",
        "status": "Draft",
        "run_log": f"Balloon ZIP close-out validation package for {label}",
    })
    package.insert(ignore_permissions=True, ignore_mandatory=True)
    frappe.db.commit()
    return package.name


def build_direct_zip_bytes(*, package, rows: list[dict], collect_attachments_for_rows, build_zip_bytes) -> dict:
    exts = []
    if getattr(package, "include_pdf", 0):
        exts.append(".pdf")
    if getattr(package, "include_dxf", 0):
        exts.append(".dxf")
    attachment_index = collect_attachments_for_rows(
        rows=rows,
        include_item_attachments=bool(getattr(package, "include_item_attachments", 1)),
        include_bom_attachments=bool(getattr(package, "include_bom_attachments", 1)),
        exts=exts,
    )
    zip_name, zip_bytes = build_zip_bytes(
        package_name=package.name,
        package_doc=package,
        rows=rows,
        attachment_index=attachment_index,
        exts=exts,
        missing_rows=[],
    )
    return {"zip_name": zip_name, "zip_bytes": zip_bytes}


def inspect_zip(zip_path: Path) -> list[dict]:
    return inspect_zip_bytes(zip_path.read_bytes())


def inspect_zip_bytes(zip_bytes: bytes) -> list[dict]:
    entries = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            if info.is_dir():
                continue
            data = zf.read(info.filename)
            classification = classify_zip_entry(info.filename)
            entries.append({
                "path": info.filename,
                "file_name": Path(info.filename).name,
                "extension": Path(info.filename).suffix.lower(),
                "size": info.file_size,
                "sha256": hashlib.sha256(data).hexdigest(),
                "classification": classification,
                "document_identity": document_identity(info.filename, classification),
            })
    return entries


def classify_zip_entry(path: str) -> str:
    lower = path.lower()
    first_segment = lower.split("/", 1)[0]
    if (
        lower == "manifest.txt"
        or lower.endswith(".xlsx")
        or "manifest" in lower
        or "configuration" in lower
        or "configured_bom_hierarchy" in lower
        or "snapshot" in lower
    ):
        return "configuration-derived"
    if first_segment in {"pdf", "stl", "dxf", "step", "stp"} or Path(lower).suffix in {".pdf", ".stl", ".dxf", ".step", ".stp"}:
        return "part-documentation"
    return "configuration-derived"


def document_identity(path: str, classification: str) -> str:
    if classification != "part-documentation":
        return path
    parts = path.split("/")
    folder = parts[0].upper() if parts else ""
    file_name = Path(path).name
    # Do not include the item-code folder in the primary stability identity:
    # these cable options may move between cable item codes while intentionally
    # retaining the same drawing/PDF document family. Raw paths are still
    # recorded separately for review.
    return f"{folder}/{file_name}"


def compare_part_documentation(cases: list[dict]) -> list[dict]:
    by_label = {case["label"]: case for case in cases}
    comparisons = []
    for left, right in (("baseline_only", "everything_moved"), ("baseline_only", "ipc")):
        if left not in by_label or right not in by_label:
            comparisons.append({
                "label": f"{left}_vs_{right}_part_documentation_identity",
                "passed": False,
                "summary": "comparison case missing",
            })
            continue
        left_set = set(by_label[left].get("part_documentation_identity_set") or [])
        right_set = set(by_label[right].get("part_documentation_identity_set") or [])
        missing_from_right = sorted(left_set - right_set)
        extra_in_right = sorted(right_set - left_set)
        comparisons.append({
            "label": f"{left}_vs_{right}_part_documentation_identity",
            "passed": not missing_from_right and not extra_in_right,
            "summary": f"{len(left_set)} vs {len(right_set)} document identities",
            "left_case": left,
            "right_case": right,
            "missing_from_right": missing_from_right,
            "extra_in_right": extra_in_right,
            "raw_path_sets_equal": set(by_label[left].get("part_documentation_raw_path_set") or []) == set(by_label[right].get("part_documentation_raw_path_set") or []),
        })
    return comparisons


def add_check(result: dict, label: str, outcome, details=None) -> None:
    if isinstance(outcome, tuple):
        passed, tuple_details = outcome
        details = tuple_details
    else:
        passed = bool(outcome)
    result["checks"].append({"label": label, "passed": bool(passed), "details": details})


if __name__ == "__main__":
    sys.exit(main())
