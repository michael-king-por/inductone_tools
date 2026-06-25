#!/usr/bin/env python3
"""Direct whitelisted-method negative permission tests for candidate sandbox.

These checks intentionally bypass Desk route/button visibility and call the
server methods directly as users who must not be authorized.  A passing check
proves the method raises frappe.PermissionError before document lookup or
domain validation can run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Callable

import frappe


EVIDENCE_DIR = "/mnt/c/hub/frappe-sandbox/validation-evidence"
NONEXISTENT_NAME = "NEGATIVE-PERMISSION-DOES-NOT-EXIST-2026-06-25"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _exception_name(exc: BaseException | None) -> str | None:
    if exc is None:
        return None
    return exc.__class__.__name__


def _call_check(label: str, user: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
    frappe.set_user(user)
    frappe.session.user = user

    raised: BaseException | None = None
    passed = False

    try:
        func(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001 - evidence records exact class
        raised = exc
        passed = isinstance(exc, frappe.PermissionError)
    finally:
        frappe.db.rollback()
        frappe.local.message_log = []

    status = "PASS" if passed else "FAIL"
    exc_name = _exception_name(raised) or "NO_EXCEPTION"
    print(f"{status} {label} as {user}: raised {exc_name}")

    return {
        "label": label,
        "user": user,
        "passed": passed,
        "expected_exception": "PermissionError",
        "actual_exception": exc_name,
        "message": str(raised) if raised else None,
    }


def run(site: str, sites_path: str) -> int:
    frappe.init(site=site, sites_path=sites_path)
    frappe.connect()

    from inductone_tools.builder_release import release_to_builder_now
    from inductone_tools.build_completion_accept import accept_completion_create_as_built
    from inductone_tools.engineering_signoff import (
        approve_signoff,
        reject_signoff,
        supersede_config_option,
    )
    from inductone_tools.part_numbering import allocate_numbers

    motion_builder = "motion.builder@plusonerobotics.com"
    operations_viewer = "candidate.operations.viewer@example.invalid"

    checks: list[tuple[str, str, Callable[..., Any], tuple[Any, ...], dict[str, Any]]] = [
        ("engineering_signoff.approve_signoff", motion_builder, approve_signoff, (NONEXISTENT_NAME,), {"notes": "negative permission test"}),
        ("engineering_signoff.approve_signoff", operations_viewer, approve_signoff, (NONEXISTENT_NAME,), {"notes": "negative permission test"}),
        ("engineering_signoff.reject_signoff", motion_builder, reject_signoff, (NONEXISTENT_NAME,), {"reason": "negative permission test"}),
        ("engineering_signoff.reject_signoff", operations_viewer, reject_signoff, (NONEXISTENT_NAME,), {"reason": "negative permission test"}),
        (
            "engineering_signoff.supersede_config_option",
            motion_builder,
            supersede_config_option,
            (NONEXISTENT_NAME,),
            {"new_option_code": "NEGATIVE-PERMISSION-TEST", "notes": "negative permission test"},
        ),
        (
            "engineering_signoff.supersede_config_option",
            operations_viewer,
            supersede_config_option,
            (NONEXISTENT_NAME,),
            {"new_option_code": "NEGATIVE-PERMISSION-TEST", "notes": "negative permission test"},
        ),
        ("part_numbering.allocate_numbers", motion_builder, allocate_numbers, (NONEXISTENT_NAME,), {}),
        ("part_numbering.allocate_numbers", operations_viewer, allocate_numbers, (NONEXISTENT_NAME,), {}),
        ("builder_release.release_to_builder_now", motion_builder, release_to_builder_now, (NONEXISTENT_NAME,), {}),
        (
            "build_completion_accept.accept_completion_create_as_built",
            motion_builder,
            accept_completion_create_as_built,
            (NONEXISTENT_NAME,),
            {},
        ),
    ]

    results = [_call_check(label, user, func, *args, **kwargs) for label, user, func, args, kwargs in checks]
    passed = sum(1 for row in results if row["passed"])
    failed = len(results) - passed

    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    evidence_path = os.path.join(EVIDENCE_DIR, f"method_negative_tests_{_timestamp()}.json")
    payload = {
        "site": site,
        "sites_path": sites_path,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {"total": len(results), "passed": passed, "failed": failed},
        "results": results,
    }
    with open(evidence_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)

    print(f"SUMMARY {passed}/{len(results)} passed; evidence={evidence_path}")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    args = parser.parse_args()

    try:
        return run(args.site, args.sites_path)
    finally:
        frappe.destroy()


if __name__ == "__main__":
    sys.exit(main())
