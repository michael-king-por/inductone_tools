#!/usr/bin/env python3
"""Audit Workspace/Dashboard role restrictions for orphaned internal pages."""

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

INTERNAL_ROLES = {
    "Operations Manager",
    "Operations Viewer",
    "Engineering User",
    "Procurement User",
    "Finance Viewer",
    "InductOne Manager",
    "InductOne Process Architect",
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _child_roles(doc) -> list[str]:
    return [row.role for row in doc.get("roles")]


def run(site: str, sites_path: str, evidence_dir: str) -> int:
    import frappe

    frappe.init(site=site, sites_path=sites_path)
    frappe.connect()
    try:
        workspaces: list[dict[str, Any]] = []
        for row in frappe.get_all(
            "Workspace",
            fields=["name", "title", "label", "public", "is_hidden", "module"],
            order_by="sequence_id asc, name asc",
        ):
            doc = frappe.get_doc("Workspace", row.name)
            roles = _child_roles(doc)
            workspaces.append(
                {
                    **dict(row),
                    "roles": roles,
                    "visible_to_any_internal_role": not roles or bool(set(roles) & INTERNAL_ROLES),
                    "orphaned_from_internal_roles": bool(roles) and not bool(set(roles) & INTERNAL_ROLES),
                }
            )

        dashboards: list[dict[str, Any]] = []
        if frappe.db.exists("DocType", "Dashboard"):
            fields = ["name"]
            meta = frappe.get_meta("Dashboard")
            for field in ["dashboard_name", "module", "is_standard"]:
                if meta.has_field(field):
                    fields.append(field)
            for row in frappe.get_all("Dashboard", fields=fields, order_by="name asc"):
                doc = frappe.get_doc("Dashboard", row.name)
                roles = _child_roles(doc) if doc.meta.has_field("roles") else []
                dashboards.append(
                    {
                        **dict(row),
                        "roles": roles,
                        "visible_to_any_internal_role": not roles or bool(set(roles) & INTERNAL_ROLES),
                        "orphaned_from_internal_roles": bool(roles) and not bool(set(roles) & INTERNAL_ROLES),
                    }
                )

        orphaned = [
            {"type": "Workspace", **row}
            for row in workspaces
            if row["orphaned_from_internal_roles"]
        ] + [
            {"type": "Dashboard", **row}
            for row in dashboards
            if row["orphaned_from_internal_roles"]
        ]

        payload = {
            "site": site,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "internal_roles": sorted(INTERNAL_ROLES),
            "summary": {
                "workspaces": len(workspaces),
                "dashboards": len(dashboards),
                "orphaned_from_internal_roles": len(orphaned),
            },
            "workspaces": workspaces,
            "dashboards": dashboards,
            "orphaned": orphaned,
        }
    finally:
        frappe.destroy()

    evidence_path = Path(evidence_dir) / f"workspace_visibility_audit_{_timestamp()}.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(
        "SUMMARY "
        f"workspaces={payload['summary']['workspaces']} "
        f"dashboards={payload['summary']['dashboards']} "
        f"orphaned={payload['summary']['orphaned_from_internal_roles']} "
        f"evidence={evidence_path}"
    )
    for row in orphaned:
        print(f"ORPHAN {row['type']} {row['name']} roles={row.get('roles')}")
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
