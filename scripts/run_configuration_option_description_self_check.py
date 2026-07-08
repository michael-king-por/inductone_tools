#!/usr/bin/env python3
"""Validate DEV configuration option descriptions against the resolver catalog."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_EVIDENCE_DIR = Path("/mnt/c/hub/frappe-sandbox/validation-evidence")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    return parser.parse_args()


def section_split(builder_description: str) -> dict[str, str]:
    if builder_description.count("\n\nConfiguration effect:\n") != 1:
        raise AssertionError("Configuration effect marker must appear exactly once")
    if builder_description.count("\n\nNotes:\n") != 1:
        raise AssertionError("Notes marker must appear exactly once")

    main, rest = builder_description.split("\n\nConfiguration effect:\n", 1)
    effect, notes = rest.split("\n\nNotes:\n", 1)
    if not main.strip():
        raise AssertionError("main description is empty")
    if not effect.strip():
        raise AssertionError("Configuration effect section is empty")
    if not notes.strip():
        raise AssertionError("Notes section is empty")
    return {"main": main.strip(), "configuration_effect": effect.strip(), "notes": notes.strip()}


def expected_effect_codes(spec: dict) -> set[str]:
    codes: set[str] = set()
    for mapping in spec["mappings_table"]:
        if mapping["action"] == "REPLACE":
            codes.add(mapping["replace_with_item"])
        elif mapping["action"] == "ADD":
            codes.add(mapping["target_item"])
    return codes


def main() -> int:
    args = parse_args()

    import frappe
    from inductone_tools.balloon_scoped_options import (
        INTERNAL_NOTES,
        MOVED_OPTION_CODES,
        STANDARD_OPTION_CODES,
        catalog_specs,
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = args.evidence_dir / f"configuration_option_description_self_check_{timestamp}.json"

    specs = {spec["option_code"]: spec for spec in catalog_specs()}
    known_effect_codes = set()
    for spec in specs.values():
        known_effect_codes.update(expected_effect_codes(spec))

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    results = []
    try:
        for code, spec in specs.items():
            docname = frappe.db.get_value("InductOne Configuration Option", {"option_code": code}, "name")
            row = {
                "option_code": code,
                "docname": docname,
                "status": None,
                "mapping_status": None,
                "passed": True,
                "findings": [],
                "expected_effect_codes": sorted(expected_effect_codes(spec)),
                "effect_codes_found": [],
            }

            if not docname:
                row["passed"] = False
                row["findings"].append("missing option record")
                results.append(row)
                continue

            doc = frappe.get_doc("InductOne Configuration Option", docname)
            row["status"] = doc.status
            row["mapping_status"] = doc.mapping_status

            if doc.status != "Draft":
                row["passed"] = False
                row["findings"].append(f"expected Draft, found {doc.status!r}")
            if doc.mapping_status != "Complete":
                row["passed"] = False
                row["findings"].append(f"expected mapping_status Complete, found {doc.mapping_status!r}")
            if (doc.internal_notes or "") != INTERNAL_NOTES[code]:
                row["passed"] = False
                row["findings"].append("internal_notes does not match catalog source")
            if not (doc.internal_notes or "").strip():
                row["passed"] = False
                row["findings"].append("internal_notes is empty")

            # Internal notes are decision guidance, not build implementation.
            internal_hits = [
                item_code
                for item_code in known_effect_codes
                if item_code and item_code in (doc.internal_notes or "")
            ]
            if internal_hits:
                row["passed"] = False
                row["findings"].append(f"internal_notes contains part codes: {internal_hits}")

            try:
                sections = section_split(doc.builder_description or "")
                row["render_sections"] = sections
            except AssertionError as exc:
                row["passed"] = False
                row["findings"].append(str(exc))
                sections = {"configuration_effect": ""}

            effect = sections.get("configuration_effect", "")
            found_effect_codes = sorted(
                item_code for item_code in known_effect_codes if item_code and item_code in effect
            )
            row["effect_codes_found"] = found_effect_codes

            if code in MOVED_OPTION_CODES:
                expected = expected_effect_codes(spec)
                found = set(found_effect_codes)
                if found != expected:
                    row["passed"] = False
                    row["findings"].append({
                        "effect_code_mismatch": {
                            "missing_from_description": sorted(expected - found),
                            "extra_in_description": sorted(found - expected),
                        }
                    })
                notes = (sections.get("notes") or "").lower()
                for token in ("overlap", "double cabling", "paired"):
                    if token not in notes:
                        row["passed"] = False
                        row["findings"].append(f"moved option notes missing {token!r} guidance")
            elif code in STANDARD_OPTION_CODES:
                if "No change. Baseline standard cabling applies." not in effect:
                    row["passed"] = False
                    row["findings"].append("standard option effect must explicitly state no change")
            elif code == "DEV-BASELINE":
                if "Always applied" not in (sections.get("notes") or ""):
                    row["passed"] = False
                    row["findings"].append("baseline notes must document always-applied behavior")

            results.append(row)
    finally:
        frappe.destroy()

    payload = {
        "site": args.site,
        "generated_at_utc": timestamp,
        "option_count": len(results),
        "passed": all(row["passed"] for row in results),
        "results": results,
    }
    evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    for row in results:
        status = "PASS" if row["passed"] else "FAIL"
        print(f"{status} {row['option_code']}: {row['status']} {row['findings'] or ''}")
    print(f"Evidence: {evidence_path}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
