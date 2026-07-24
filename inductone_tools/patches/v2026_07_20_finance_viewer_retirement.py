"""Retire Finance Viewer and converge report access to Global Viewer.

Finance/audit broad read visibility is now served by Global Viewer. Fixture
removal does not delete database rows, so this patch removes stale Finance
Viewer assignments/permissions/report grants with a pre-delete evidence
snapshot, then ensures Global Viewer can open Report records.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import frappe


RETIRED_ROLE = "Finance Viewer"
GLOBAL_VIEWER = "Global Viewer"


def execute() -> None:
    _ensure_global_viewer_role()

    snapshot = {
        "site": frappe.local.site,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "retired_role": RETIRED_ROLE,
        "custom_docperm_rows": _rows("Custom DocPerm", {"role": RETIRED_ROLE}),
        "has_role_rows": _rows("Has Role", {"role": RETIRED_ROLE}),
        "role_profile": _doc_snapshot("Role Profile", RETIRED_ROLE),
        "role": _doc_snapshot("Role", RETIRED_ROLE),
    }
    snapshot_path = _write_snapshot(snapshot)

    frappe.db.delete("Custom DocPerm", {"role": RETIRED_ROLE})
    frappe.db.delete("Has Role", {"role": RETIRED_ROLE})

    if frappe.db.exists("Role Profile", RETIRED_ROLE):
        frappe.delete_doc("Role Profile", RETIRED_ROLE, ignore_permissions=True)

    if frappe.db.exists("Role", RETIRED_ROLE):
        frappe.delete_doc("Role", RETIRED_ROLE, ignore_permissions=True)

    reports_updated = _ensure_global_viewer_report_roles()

    frappe.clear_cache()
    frappe.logger().info(
        "Retired %s; snapshot=%s; reports updated for %s=%s",
        RETIRED_ROLE,
        snapshot_path,
        GLOBAL_VIEWER,
        reports_updated,
    )


def _rows(doctype: str, filters: dict) -> list[dict]:
    fields = ["*"]
    return frappe.get_all(doctype, filters=filters, fields=fields, limit_page_length=0)


def _doc_snapshot(doctype: str, name: str) -> dict | None:
    if not frappe.db.exists(doctype, name):
        return None
    return frappe.get_doc(doctype, name).as_dict()


def _write_snapshot(payload: dict) -> str:
    evidence_dir = _evidence_dir()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / (
        f"finance_viewer_retirement_deleted_{payload['generated_at_utc']}.json"
    )
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return str(path)


def _evidence_dir() -> Path:
    explicit = frappe.conf.get("validation_evidence_dir")
    if explicit:
        return Path(explicit)

    candidate_path = Path("/mnt/c/hub/frappe-sandbox/validation-evidence")
    if candidate_path.exists() or Path("/mnt/c/hub").exists():
        return candidate_path

    return Path(frappe.get_site_path("private", "files", "validation-evidence"))


def _ensure_global_viewer_role() -> None:
    if frappe.db.exists("Role", GLOBAL_VIEWER):
        return

    role = frappe.new_doc("Role")
    role.role_name = GLOBAL_VIEWER
    role.desk_access = 1
    role.is_custom = 1
    role.insert(ignore_permissions=True)


def _ensure_global_viewer_report_roles() -> int:
    updated = 0
    for report_name in frappe.get_all("Report", pluck="name", limit_page_length=0):
        if frappe.db.exists(
            "Has Role",
            {
                "parent": report_name,
                "parenttype": "Report",
                "parentfield": "roles",
                "role": GLOBAL_VIEWER,
            },
        ):
            continue

        max_idx = (
            frappe.db.sql(
                """
                select coalesce(max(idx), 0)
                from `tabHas Role`
                where parent = %s
                  and parenttype = 'Report'
                  and parentfield = 'roles'
                """,
                report_name,
            )[0][0]
            or 0
        )
        frappe.get_doc(
            {
                "doctype": "Has Role",
                "parent": report_name,
                "parenttype": "Report",
                "parentfield": "roles",
                "idx": int(max_idx) + 1,
                "role": GLOBAL_VIEWER,
            }
        ).insert(ignore_permissions=True)
        updated += 1
    return updated
