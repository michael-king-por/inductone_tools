#!/usr/bin/env python3
"""Candidate-only release-gate negative matrix for InductOne CSA.

This script creates small synthetic candidate records and proves the builder
release readiness gate fails closed for procedural gaps that are easy to miss
when only the happy path is tested.

It intentionally mutates candidate only. Do not run against production.
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
    parser = argparse.ArgumentParser(description="Run candidate-only InductOne CSA release gate matrix.")
    parser.add_argument("--site", default=DEFAULT_SITE)
    parser.add_argument("--sites-path", default=DEFAULT_SITES_PATH)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--source-build", default=DEFAULT_SOURCE_BUILD)
    parser.add_argument("--manager-user", default="christina.gt@plusonerobotics.com")
    parser.add_argument("--confirm-candidate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.confirm_candidate or EXPECTED_SITE_FRAGMENT not in args.site:
        print(
            "Refusing to run mutating release gate matrix unless --confirm-candidate "
            f"is supplied and site contains '{EXPECTED_SITE_FRAGMENT}'.",
            file=sys.stderr,
        )
        return 2

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = args.evidence_dir / f"inductone_csa_release_gate_matrix_{timestamp}.json"

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
        frappe.set_user(args.manager_user)
        run_matrix(args, frappe, payload, timestamp)
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


def run_matrix(args, frappe, payload: dict, timestamp: str) -> None:
    from inductone_tools.builder_release import check_builder_release_readiness, release_to_builder_now

    source = frappe.get_doc("InductOne Build", args.source_build)

    # Gate 1: selected Draft configuration option is explicitly blocked.
    draft_option = create_draft_option(frappe, timestamp)
    payload["created_records"].append({"doctype": "InductOne Configuration Option", "name": draft_option.name})

    draft_build = create_matrix_build(frappe, source, timestamp, "draft-option")
    co = create_matrix_co(frappe, draft_build, timestamp, selected_option=draft_option)
    draft_build.latest_config_order = co.name
    draft_build.save(ignore_permissions=True)
    frappe.db.commit()
    payload["created_records"].extend([
        {"doctype": "InductOne Build", "name": draft_build.name},
        {"doctype": "InductOne Configuration Order", "name": co.name},
    ])
    readiness = check_builder_release_readiness(draft_build.name)
    add_check(
        payload,
        "release_gate_blocks_selected_draft_configuration_option",
        (not readiness.get("ready"))
        and contains(readiness.get("missing", []), draft_option.option_code)
        and contains(readiness.get("missing", []), "Only Released configuration options"),
        readiness,
    )

    thrown = call_expect_release_failure(release_to_builder_now, draft_build.name)
    add_check(
        payload,
        "release_method_refuses_selected_draft_configuration_option",
        thrown["passed"] and draft_option.option_code in thrown["message"],
        thrown,
    )

    # Gate 2: missing Top Item signoff is reported by the release gate.
    top_item_build = create_matrix_build(frappe, source, timestamp, "top-item-nosignoff")
    top_item_build.top_item = f"CANDIDATE-NO-SIGNOFF-ITEM-{timestamp}"
    top_item_build.flags.ignore_links = True
    top_item_build.save(ignore_permissions=True)
    frappe.db.commit()
    payload["created_records"].append({"doctype": "InductOne Build", "name": top_item_build.name})
    readiness = check_builder_release_readiness(top_item_build.name)
    add_check(
        payload,
        "release_gate_reports_missing_top_item_signoff",
        (not readiness.get("ready")) and contains(readiness.get("missing", []), "Item CANDIDATE-NO-SIGNOFF-ITEM"),
        readiness,
    )

    # Gate 3: missing Product Bundle signoff is reported.  The synthetic
    # Product Bundle intentionally uses an ignored-link synthetic new_item_code
    # so this candidate mutation cannot collide with real product bundles.
    pb_build = create_matrix_build(frappe, source, timestamp, "product-bundle-nosignoff")
    synthetic_top_item = f"CANDIDATE-PB-NO-SIGNOFF-{timestamp}"
    pb_build.top_item = synthetic_top_item
    pb_build.flags.ignore_links = True
    pb_build.save(ignore_permissions=True)
    pb = create_synthetic_product_bundle(frappe, synthetic_top_item, source.top_item, timestamp)
    payload["created_records"].extend([
        {"doctype": "InductOne Build", "name": pb_build.name},
        {"doctype": "Product Bundle", "name": pb.name},
    ])
    readiness = check_builder_release_readiness(pb_build.name)
    add_check(
        payload,
        "release_gate_reports_missing_product_bundle_signoff",
        (not readiness.get("ready")) and contains(readiness.get("missing", []), f"Product Bundle {pb.name}"),
        readiness,
    )


def create_matrix_build(frappe, source, timestamp: str, suffix: str):
    doc = frappe.new_doc("InductOne Build")
    doc.sales_order = source.sales_order
    doc.sales_order_item_idx = source.sales_order_item_idx
    doc.sales_order_item_row_name = getattr(source, "sales_order_item_row_name", None)
    doc.customer_project_label = f"Candidate release gate matrix {suffix} {timestamp}"
    doc.top_item = source.top_item
    doc.top_bom = source.top_bom
    doc.orientation = source.orientation or "Right-Hand"
    doc.builder_supplier = source.builder_supplier
    doc.builder_po_reference = f"Candidate release gate matrix {suffix}"
    safe_suffix = "".join(ch for ch in suffix.upper() if ch.isalnum())[:6]
    doc.system_serial = f"IND-GATE-{timestamp[-7:-1]}-{safe_suffix}"
    doc.build_status = "DRAFT"
    doc.completion_status = "Open"
    doc.flags.ignore_links = True
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    frappe.db.commit()
    return doc


def create_matrix_co(frappe, build, timestamp: str, selected_option):
    co = frappe.new_doc("InductOne Configuration Order")
    co.inductone_build = build.name
    co.co_status = "Draft"
    co.config_order_rev = 1
    co.generated_at = frappe.utils.now_datetime()
    co.generated_by = frappe.session.user
    co.builder_supplier = build.builder_supplier
    co.sales_order = build.sales_order
    co.sales_order_item_idx = build.sales_order_item_idx
    co.top_item = build.top_item
    co.top_bom = build.top_bom
    co.orientation = build.orientation
    co.system_serial = build.system_serial
    co.append("selected_options", {
        "option": selected_option.name,
        "option_code": selected_option.option_code,
        "option_name": selected_option.option_name,
        "option_category": selected_option.option_category,
    })
    co.flags.ignore_links = True
    co.insert(ignore_permissions=True, ignore_mandatory=True)
    frappe.db.commit()
    return co


def create_draft_option(frappe, timestamp: str):
    code = f"CANDIDATE-DRAFT-GATE-{timestamp}"
    doc = frappe.new_doc("InductOne Configuration Option")
    doc.option_code = code
    doc.option_name = f"Candidate Draft Gate {timestamp}"
    doc.option_category = "Other"
    doc.option_group = f"Candidate Gate {timestamp}"
    doc.option_group_required = 0
    doc.is_default_selection = 0
    doc.is_active = 1
    doc.status = "Draft"
    doc.mapping_status = "Complete"
    doc.owner_role = "Ops"
    doc.sort_order = 99999
    doc.internal_notes = "Candidate-only release gate matrix draft option."
    doc.builder_description = "Candidate-only draft option; must be blocked from builder release."
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    frappe.db.commit()
    return doc


def create_synthetic_product_bundle(frappe, new_item_code: str, component_item_code: str, timestamp: str):
    doc = frappe.new_doc("Product Bundle")
    doc.new_item_code = new_item_code
    doc.description = f"Candidate release gate matrix Product Bundle {timestamp}"
    doc.append("items", {
        "item_code": component_item_code,
        "qty": 1,
        "description": "Candidate release gate matrix component",
    })
    doc.flags.ignore_links = True
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    frappe.db.commit()
    return doc


def call_expect_release_failure(func, *args, **kwargs) -> dict:
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
        "passed": bool(raised) and "readiness check failed" in message.lower(),
        "actual_exception": raised.__class__.__name__ if raised else "NO_EXCEPTION",
        "message": message,
    }


def contains(messages: list[str], needle: str) -> bool:
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
