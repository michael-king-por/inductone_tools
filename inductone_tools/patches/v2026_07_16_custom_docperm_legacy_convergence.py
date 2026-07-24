"""Converge legacy Custom DocPerm rows to deterministic fixture ownership.

This patch removes only DB-local Custom DocPerm rows when an equivalent
deterministic fixture-owned row exists for the same (parent, role, permlevel)
key. It keys off the fixture, not the current database, because Frappe runs
patches before fixture import during `bench migrate`.

It does not touch standard DocPerm rows, deterministic fixture rows, or any
legacy Custom DocPerm key that is not represented by the fixture.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import frappe


KEY_FIELDS = ("parent", "role", "permlevel")
PREFERRED_SNAPSHOT_FIELDS = [
    "name",
    "owner",
    "creation",
    "modified",
    "modified_by",
    "docstatus",
    "idx",
    "parent",
    "parentfield",
    "parenttype",
    "role",
    "permlevel",
    "if_owner",
    "select",
    "read",
    "write",
    "create",
    "delete",
    "submit",
    "cancel",
    "amend",
    "report",
    "export",
    "import",
    "share",
    "print",
    "email",
]


def execute() -> None:
    fixture_rows = _load_fixture_rows()
    deterministic_prefix = _deterministic_prefix_from_fixture(fixture_rows)

    deterministic_keys = {
        _key(row)
        for row in fixture_rows
        if str(row.get("name") or "").startswith(deterministic_prefix)
    }
    deterministic_names = {
        str(row.get("name"))
        for row in fixture_rows
        if str(row.get("name") or "").startswith(deterministic_prefix)
    }

    if not deterministic_keys or not deterministic_names:
        frappe.throw(
            "Custom DocPerm convergence refused to run: no deterministic fixture rows found."
        )

    snapshot_fields = _snapshot_fields()
    db_rows = frappe.get_all(
        "Custom DocPerm",
        fields=snapshot_fields,
        order_by="parent, role, permlevel, name",
    )

    db_by_key = defaultdict(list)
    for row in db_rows:
        db_by_key[_key(row)].append(row)

    rows_to_delete = []
    for key, rows in db_by_key.items():
        if key not in deterministic_keys:
            continue
        for row in rows:
            name = str(row.get("name") or "")
            if name in deterministic_names or name.startswith(deterministic_prefix):
                continue
            rows_to_delete.append(row)

    snapshot_path = _write_delete_snapshot(
        deterministic_prefix=deterministic_prefix,
        fixture_row_count=len(fixture_rows),
        database_row_count=len(db_rows),
        deterministic_key_count=len(deterministic_keys),
        snapshot_fields=snapshot_fields,
        rows_to_delete=rows_to_delete,
    )

    for row in rows_to_delete:
        # Patch helper only: direct DB delete is intentional here. This is not a
        # whitelisted method and never uses ignore_permissions=True.
        frappe.db.delete("Custom DocPerm", {"name": row["name"]})

    frappe.clear_cache()
    frappe.logger().info(
        "Custom DocPerm legacy convergence deleted %s rows; snapshot=%s",
        len(rows_to_delete),
        snapshot_path,
    )


def _load_fixture_rows() -> list[dict]:
    fixture_path = Path(
        frappe.get_app_path("inductone_tools", "fixtures", "custom_docperm.json")
    )
    with fixture_path.open(encoding="utf-8") as handle:
        rows = json.load(handle)
    if not isinstance(rows, list):
        frappe.throw(f"Expected list in {fixture_path}")
    return rows


def _deterministic_prefix_from_fixture(rows: list[dict]) -> str:
    names = [str(row.get("name") or "") for row in rows if row.get("name")]
    if not names:
        frappe.throw("Custom DocPerm fixture has no named rows.")

    prefix_counts = Counter()
    for name in names:
        if "_" not in name:
            frappe.throw(
                f"Custom DocPerm fixture row {name!r} does not contain a deterministic prefix separator."
            )
        prefix_counts[name.split("_", 1)[0] + "_"] += 1

    if len(prefix_counts) != 1:
        frappe.throw(
            "Custom DocPerm fixture has multiple name prefixes; refusing legacy convergence: "
            + json.dumps(prefix_counts, default=str)
        )

    prefix, count = prefix_counts.most_common(1)[0]
    if count != len(names):
        frappe.throw(
            "Custom DocPerm fixture prefix discovery did not cover all named rows; refusing legacy convergence."
        )
    return prefix


def _key(row: dict) -> tuple:
    return tuple(row.get(field) for field in KEY_FIELDS)


def _snapshot_fields() -> list[str]:
    columns = set(frappe.db.get_table_columns("Custom DocPerm"))
    fields = [field for field in PREFERRED_SNAPSHOT_FIELDS if field in columns]
    missing_required = [field for field in ("name", "parent", "role", "permlevel") if field not in fields]
    if missing_required:
        frappe.throw(
            "Custom DocPerm convergence refused to run; missing required columns: "
            + ", ".join(missing_required)
        )
    return fields


def _write_delete_snapshot(
    *,
    deterministic_prefix: str,
    fixture_row_count: int,
    database_row_count: int,
    deterministic_key_count: int,
    snapshot_fields: list[str],
    rows_to_delete: list[dict],
) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_dir = _evidence_dir()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = (
        evidence_dir / f"custom_docperm_legacy_convergence_deleted_{timestamp}.json"
    )
    payload = {
        "site": frappe.local.site,
        "generated_at_utc": timestamp,
        "deterministic_prefix": deterministic_prefix,
        "fixture_row_count": fixture_row_count,
        "database_row_count_before": database_row_count,
        "deterministic_key_count": deterministic_key_count,
        "snapshot_fields": snapshot_fields,
        "delete_count": len(rows_to_delete),
        "deleted_rows": rows_to_delete,
        "guards": [
            "Custom DocPerm only",
            "standard DocPerm never touched",
            "deterministic fixture-named rows never deleted",
            "legacy rows deleted only when a deterministic fixture-owned row exists for the same parent/role/permlevel key",
            "fixture keys are authoritative because patches run before fixture import",
            "legacy rows with no deterministic equivalent left untouched",
        ],
    }
    snapshot_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return str(snapshot_path)


def _evidence_dir() -> Path:
    explicit = frappe.conf.get("validation_evidence_dir")
    if explicit:
        return Path(explicit)

    candidate_path = Path("/mnt/c/hub/frappe-sandbox/validation-evidence")
    if candidate_path.exists() or Path("/mnt/c/hub").exists():
        return candidate_path

    return Path(frappe.get_site_path("private", "files", "validation-evidence"))
