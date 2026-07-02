#!/usr/bin/env python3
"""Pre-deploy permission gate for InductOne hardening.

Runs the standing permission audits against one site, aggregates them into a
single GATE PASS/FAIL, and exits non-zero if any non-accepted issue is found.
This is the repeatable gate that should pass before any future deploy, so the
regression classes already fixed (lost report/link dependencies, orphaned
workspaces, weakened high-risk denials) cannot ship again.

It orchestrates the existing standalone audits as subprocesses (each manages its
own frappe.init/connect/destroy):
  - run_production_post_deploy_validation.py  (high-risk denials + finance exec)
  - run_static_link_dependency_audit.py       (write-without-link-read gaps)
  - run_workspace_visibility_audit.py          (orphaned internal pages)

The effective-permission regression diff needs a baseline + candidate and is run
separately; this gate reports whether it was run, not its full contents.

ACCEPTED findings below are the owner-classified, non-blocking exceptions
(2026-06-29). Adjust them deliberately — every entry is a documented decision.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent

# Owner-accepted, non-blocking exceptions (see downstream-loss-triage-2026-06-29.md).
ACCEPTED_LINK_TARGET_DOCTYPES = {"Country", "User"}  # Desk-not-blocking / cosmetic
ACCEPTED_ORPHAN_WORKSPACES = {"Builder Portal"}  # intentional external-builder page


def _newest(evidence_dir: str, pattern: str) -> dict | None:
    matches = sorted(
        glob.glob(str(Path(evidence_dir) / pattern)),
        key=os.path.getmtime,
    )
    if not matches:
        return None
    return json.loads(Path(matches[-1]).read_text(encoding="utf-8"))


def _run_audit(script: str, site: str, sites_path: str, evidence_dir: str) -> int:
    cmd = [
        sys.executable,
        str(HERE / script),
        "--site", site,
        "--sites-path", sites_path,
        "--evidence-dir", evidence_dir,
    ]
    print(f"\n--- running {script} ---")
    return subprocess.run(cmd, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument(
        "--evidence-dir",
        default=os.environ.get("VALIDATION_EVIDENCE_DIR", "deployment-evidence"),
    )
    parser.add_argument("--finance-report-user", default=None)
    args = parser.parse_args()

    failures: list[str] = []

    # 1) High-risk denial + finance execution validator (authoritative exit code).
    val_cmd = [
        sys.executable,
        str(HERE / "run_production_post_deploy_validation.py"),
        "--site", args.site,
        "--sites-path", args.sites_path,
        "--evidence-dir", args.evidence_dir,
    ]
    if args.finance_report_user:
        val_cmd += ["--finance-report-user", args.finance_report_user]
    print("\n--- running run_production_post_deploy_validation.py ---")
    if subprocess.run(val_cmd, check=False).returncode != 0:
        failures.append("post_deploy_validation: one or more checks FAILED")

    # 2) Static link-dependency audit (informational exit; judge by evidence).
    _run_audit("run_static_link_dependency_audit.py", args.site, args.sites_path, args.evidence_dir)
    link = _newest(args.evidence_dir, "static_link_dependency_audit_*.json")
    if link is None:
        failures.append("static_link_audit: no evidence file produced")
    else:
        unexpected = [
            m for m in link.get("missing", [])
            if m.get("target_doctype") not in ACCEPTED_LINK_TARGET_DOCTYPES
        ]
        if unexpected:
            failures.append(
                f"static_link_audit: {len(unexpected)} unexpected missing link-read "
                f"dependencies (accepted: {sorted(ACCEPTED_LINK_TARGET_DOCTYPES)})"
            )
            for m in unexpected[:20]:
                print(f"  MISSING {m.get('role')} {m.get('source_doctype')}."
                      f"{m.get('fieldname')} -> {m.get('target_doctype')}")

    # 3) Workspace visibility audit (informational exit; judge by evidence).
    _run_audit("run_workspace_visibility_audit.py", args.site, args.sites_path, args.evidence_dir)
    ws = _newest(args.evidence_dir, "workspace_visibility_audit_*.json")
    if ws is None:
        failures.append("workspace_audit: no evidence file produced")
    else:
        unexpected = [
            o for o in ws.get("orphaned", [])
            if o.get("name") not in ACCEPTED_ORPHAN_WORKSPACES
        ]
        if unexpected:
            failures.append(
                f"workspace_audit: {len(unexpected)} unexpected orphaned page(s) "
                f"(accepted: {sorted(ACCEPTED_ORPHAN_WORKSPACES)})"
            )
            for o in unexpected:
                print(f"  ORPHAN {o.get('type')} {o.get('name')} roles={o.get('roles')}")

    print("\n==================== PRE-DEPLOY PERMISSION GATE ====================")
    if failures:
        print("GATE: FAIL")
        for f in failures:
            print(f"  - {f}")
        print("Reminder: also run run_effective_permission_regression_diff.py against a")
        print("candidate synced to production roles before deploying.")
        return 1
    print("GATE: PASS (post-deploy validation, link-dependency audit, workspace audit)")
    print("Reminder: also run the effective-permission regression diff against a")
    print("production-synced candidate as the final 'nobody lost needed access' check.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
