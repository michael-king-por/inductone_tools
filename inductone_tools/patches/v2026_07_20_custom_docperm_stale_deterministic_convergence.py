"""Remove stale deterministic Custom DocPerm rows no longer in the fixture.

Frappe fixture sync inserts and updates fixture rows, but it does not delete
database rows when a fixture row is removed. The permission model now treats
``inductone_tools/fixtures/custom_docperm.json`` as authoritative for every
deterministic ``perm_*`` Custom DocPerm row. This patch deletes only
deterministic Custom DocPerm rows whose names are absent from the current
fixture, after snapshotting them for audit/reversal.

It intentionally does not touch standard DocPerm rows, non-deterministic
Custom DocPerm rows, or any DocType other than Custom DocPerm.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import frappe


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
    fixture_names = {
        str(row.get("name"))
        for row in fixture_rows
        if str(row.get("name") or "").startswith(deterministic_prefix)
    }
    if not fixture_names:
        frappe.throw("Stale deterministic Custom DocPerm convergence refused: no fixture names.")

    snapshot_fields = _snapshot_fields()
    db_rows = frappe.get_all(
        "Custom DocPerm",
        fields=snapshot_fields,
        order_by="parent, role, permlevel, name",
        limit_page_length=0,
    )
    rows_to_delete = [
        row
        for row in db_rows
        if str(row.get("name") or "").startswith(deterministic_prefix)
        and str(row.get("name")) not in fixture_names
    ]

    snapshot_path = _write_delete_snapshot(
        deterministic_prefix=deterministic_prefix,
        fixture_row_count=len(fixture_rows),
        database_row_count=len(db_rows),
        snapshot_fields=snapshot_fields,
        rows_to_delete=rows_to_delete,
    )

    for row in rows_to_delete:
        frappe.db.delete("Custom DocPerm", {"name": row["name"]})

    frappe.clear_cache()
    frappe.logger().info(
        "Custom DocPerm stale deterministic convergence deleted %s rows; snapshot=%s",
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
            "Custom DocPerm fixture has multiple name prefixes; refusing stale deterministic convergence: "
            + json.dumps(prefix_counts, default=str)
        )
    return prefix_counts.most_common(1)[0][0]


def _snapshot_fields() -> list[str]:
    columns = set(frappe.db.get_table_columns("Custom DocPerm"))
    fields = [field for field in PREFERRED_SNAPSHOT_FIELDS if field in columns]
    missing_required = [field for field in ("name", "parent", "role", "permlevel") if field not in fields]
    if missing_required:
        frappe.throw(
            "Stale deterministic Custom DocPerm convergence refused; missing required columns: "
            + ", ".join(missing_required)
        )
    return fields


def _write_delete_snapshot(
    *,
    deterministic_prefix: str,
    fixture_row_count: int,
    database_row_count: int,
    snapshot_fields: list[str],
    rows_to_delete: list[dict],
) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_dir = _evidence_dir()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = (
        evidence_dir
        / f"custom_docperm_stale_deterministic_convergence_deleted_{timestamp}.json"
    )
    payload = {
        "site": frappe.local.site,
        "generated_at_utc": timestamp,
        "deterministic_prefix": deterministic_prefix,
        "fixture_row_count": fixture_row_count,
        "database_row_count_before": database_row_count,
        "snapshot_fields": snapshot_fields,
        "delete_count": len(rows_to_delete),
        "deleted_rows": rows_to_delete,
        "guards": [
            "Custom DocPerm only",
            "standard DocPerm never touched",
            "only deterministic fixture-prefix rows considered",
            "rows deleted only when absent from the current fixture by name",
            "non-deterministic DB-local rows are left for separate owner triage/convergence",
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
