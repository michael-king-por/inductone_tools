#!/usr/bin/env python3
"""
Validate the server-side InductOne Build Completion lifecycle in a Frappe site.

Run from inside a Frappe bench's Python environment:

    env/bin/python /path/to/inductone_tools/scripts/validate_build_completion_lifecycle.py \
      --bench /path/to/frappe-bench \
      --site inductone-candidate.localhost

The test deliberately bypasses mandatory-field checks so it can isolate the
state-machine validator. It still runs the DocType validate hook.

All inserted records are rolled back; the script should leave no persistent
Build Completion records behind.
"""

from __future__ import annotations

import argparse
import json
import os
import traceback

import frappe


DOCTYPE = "InductOne Build Completion"


def result(name: str, ok: bool, detail: str | None = None) -> dict:
    return {
        "test": name,
        "ok": bool(ok),
        "detail": detail or "",
    }


def expect_pass(name, fn):
    try:
        detail = fn()
        frappe.db.rollback()
        return result(name, True, detail)
    except Exception as exc:
        frappe.db.rollback()
        return result(name, False, f"{type(exc).__name__}: {exc}")


def expect_fail(name, fn, contains=None):
    try:
        detail = fn()
        frappe.db.rollback()
        return result(name, False, f"unexpected pass: {detail}")
    except Exception as exc:
        frappe.db.rollback()
        message = str(exc)
        if contains and contains not in message:
            return result(name, False, f"failed, but wrong message: {type(exc).__name__}: {message}")
        return result(name, True, f"{type(exc).__name__}: {message}")


def make_completion(status: str):
    doc = frappe.new_doc(DOCTYPE)
    doc.status = status
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc


def run_validation(bench: str, site: str) -> dict:
    os.chdir(bench)
    frappe.init(site=site, sites_path=os.path.join(bench, "sites"))
    frappe.connect()
    frappe.set_user("Administrator")

    from inductone_tools.build_completion import _COMPLETION_TRANSITIONS

    out = {
        "site": site,
        "doctype": DOCTYPE,
        "transition_table": {k: sorted(v) for k, v in _COMPLETION_TRANSITIONS.items()},
        "tests": [],
    }

    out["tests"].append(expect_pass(
        "new Draft completion is allowed",
        lambda: f"created {make_completion('Draft').name} as Draft",
    ))

    def draft_to_submitted():
        doc = make_completion("Draft")
        name = doc.name
        doc.status = "Submitted"
        doc.save(ignore_permissions=True)
        return f"{name}: Draft -> Submitted"

    out["tests"].append(expect_pass("Draft -> Submitted is allowed", draft_to_submitted))

    out["tests"].append(expect_pass(
        "new Submitted completion remains allowed",
        lambda: f"created {make_completion('Submitted').name} as Submitted",
    ))

    out["tests"].append(expect_fail(
        "new Reviewed completion is blocked",
        lambda: make_completion("Reviewed").name,
        "New Build Completions must start",
    ))

    def submitted_to_draft():
        doc = make_completion("Submitted")
        doc.status = "Draft"
        doc.save(ignore_permissions=True)
        return doc.name

    out["tests"].append(expect_fail(
        "Submitted -> Draft is blocked",
        submitted_to_draft,
        "Invalid Build Completion transition",
    ))

    def submitted_to_reviewed_without_serials():
        doc = make_completion("Submitted")
        doc.status = "Reviewed"
        doc.save(ignore_permissions=True)
        return doc.name

    out["tests"].append(expect_fail(
        "Submitted -> Reviewed without serials is blocked",
        submitted_to_reviewed_without_serials,
        "at least one serial row is required",
    ))

    def direct_accept_is_blocked():
        doc = make_completion("Submitted")
        doc.append("serials", {"serial_number": "TEST-SERIAL-001"})
        doc.status = "Reviewed"
        doc.save(ignore_permissions=True)
        doc.status = "Accepted"
        doc.save(ignore_permissions=True)
        return doc.name

    out["tests"].append(expect_fail(
        "direct Reviewed -> Accepted is still blocked",
        direct_accept_is_blocked,
        "only be set to 'Accepted' through",
    ))

    out["all_passed"] = all(t["ok"] for t in out["tests"])
    frappe.destroy()
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", required=True, help="Absolute path to the Frappe bench.")
    parser.add_argument("--site", required=True, help="Site name to validate.")
    args = parser.parse_args()

    out = run_validation(os.path.abspath(args.bench), args.site)
    print(json.dumps(out, indent=2))
    return 0 if out["all_passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise
