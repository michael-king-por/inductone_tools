#!/usr/bin/env python3
"""Inventory InductOne Configuration Option status values before status cleanup."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_EVIDENCE_DIR = Path("/mnt/c/hub/frappe-sandbox/validation-evidence")
ALLOWED_PRE_CLEANUP_STATUSES = {"Draft", "Released", "Deprecated", "Defined-Ops"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    import frappe
    from inductone_tools.balloon_scoped_options import option_codes

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = args.evidence_dir / f"configuration_option_status_inventory_{timestamp}.json"

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        rows = frappe.get_all(
            "InductOne Configuration Option",
            fields=["name", "option_code", "status", "workflow_state"],
            order_by="option_code asc",
        )
        counts = Counter(row.status for row in rows)
        dev_codes = set(option_codes())
        defined_ops = [row for row in rows if row.status == "Defined-Ops"]
        defined_product = [row for row in rows if row.status == "Defined-Product"]
        unexpected_status_rows = [
            row for row in rows if (row.status or "") not in ALLOWED_PRE_CLEANUP_STATUSES
        ]
        defined_ops_non_dev = [
            row for row in defined_ops if (row.option_code or row.name) not in dev_codes
        ]
        workflows = frappe.get_all(
            "Workflow",
            filters={"document_type": "InductOne Configuration Option"},
            fields=["name", "document_type", "is_active"],
        )
        workflow_state_counts = Counter(row.workflow_state for row in rows)
    finally:
        frappe.destroy()

    passed = (
        not unexpected_status_rows
        and not defined_product
        and not defined_ops_non_dev
        and len(defined_ops) == len(dev_codes)
    )
    payload = {
        "site": args.site,
        "generated_at_utc": timestamp,
        "passed": passed,
        "status_counts": dict(sorted(counts.items())),
        "workflow_state_counts": {str(k): v for k, v in sorted(workflow_state_counts.items(), key=lambda kv: str(kv[0]))},
        "defined_ops_count": len(defined_ops),
        "defined_ops_codes": sorted(row.option_code or row.name for row in defined_ops),
        "defined_ops_non_dev": [dict(row) for row in defined_ops_non_dev],
        "defined_product": [dict(row) for row in defined_product],
        "unexpected_status_rows": [dict(row) for row in unexpected_status_rows],
        "configuration_option_workflows": [dict(row) for row in workflows],
    }
    evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print(("PASS" if passed else "FAIL"), "configuration option status inventory")
    print(json.dumps(payload["status_counts"], indent=2))
    print(f"Workflows: {payload['configuration_option_workflows']}")
    print(f"Evidence: {evidence_path}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
