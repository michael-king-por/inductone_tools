#!/usr/bin/env python3
"""Validate the InductOne usability and in-app guidance tranche.

This is a candidate-sandbox validation script. It checks fixture ownership,
Workspace wiring, onboarding records, Client Script presence, builder access
negative gates, and the read-only guidance APIs.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_EVIDENCE_DIR = Path("/mnt/c/hub/frappe-sandbox/validation-evidence")

EXPECTED_CLIENT_SCRIPTS = [
    "InductOne Guidance - Configuration Order",
    "InductOne Guidance - Build Completion",
    "InductOne Guidance - Operations Build",
    "InductOne Guidance - Engineering Signoff",
    "InductOne Guidance - Configuration Option",
]

EXPECTED_CUSTOM_BLOCKS = [
    "Builder Banner",
    "Builder Guidance Panel",
    "Help and contact",
    "Operations Guidance Panel",
    "Engineering Banner Info",
    "Engineering Banner Workflows",
]

EXPECTED_ONBOARDING_STEPS = [
    "Receive an InductOne Build",
    "Download the release package",
    "Upload the builder serial workbook",
    "Respond to a rejected Build Completion",
]

EXTERNAL_BUILDER_USERS = [
    "motion.builder@plusonerobotics.com",
    "lam@plusonerobotics.com",
]

EXPECTED_BUILDER_WORKSPACES = ["Builder Portal"]

BUILDER_VISIBLE_CONFIGURATION_ORDER_STATUSES = {
    "Released",
    "Awaiting Completion",
    "Closed",
    "Completed",
}

TOUCHED_FILES = [
    "inductone_tools/guidance.py",
    "inductone_tools/public/js/guidance.js",
    "inductone_tools/fixtures/custom_html_block.json",
    "inductone_tools/fixtures/module_onboarding.json",
    "inductone_tools/fixtures/onboarding_step.json",
]


def record(results, key, passed, detail=None):
    row = {
        "key": key,
        "status": "PASS" if passed else "FAIL",
        "detail": detail or {},
    }
    print(row["status"], key, json.dumps(row["detail"], default=str))
    results.append(row)


def load_json_fixtures(repo_root: Path):
    fixture_dir = repo_root / "inductone_tools" / "fixtures"
    parsed = {}
    for path in sorted(fixture_dir.glob("*.json")):
        parsed[path.name] = json.loads(path.read_text(encoding="utf-8"))
    return parsed


def contains_em_dash(repo_root: Path):
    hits = []
    for rel in TOUCHED_FILES:
        path = repo_root / rel
        if not path.exists():
            hits.append({"file": rel, "problem": "missing"})
            continue
        text = path.read_text(encoding="utf-8")
        if "\u2014" in text:
            hits.append({"file": rel, "problem": "contains em dash"})
    return hits


def validate_repo_fixtures(repo_root: Path, results):
    fixtures = load_json_fixtures(repo_root)
    record(results, "fixture_json_parse", True, {"files": len(fixtures)})

    client_names = {row.get("name") for row in fixtures["client_script.json"]}
    missing_scripts = sorted(set(EXPECTED_CLIENT_SCRIPTS) - client_names)
    record(results, "client_script_fixture_contains_guidance", not missing_scripts, {"missing": missing_scripts})

    block_names = {row.get("name") for row in fixtures["custom_html_block.json"]}
    missing_blocks = sorted(set(EXPECTED_CUSTOM_BLOCKS) - block_names)
    record(results, "custom_html_block_fixture_contains_guidance", not missing_blocks, {"missing": missing_blocks})

    module_names = {row.get("name") for row in fixtures["module_onboarding.json"]}
    step_names = {row.get("name") for row in fixtures["onboarding_step.json"]}
    record(
        results,
        "onboarding_fixture_contains_builder_sequence",
        "InductOne External Builder Onboarding" in module_names and not (set(EXPECTED_ONBOARDING_STEPS) - step_names),
        {
            "modules": sorted(module_names),
            "missing_steps": sorted(set(EXPECTED_ONBOARDING_STEPS) - step_names),
        },
    )

    workspace = next(row for row in fixtures["workspace.json"] if row.get("name") == "Builder Portal")
    content = workspace.get("content") or ""
    shortcuts = sorted(sc.get("label") for sc in workspace.get("shortcuts", []))
    record(
        results,
        "builder_workspace_fixture_wiring",
        "Builder Guidance Panel" in content and shortcuts == ["Build Completions", "Configuration Orders"],
        {"shortcuts": shortcuts, "has_guidance_panel": "Builder Guidance Panel" in content},
    )

    em_dash_hits = contains_em_dash(repo_root)
    record(results, "controlled_vocabulary_no_em_dash_in_touched_surfaces", not em_dash_hits, {"hits": em_dash_hits})

    wiki_pages = fixtures["wiki_page.json"]
    wiki_content_by_name = {row.get("name"): row.get("content", "") for row in wiki_pages}
    policy_needles = {
        "owner_p1": (
            "inductone-csa-owner-handbook",
            "Catalog and print views show Released options by default. Draft and Deprecated options remain reachable only through explicit filters",
        ),
        "owner_p2": (
            "inductone-csa-owner-handbook",
            "Validation snapshots are generated on scratch builds only; a real Build's snapshot history is a clean audit trail.",
        ),
        "owner_p4": (
            "inductone-csa-owner-handbook",
            "Reviewed = data check: the uploaded workbook parses, serial rows are complete, and serial rows are well-formed. Accepted = evidence check",
        ),
        "config_p1": (
            "3hmhgl7qdu",
            "Policy of record: Catalog and print views show Released options by default.",
        ),
        "asbuilt_p4": (
            "3hmtouafd5",
            "There is no reviewer-not-equal-acceptor constraint.",
        ),
        "owner_w7_fco_intake": (
            "inductone-csa-owner-handbook",
            "Field-side POR Field Change / Deviation intake is distinct from formal pre-release build/configuration deviation control, which is handled procedurally rather than by a separate ERPNext workflow (there is no in-ERPNext Deviation Request DocType).",
        ),
        "deviation_w7_fco_intake": (
            "3hngf036ne",
            "Field-side intake flow -- keep distinct from ERPNext deviation records",
        ),
        "records_w7_fco_register_v2": (
            "inductone-csa-controlled-records-index",
            "Registers/SUP-FCO-R01_FCORegister-v2-0.xlsx",
        ),
        "records_w7_operating_instance_placeholder": (
            "inductone-csa-controlled-records-index",
            "Operating instance location: to be designated",
        ),
    }
    missing_policy = [
        {"key": key, "page": page, "needle": needle}
        for key, (page, needle) in policy_needles.items()
        if needle not in wiki_content_by_name.get(page, "")
    ]
    record(results, "wiki_policy_text_present_p1_p2_p4_w7_fco", not missing_policy, {"missing": missing_policy})

    records_index = wiki_content_by_name.get("inductone-csa-controlled-records-index", "")
    old_fco_register_name = "Registers/SUP-FCO-R01_FCORegister.xlsx"
    w7_records_index_ok = (
        old_fco_register_name not in records_index
        and "Register template" in records_index
        and "Pending released SharePoint link" in records_index
        and "SUP-FCO-R01_FCORegister-v2-0.xlsx" in records_index
        and "Operating instance location: to be designated" in records_index
    )
    record(
        results,
        "records_index_sup_fco_r01_v2_template_row",
        w7_records_index_ok,
        {
            "old_filename_present": old_fco_register_name in records_index,
            "has_register_template_family": "Register template" in records_index,
            "has_placeholder_link": "Pending released SharePoint link" in records_index,
            "has_operating_instance_placeholder": "Operating instance location: to be designated" in records_index,
        },
    )

    deviation_page = wiki_content_by_name.get("3hngf036ne", "")
    fco_intake_needles = [
        "POR Field Change / Deviation intake form (JotForm)",
        "Operations Engineering triages the intake",
        "OPS-FCO-T01",
        "OPS-FCO-T02",
        "OPS-CFG-DEV-01",
        "ECR through the Engineering Change process",
        "ERPNext as-maintained update",
    ]
    missing_fco_needles = [needle for needle in fco_intake_needles if needle not in deviation_page]
    record(
        results,
        "deviation_requests_field_side_intake_flow_encoded",
        not missing_fco_needles,
        {"missing": missing_fco_needles},
    )

    per_option_script = (repo_root / "scripts" / "run_per_option_snapshot_diff_reports.py").read_text(encoding="utf-8")
    lifecycle_script = (repo_root / "scripts" / "run_inductone_csa_lifecycle_smoke.py").read_text(encoding="utf-8")
    user_notes_script = (repo_root / "scripts" / "run_user_notes_roundtrip_validation.py").read_text(encoding="utf-8")
    scratch_ok = (
        "create_scratch_build(frappe, source_build, timestamp)" in per_option_script
        and "--use-requested-build" in per_option_script
        and "create_smoke_build(frappe, source_build, timestamp)" in lifecycle_script
        and "create_scratch_build(source_build)" in user_notes_script
    )
    record(
        results,
        "scratch_build_policy_encoded_for_snapshot_validations",
        scratch_ok,
        {
            "per_option_defaults_to_scratch": "create_scratch_build(frappe, source_build, timestamp)" in per_option_script,
            "per_option_explicit_override_required": "--use-requested-build" in per_option_script,
            "lifecycle_smoke_clones_scratch": "create_smoke_build(frappe, source_build, timestamp)" in lifecycle_script,
            "user_notes_roundtrip_clones_scratch": "create_scratch_build(source_build)" in user_notes_script,
        },
    )


def validate_candidate(site: str, sites_path: str, results):
    import frappe
    from frappe.permissions import has_permission

    frappe.init(site=site, sites_path=sites_path)
    frappe.connect()

    try:
        workspace = frappe.get_doc("Workspace", "Builder Portal")
        roles = sorted(row.role for row in workspace.roles)
        shortcuts = sorted(row.label for row in workspace.shortcuts)
        content = workspace.content or ""
        record(
            results,
            "candidate_builder_workspace_roles_and_links",
            roles == ["InductOne External Builder"] and shortcuts == ["Build Completions", "Configuration Orders"] and "Builder Guidance Panel" in content,
            {"roles": roles, "shortcuts": shortcuts, "has_guidance_panel": "Builder Guidance Panel" in content},
        )

        workspace_rows = []
        for row in frappe.get_all("Workspace", fields=["name", "title", "public", "is_hidden"], order_by="name"):
            doc = frappe.get_doc("Workspace", row.name)
            workspace_rows.append({**row, "roles": [role_row.role for role_row in doc.get("roles")]})

        builder_visibility = {}
        for user in EXTERNAL_BUILDER_USERS:
            user_roles = set(frappe.get_roles(user))
            visible = []
            for row in workspace_rows:
                if row.get("is_hidden"):
                    continue
                roles = set(row.get("roles") or [])
                if not roles or roles & user_roles:
                    visible.append(row["name"])
            builder_visibility[user] = sorted(visible)
        record(
            results,
            "external_builders_see_builder_portal_only",
            all(visible == EXPECTED_BUILDER_WORKSPACES for visible in builder_visibility.values()),
            {"visibility": builder_visibility, "expected": EXPECTED_BUILDER_WORKSPACES},
        )

        missing_blocks = [name for name in EXPECTED_CUSTOM_BLOCKS if not frappe.db.exists("Custom HTML Block", name)]
        record(results, "candidate_custom_html_blocks_exist", not missing_blocks, {"missing": missing_blocks})

        builder_banner = frappe.db.get_value("Custom HTML Block", "Builder Banner", "html") or ""
        builder_guidance_row = frappe.db.get_value("Custom HTML Block", "Builder Guidance Panel", ["html", "script"], as_dict=True) or {}
        builder_guidance = builder_guidance_row.get("html") or ""
        builder_guidance_script = builder_guidance_row.get("script") or ""
        builder_help = frappe.db.get_value("Custom HTML Block", "Help and contact", "html") or ""
        record(
            results,
            "candidate_builder_portal_block_content_current",
            "Builder Portal" in builder_banner
            and "Your assigned InductOne release packages and completion uploads" in builder_banner
            and "data-por-builder-guidance" in builder_guidance
            and "What you need to do" in builder_guidance
            and "Download the release package" in builder_guidance
            and "root_element.querySelector" in builder_guidance_script
            and "ops@plusonerobotics.com" in builder_help
            and "michael.king@plusonerobotics.com" not in builder_help
            and "InductOne \u2014 Operations & Build" not in builder_banner,
            {
                "banner_has_current_title": "Builder Portal" in builder_banner,
                "banner_has_current_subtitle": "Your assigned InductOne release packages and completion uploads" in builder_banner,
                "guidance_mount_present": "data-por-builder-guidance" in builder_guidance,
                "guidance_static_title_present": "What you need to do" in builder_guidance,
                "guidance_static_steps_present": "Download the release package" in builder_guidance,
                "guidance_script_targets_shadow_root": "root_element.querySelector" in builder_guidance_script,
                "help_uses_ops_alias": "ops@plusonerobotics.com" in builder_help,
                "help_uses_personal_email": "michael.king@plusonerobotics.com" in builder_help,
                "banner_has_old_title": "InductOne \u2014 Operations & Build" in builder_banner,
            },
        )

        missing_scripts = [
            name
            for name in EXPECTED_CLIENT_SCRIPTS
            if not frappe.db.exists("Client Script", {"name": name, "enabled": 1})
        ]
        record(results, "candidate_guidance_client_scripts_enabled", not missing_scripts, {"missing": missing_scripts})

        onboarding_exists = frappe.db.exists("Module Onboarding", "InductOne External Builder Onboarding")
        step_missing = [name for name in EXPECTED_ONBOARDING_STEPS if not frappe.db.exists("Onboarding Step", name)]
        record(
            results,
            "candidate_onboarding_records_exist",
            bool(onboarding_exists) and not step_missing,
            {"module_onboarding": bool(onboarding_exists), "missing_steps": step_missing},
        )

        frappe.set_user("motion.builder@plusonerobotics.com")
        builder_allowed = {
            "InductOne Configuration Order": bool(has_permission("InductOne Configuration Order", ptype="read", user=frappe.session.user)),
            "InductOne Build Completion": bool(has_permission("InductOne Build Completion", ptype="read", user=frappe.session.user)),
        }
        builder_denied = {
            "Item": bool(has_permission("Item", ptype="read", user=frappe.session.user)),
            "BOM": bool(has_permission("BOM", ptype="read", user=frappe.session.user)),
            "BOM Export Package": bool(has_permission("BOM Export Package", ptype="read", user=frappe.session.user)),
            "Configured BOM Snapshot": bool(has_permission("Configured BOM Snapshot", ptype="read", user=frappe.session.user)),
        }
        record(
            results,
            "builder_access_model_reasserted",
            all(builder_allowed.values()) and not any(builder_denied.values()),
            {"allowed": builder_allowed, "denied_should_be_false": builder_denied},
        )

        visible_cos = frappe.get_list(
            "InductOne Configuration Order",
            fields=["name", "co_status", "builder_supplier"],
            limit_page_length=500,
            order_by="modified desc",
        )
        invalid_visible_cos = [
            row for row in visible_cos
            if row.get("co_status") not in BUILDER_VISIBLE_CONFIGURATION_ORDER_STATUSES
        ]
        record(
            results,
            "builder_configuration_order_status_visibility",
            not invalid_visible_cos,
            {
                "visible_count": len(visible_cos),
                "allowed_statuses": sorted(BUILDER_VISIBLE_CONFIGURATION_ORDER_STATUSES),
                "invalid_visible": invalid_visible_cos[:20],
            },
        )

        from inductone_tools.external_builder_permissions import restrict_configuration_order_permission

        supplier = None
        supplier_rows = frappe.get_all(
            "User Permission",
            filters={"user": frappe.session.user, "allow": "Supplier"},
            pluck="for_value",
            limit_page_length=10,
        )
        if supplier_rows:
            supplier = supplier_rows[0]
        synthetic_draft = frappe._dict({"builder_supplier": supplier, "co_status": "Draft"})
        synthetic_released = frappe._dict({"builder_supplier": supplier, "co_status": "Released"})
        record(
            results,
            "builder_configuration_order_direct_permission_status_gate",
            supplier
            and restrict_configuration_order_permission(synthetic_draft, frappe.session.user) is False
            and restrict_configuration_order_permission(synthetic_released, frappe.session.user) is True,
            {"supplier": supplier},
        )

        from inductone_tools.guidance import get_builder_portal_guidance, get_form_guidance

        portal_payload = get_builder_portal_guidance()
        invalid_task_statuses = [
            task for task in portal_payload.get("tasks", [])
            if task.get("doctype") == "InductOne Configuration Order"
            and task.get("status") not in BUILDER_VISIBLE_CONFIGURATION_ORDER_STATUSES
        ]
        record(
            results,
            "builder_portal_guidance_payload",
            "tasks" in portal_payload
            and "sections" in portal_payload
            and "empty_state" in portal_payload
            and not invalid_task_statuses,
            {
                "task_count": len(portal_payload.get("tasks", [])),
                "sections": [s.get("title") for s in portal_payload.get("sections", [])],
                "empty_state": portal_payload.get("empty_state"),
                "invalid_task_statuses": invalid_task_statuses,
            },
        )

        sample_completion = {
            "doctype": "InductOne Build Completion",
            "name": "VALIDATION-SAMPLE",
            "status": "Rejected",
            "configuration_order": "VALIDATION-CO",
            "serials": [],
            "review_notes": "Correct workbook and resubmit.",
        }
        form_payload = get_form_guidance("InductOne Build Completion", doc=json.dumps(sample_completion))
        record(
            results,
            "build_completion_form_guidance_payload",
            form_payload.get("status") == "Rejected"
            and "next_action" in form_payload
            and len(form_payload.get("checklist", [])) >= 3,
            {"payload": form_payload},
        )
    finally:
        frappe.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR))
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    results = []
    validate_repo_fixtures(repo_root, results)
    validate_candidate(args.site, args.sites_path, results)

    passed = all(row["status"] == "PASS" for row in results)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "site": args.site,
        "results": results,
        "passed": passed,
    }
    evidence_path = evidence_dir / f"usability_guidance_validation_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print("Evidence:", evidence_path)
    print("GATE:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
