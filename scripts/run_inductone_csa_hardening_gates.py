#!/usr/bin/env python3
"""Candidate-only hardening gates for the InductOne CSA lifecycle.

This script closes the validation gaps left after the full happy-path lifecycle
smoke:

1. direct negative coverage for builder acknowledgement,
2. negative release-readiness checks,
3. repeated hierarchy population idempotency.

It is intentionally candidate-only. It creates small synthetic records for
negative readiness checks and may re-populate an existing candidate snapshot's
hierarchy child table. Do not run it against production.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_SITE = "inductone-candidate.localhost"
DEFAULT_SITES_PATH = "/home/michaelplusone/frappe-sandbox/benches/candidate-bench/sites"
DEFAULT_EVIDENCE_DIR = Path("/mnt/c/hub/frappe-sandbox/validation-evidence")
DEFAULT_SOURCE_BUILD = "SAL-ORD-2026-00054-BLD-0225"
EXPECTED_SITE_FRAGMENT = "candidate"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run candidate-only InductOne CSA hardening gates.")
    parser.add_argument("--site", default=DEFAULT_SITE)
    parser.add_argument("--sites-path", default=DEFAULT_SITES_PATH)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--source-build", default=DEFAULT_SOURCE_BUILD)
    parser.add_argument("--snapshot", help="Optional snapshot to use for hierarchy idempotency.")
    parser.add_argument("--confirm-candidate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.confirm_candidate or EXPECTED_SITE_FRAGMENT not in args.site:
        print(
            "Refusing to run mutating hardening gates unless --confirm-candidate "
            f"is supplied and site contains '{EXPECTED_SITE_FRAGMENT}'.",
            file=sys.stderr,
        )
        return 2

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = args.evidence_dir / f"inductone_csa_hardening_gates_{timestamp}.json"

    import frappe

    payload = {
        "site": args.site,
        "source_build": args.source_build,
        "generated_at_utc": timestamp,
        "candidate_only": True,
        "checks": [],
        "created_records": [],
        "failures": [],
    }

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        run_checks(args, frappe, payload, timestamp)
    except Exception as exc:  # noqa: BLE001 - evidence wants exact failure
        payload["failures"].append({
            "type": exc.__class__.__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        })
    finally:
        payload["passed"] = not payload["failures"] and all(row["passed"] for row in payload["checks"])
        evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"Evidence: {evidence_path}")
        print("SUMMARY", "PASS" if payload["passed"] else "FAIL")
        for row in payload["checks"]:
            print("PASS" if row["passed"] else "FAIL", row["label"], summarize(row.get("details")))
        frappe.destroy()

    return 0 if payload["passed"] else 1


def run_checks(args, frappe, payload: dict, timestamp: str) -> None:
    from inductone_tools.builder_release import (
        acknowledge_builder_release,
        check_builder_release_readiness,
        release_to_builder_now,
    )
    from inductone_tools.snapshot.hierarchy import populate_snapshot_hierarchy

    # Gate 1: direct acknowledgement negatives.
    motion_build = find_motion_build_with_configuration_order(frappe)
    if not motion_build:
        add_check(payload, "ack_negative_precondition_motion_build", False, "No Motion build with linked CO found.")
    else:
        add_check(payload, "ack_negative_precondition_motion_build", True, motion_build)

        expect_permission_error(
            payload,
            "acknowledge_denies_operations_viewer_before_doc_lookup",
            "candidate.operations.viewer@example.invalid",
            acknowledge_builder_release,
            "NEGATIVE-ACK-DOES-NOT-EXIST",
        )

        expect_permission_error(
            payload,
            "acknowledge_denies_wrong_external_builder_supplier",
            "lam@plusonerobotics.com",
            acknowledge_builder_release,
            motion_build,
        )

    # Gate 2: release readiness must fail closed for missing prerequisites.
    frappe.set_user("christina.gt@plusonerobotics.com")
    source_build = frappe.get_doc("InductOne Build", args.source_build)

    missing_serial_build = create_negative_build(frappe, source_build, timestamp, "missing-serial")
    payload["created_records"].append({"doctype": "InductOne Build", "name": missing_serial_build.name})
    readiness = check_builder_release_readiness(missing_serial_build.name)
    add_check(
        payload,
        "readiness_fails_missing_serial_snapshot_co_package",
        (not readiness.get("ready"))
        and contains_any(readiness.get("missing", []), "System serial")
        and contains_any(readiness.get("missing", []), "No snapshot")
        and contains_any(readiness.get("missing", []), "No Configuration Order")
        and contains_any(readiness.get("missing", []), "No BOM Export Package"),
        readiness,
    )

    thrown = call_expect_exception(
        release_to_builder_now,
        missing_serial_build.name,
        expected_substring="readiness check failed",
    )
    add_check(payload, "release_to_builder_refuses_incomplete_build", thrown["passed"], thrown)

    missing_top_bom_build = create_negative_build(frappe, source_build, timestamp, "missing-top-bom")
    missing_top_bom_build.top_bom = None
    missing_top_bom_build.save(ignore_permissions=True)
    frappe.db.commit()
    payload["created_records"].append({"doctype": "InductOne Build", "name": missing_top_bom_build.name})
    top_bom_readiness = check_builder_release_readiness(missing_top_bom_build.name)
    add_check(
        payload,
        "readiness_fails_missing_top_bom",
        (not top_bom_readiness.get("ready")) and contains_any(top_bom_readiness.get("missing", []), "Top BOM"),
        top_bom_readiness,
    )

    # Gate 3: hierarchy population is idempotent across repeated calls.
    snapshot_name = args.snapshot or find_latest_snapshot_with_hierarchy(frappe)
    if not snapshot_name:
        add_check(payload, "hierarchy_idempotency_precondition_snapshot", False, "No snapshot with hierarchy rows found.")
    else:
        before = count_hierarchy_rows(frappe, snapshot_name)
        first = populate_snapshot_hierarchy(snapshot_name)
        after_first = count_hierarchy_rows(frappe, snapshot_name)
        second = populate_snapshot_hierarchy(snapshot_name)
        after_second = count_hierarchy_rows(frappe, snapshot_name)
        add_check(
            payload,
            "hierarchy_population_idempotent_repeated_calls",
            before > 0
            and first.get("ok")
            and second.get("ok")
            and after_first == first.get("hierarchy_rows")
            and after_second == second.get("hierarchy_rows")
            and after_first == after_second,
            {
                "snapshot": snapshot_name,
                "before_rows": before,
                "first_result": first,
                "after_first_rows": after_first,
                "second_result": second,
                "after_second_rows": after_second,
            },
        )


def create_negative_build(frappe, source_build, timestamp: str, suffix: str):
    doc = frappe.new_doc("InductOne Build")
    doc.sales_order = source_build.sales_order
    doc.sales_order_item_idx = source_build.sales_order_item_idx
    doc.sales_order_item_row_name = getattr(source_build, "sales_order_item_row_name", None)
    doc.customer_project_label = f"Candidate negative release readiness {suffix} {timestamp}"
    doc.top_item = source_build.top_item
    doc.top_bom = source_build.top_bom
    doc.orientation = source_build.orientation or "Right-Hand"
    doc.builder_supplier = source_build.builder_supplier
    doc.builder_po_reference = f"Candidate negative readiness {suffix}"
    doc.build_status = "DRAFT"
    doc.completion_status = "Open"
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    frappe.db.commit()
    return doc


def find_motion_build_with_configuration_order(frappe) -> str | None:
    rows = frappe.db.sql(
        """
        select b.name
        from `tabInductOne Build` b
        inner join `tabInductOne Configuration Order` co
          on co.name = b.latest_config_order
        where b.builder_supplier = 'Motion Controls'
        order by b.modified desc
        limit 1
        """,
        as_dict=True,
    )
    return rows[0]["name"] if rows else None


def find_latest_snapshot_with_hierarchy(frappe) -> str | None:
    rows = frappe.db.sql(
        """
        select s.name
        from `tabConfigured BOM Snapshot` s
        where exists (
            select 1
            from `tabConfigured BOM Snapshot Hierarchy` h
            where h.parent = s.name
        )
        order by s.modified desc
        limit 1
        """,
        as_dict=True,
    )
    return rows[0]["name"] if rows else None


def count_hierarchy_rows(frappe, snapshot_name: str) -> int:
    return frappe.db.count(
        "Configured BOM Snapshot Hierarchy",
        {
            "parent": snapshot_name,
            "parenttype": "Configured BOM Snapshot",
            "parentfield": "hierarchy",
        },
    )


def expect_permission_error(payload: dict, label: str, user: str, func, *args, **kwargs) -> None:
    import frappe

    frappe.set_user(user)
    raised = None
    try:
        func(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001 - record exact class
        raised = exc
    finally:
        frappe.db.rollback()
        frappe.local.message_log = []

    add_check(
        payload,
        label,
        isinstance(raised, frappe.PermissionError),
        {
            "user": user,
            "expected_exception": "PermissionError",
            "actual_exception": raised.__class__.__name__ if raised else "NO_EXCEPTION",
            "message": str(raised) if raised else None,
        },
    )


def call_expect_exception(func, *args, expected_substring: str | None = None, **kwargs) -> dict:
    import frappe

    raised = None
    try:
        func(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001 - record exact class
        raised = exc
    finally:
        frappe.db.rollback()
        frappe.local.message_log = []

    message = str(raised) if raised else ""
    return {
        "passed": bool(raised) and (not expected_substring or expected_substring.lower() in message.lower()),
        "actual_exception": raised.__class__.__name__ if raised else "NO_EXCEPTION",
        "message": message,
        "expected_substring": expected_substring,
    }


def contains_any(messages: list[str], needle: str) -> bool:
    return any(needle.lower() in str(message).lower() for message in messages)


def add_check(payload: dict, label: str, passed: bool, details=None) -> None:
    payload["checks"].append({
        "label": label,
        "passed": bool(passed),
        "details": details,
    })
    print("PASS" if passed else "FAIL", label, summarize(details), flush=True)


def summarize(details) -> str:
    if details is None:
        return ""
    if isinstance(details, str):
        return details[:400]
    return json.dumps(details, default=str, sort_keys=True)[:700]


if __name__ == "__main__":
    sys.exit(main())
