#!/usr/bin/env python3
"""Load the reviewed balloon-scoped InductOne option catalog.

This is intended for candidate validation first. Production use requires human
approval of the validation report and should be run only after the code/fixture
branch has been deployed there.
"""

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


def main() -> int:
    args = parse_args()

    import frappe
    from inductone_tools.balloon_scoped_options import catalog_specs, upsert_catalog

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = args.evidence_dir / f"balloon_scoped_option_loader_{timestamp}.json"

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        results = upsert_catalog(frappe)
        payload = {
            "site": args.site,
            "generated_at_utc": timestamp,
            "option_count": len(results),
            "mapping_count": sum(row["mapping_count"] for row in results),
            "catalog_specs": [
                {
                    "option_code": spec["option_code"],
                    "option_group": spec["option_group"],
                    "is_default_selection": spec["is_default_selection"],
                    "mapping_count": len(spec["mappings_table"]),
                }
                for spec in catalog_specs()
            ],
            "results": results,
        }
        evidence_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    finally:
        frappe.destroy()

    print(f"Loaded {len(results)} balloon-scoped options.")
    for row in results:
        print(f"PASS {row['option_code']}: {row['action']} {row['name']} ({row['mapping_count']} mappings)")
    print(f"Evidence: {evidence_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

