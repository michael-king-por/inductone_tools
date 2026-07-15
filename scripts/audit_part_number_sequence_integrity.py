#!/usr/bin/env python3
"""Audit Part Number Assignment rows that can affect allocator sequence.

This is read-only. It exists because the allocator originally treated every
numeric value matching ``^[1-4][0-9]+$`` as sequence-authoritative. That allowed
vendor/manufacturer cable numbers represented in the assignment ledger to jump
the allocator from the 10005xx range into 14179xx.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import frappe

from inductone_tools.part_numbering import (
    LIVE_SEQUENCE_EXCEPTION_BATCHES,
    _extract_sequence,
    _is_sequence_authoritative_assignment,
    _make_part_number,
)


CONTROLLED_NUMBER_RE = re.compile(r"^[1-4][0-9]+$")
FAMILIES = ["Part", "Assembly", "Software", "Service"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument(
        "--evidence-dir",
        default="/tmp",
        help="Directory where JSON evidence should be written.",
    )
    return parser.parse_args()


def _as_dict(row) -> dict:
    return dict(row)


def run(site: str, sites_path: str, evidence_dir: str) -> int:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_path = Path(evidence_dir) / f"part_number_sequence_integrity_{timestamp}.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)

    frappe.init(site=site, sites_path=sites_path)
    frappe.connect()

    try:
        rows = frappe.get_all(
            "Part Number Assignment",
            fields=[
                "name",
                "part_number",
                "number_family",
                "status",
                "reserved_for",
                "description_requested",
                "allocation_batch_id",
                "is_custom_number",
                "gitlab_reference",
                "released_item",
                "creation",
                "modified",
                "owner",
            ],
            limit_page_length=0,
            order_by="creation asc, part_number asc",
        )

        controlled_like = []
        sequence_authoritative = []
        manual_or_custom_controlled_like = []
        live_exception_batch_rows = []

        for raw in rows:
            row = _as_dict(raw)
            part_number = str(row.get("part_number") or "").strip()
            sequence = _extract_sequence(part_number)

            if sequence is None:
                continue

            row["sequence"] = sequence
            row["sequence_authoritative"] = _is_sequence_authoritative_assignment(raw)

            controlled_like.append(row)

            if row["sequence_authoritative"]:
                sequence_authoritative.append(row)
            else:
                manual_or_custom_controlled_like.append(row)

            if row.get("allocation_batch_id") in LIVE_SEQUENCE_EXCEPTION_BATCHES:
                live_exception_batch_rows.append(row)

        max_sequence = max((row["sequence"] for row in sequence_authoritative), default=0)
        poisoned_max_sequence = max((row["sequence"] for row in controlled_like), default=0)

        payload = {
            "site": site,
            "generated_at_utc": timestamp,
            "live_sequence_exception_batches": sorted(LIVE_SEQUENCE_EXCEPTION_BATCHES),
            "counts": {
                "assignments_total": len(rows),
                "controlled_like": len(controlled_like),
                "sequence_authoritative": len(sequence_authoritative),
                "manual_or_custom_controlled_like": len(manual_or_custom_controlled_like),
                "live_exception_batch_rows": len(live_exception_batch_rows),
            },
            "current_sequence_authoritative_max": max_sequence,
            "legacy_poisoned_max_if_all_controlled_like_counted": poisoned_max_sequence,
            "next_by_family": {
                family: _make_part_number(family, max_sequence + 1) for family in FAMILIES
            },
            "next_if_legacy_poisoned_logic_were_used": {
                family: _make_part_number(family, poisoned_max_sequence + 1) for family in FAMILIES
            },
            "top_sequence_authoritative": sorted(
                sequence_authoritative, key=lambda row: row["sequence"], reverse=True
            )[:25],
            "top_manual_or_custom_controlled_like": sorted(
                manual_or_custom_controlled_like,
                key=lambda row: row["sequence"],
                reverse=True,
            )[:50],
            "live_exception_batch_rows": sorted(
                live_exception_batch_rows, key=lambda row: row["sequence"]
            ),
        }

        evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    finally:
        frappe.destroy()

    print(f"Evidence: {evidence_path}")
    print(f"Sequence-authoritative max: {payload['current_sequence_authoritative_max']}")
    print(f"Legacy poisoned max: {payload['legacy_poisoned_max_if_all_controlled_like_counted']}")
    print("Next by family:")
    for family, part_number in payload["next_by_family"].items():
        print(f"  {family}: {part_number}")
    print("Live exception batches:", ", ".join(payload["live_sequence_exception_batches"]) or "none")

    return 0


def main() -> int:
    args = parse_args()
    return run(args.site, args.sites_path, args.evidence_dir)


if __name__ == "__main__":
    raise SystemExit(main())
