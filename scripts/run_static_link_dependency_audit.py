#!/usr/bin/env python3
"""Static mandatory-Link dependency audit for hardened roles.

For each hardened role, this script finds DocTypes where that role has
write/create/submit authority, then checks mandatory Link fields on those
DocTypes. If the same role lacks read access to the linked target DocType, the
dependency is flagged for review.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_EVIDENCE_DIR = os.environ.get(
    "VALIDATION_EVIDENCE_DIR",
    "/mnt/c/hub/frappe-sandbox/validation-evidence",
)

HARDENED_ROLES = [
    "Operations Manager",
    "Inventory Operator",
    "Gripper Manufacturer",
    "Procurement User",
    "Operations Viewer",
    "Finance Viewer",
    "Engineering User",
    "InductOne Manager",
    "InductOne Process Architect",
]

ACTION_BITS = ["write", "create", "submit"]


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _permission_rows(frappe, doctype: str, role: str) -> list[dict[str, Any]]:
    fields = ["read", "write", "create", "submit", "cancel", "delete", "permlevel"]
    rows: list[dict[str, Any]] = []
    for table in ["DocPerm", "Custom DocPerm"]:
        if not frappe.db.exists("DocType", table):
            continue
        rows.extend(
            dict(row, source=table)
            for row in frappe.get_all(
                table,
                filters={"parent": doctype, "role": role, "permlevel": 0},
                fields=fields,
            )
        )
    return rows


def _role_has_any_action(frappe, doctype: str, role: str) -> bool:
    for row in _permission_rows(frappe, doctype, role):
        if any(int(row.get(bit) or 0) for bit in ACTION_BITS):
            return True
    return False


def _role_can_read(frappe, doctype: str, role: str) -> bool:
    for row in _permission_rows(frappe, doctype, role):
        if int(row.get("read") or 0):
            return True
    return False


def _mandatory_link_fields(meta) -> list[dict[str, str]]:
    fields = []
    for field in meta.fields:
        if (
            field.fieldtype == "Link"
            and field.reqd
            and field.options
            and field.options not in {"[Select]", "DocType"}
        ):
            fields.append(
                {
                    "fieldname": field.fieldname,
                    "label": field.label,
                    "target_doctype": field.options,
                }
            )
    return fields


def run(site: str, sites_path: str, evidence_dir: str) -> int:
    import frappe

    frappe.init(site=site, sites_path=sites_path)
    frappe.connect()
    try:
        doctypes = frappe.get_all("DocType", pluck="name", order_by="name asc")
        rows: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []

        for role in HARDENED_ROLES:
            for doctype in doctypes:
                if not _role_has_any_action(frappe, doctype, role):
                    continue
                meta = frappe.get_meta(doctype)
                links = _mandatory_link_fields(meta)
                for link in links:
                    target = link["target_doctype"]
                    target_exists = bool(frappe.db.exists("DocType", target))
                    can_read = target_exists and _role_can_read(frappe, target, role)
                    row = {
                        "role": role,
                        "source_doctype": doctype,
                        **link,
                        "target_exists": target_exists,
                        "role_can_read_target": can_read,
                        "missing_read_dependency": not can_read,
                    }
                    rows.append(row)
                    if row["missing_read_dependency"]:
                        missing.append(row)

        payload = {
            "site": site,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "roles": HARDENED_ROLES,
            "summary": {
                "checked_dependencies": len(rows),
                "missing_read_dependencies": len(missing),
            },
            "dependencies": rows,
            "missing": missing,
        }
    finally:
        frappe.destroy()

    evidence_path = Path(evidence_dir) / f"static_link_dependency_audit_{_timestamp()}.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(
        "SUMMARY "
        f"checked={payload['summary']['checked_dependencies']} "
        f"missing={payload['summary']['missing_read_dependencies']} "
        f"evidence={evidence_path}"
    )
    for row in missing[:50]:
        print(
            "MISSING "
            f"{row['role']} {row['source_doctype']}.{row['fieldname']} -> {row['target_doctype']}"
        )
    if len(missing) > 50:
        print(f"... {len(missing) - 50} more missing dependencies in evidence JSON")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--evidence-dir", default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()
    return run(args.site, args.sites_path, args.evidence_dir)


if __name__ == "__main__":
    sys.exit(main())
