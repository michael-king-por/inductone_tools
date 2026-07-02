#!/usr/bin/env python3
"""Compare BOM Item Custom Field fixtures against a live site.

This script is read-only with respect to Frappe. It exists to answer one
deployment-gate question:

    Would `bench migrate` overwrite any live BOM Item Custom Field definition?

Fixture sync inserts or updates Custom Field records to match fixture JSON.
That is safe only when fixture-managed production fields already match the
fixture definition, or when a mismatch is an explicitly approved definition
change.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SIGNIFICANT_PROPERTIES = [
    "fieldtype",
    "label",
    "options",
    "reqd",
    "default",
    "insert_after",
    "depends_on",
    "mandatory_depends_on",
    "read_only",
    "hidden",
    "no_copy",
    "translatable",
    "length",
    "permlevel",
    "fetch_from",
    "in_list_view",
]


def normalize_value(value: Any) -> Any:
    """Normalize Frappe JSON/doc values before comparing definitions."""

    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        # Frappe often stores empty nullable fields as "" in exported fixtures
        # and None in live docs. Treat those as equivalent for definition drift.
        return value if value != "" else None
    return value


def load_fixture_rows(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [
        row
        for row in data
        if row.get("doctype") == "Custom Field" and row.get("dt") == "BOM Item"
    ]
    return {row["fieldname"]: row for row in rows}


def load_live_rows(frappe: Any) -> dict[str, dict[str, Any]]:
    rows = frappe.get_all(
        "Custom Field",
        filters={"dt": "BOM Item"},
        fields=["name", "fieldname"],
        order_by="fieldname asc",
    )
    live: dict[str, dict[str, Any]] = {}
    for row in rows:
        doc = frappe.get_doc("Custom Field", row.name)
        live[row.fieldname] = doc.as_dict()
    return live


def compare_rows(
    fixture_rows: dict[str, dict[str, Any]],
    live_rows: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    all_fieldnames = sorted(set(fixture_rows) | set(live_rows))

    for fieldname in all_fieldnames:
        fixture = fixture_rows.get(fieldname)
        live = live_rows.get(fieldname)

        if fixture and not live:
            results.append(
                {
                    "fieldname": fieldname,
                    "classification": "WOULD_CREATE",
                    "diffs": {},
                }
            )
            continue

        if live and not fixture:
            results.append(
                {
                    "fieldname": fieldname,
                    "classification": "UNMANAGED_ON_SITE",
                    "diffs": {},
                }
            )
            continue

        assert fixture is not None and live is not None
        diffs: dict[str, dict[str, Any]] = {}
        for prop in SIGNIFICANT_PROPERTIES:
            live_value = normalize_value(live.get(prop))
            fixture_value = normalize_value(fixture.get(prop))
            if live_value != fixture_value:
                diffs[prop] = {
                    "site": live_value,
                    "fixture": fixture_value,
                }

        results.append(
            {
                "fieldname": fieldname,
                "classification": "WOULD_OVERWRITE" if diffs else "MATCH",
                "diffs": diffs,
            }
        )

    return results


def print_summary(results: list[dict[str, Any]], evidence_path: Path) -> None:
    counts: dict[str, int] = {}
    for result in results:
        counts[result["classification"]] = counts.get(result["classification"], 0) + 1

    print("Custom Field fixture parity: BOM Item")
    for classification in [
        "MATCH",
        "WOULD_CREATE",
        "WOULD_OVERWRITE",
        "UNMANAGED_ON_SITE",
    ]:
        print(f"  {classification}: {counts.get(classification, 0)}")

    for result in results:
        classification = result["classification"]
        fieldname = result["fieldname"]
        print(f"{classification}: {fieldname}")
        if classification == "WOULD_OVERWRITE":
            diffs = result["diffs"]
            if "options" in diffs:
                diff = diffs["options"]
                print("  !! options drift:")
                print(f"     site    = {diff['site']!r}")
                print(f"     fixture = {diff['fixture']!r}")
            for prop, diff in sorted(diffs.items()):
                if prop == "options":
                    continue
                print(f"  - {prop}: site={diff['site']!r} -> fixture={diff['fixture']!r}")

    print(f"Evidence written: {evidence_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only BOM Item Custom Field fixture/live parity checker."
    )
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--fixture-path", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_dir = args.evidence_dir
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / f"custom_field_fixture_parity_{timestamp}.json"

    import frappe

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        fixture_rows = load_fixture_rows(args.fixture_path)
        live_rows = load_live_rows(frappe)
        results = compare_rows(fixture_rows, live_rows)

        payload = {
            "site": args.site,
            "sites_path": args.sites_path,
            "fixture_path": str(args.fixture_path),
            "generated_at_utc": timestamp,
            "doctype": "BOM Item",
            "significant_properties": SIGNIFICANT_PROPERTIES,
            "summary": {
                classification: sum(
                    1 for result in results if result["classification"] == classification
                )
                for classification in [
                    "MATCH",
                    "WOULD_CREATE",
                    "WOULD_OVERWRITE",
                    "UNMANAGED_ON_SITE",
                ]
            },
            "results": results,
        }
        evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    finally:
        frappe.destroy()

    print_summary(results, evidence_path)
    return 1 if any(result["classification"] == "WOULD_OVERWRITE" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
