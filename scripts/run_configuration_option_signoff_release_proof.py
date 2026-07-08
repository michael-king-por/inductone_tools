#!/usr/bin/env python3
"""Prove Draft -> Engineering Signoff -> Released for DEV options in candidate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_EVIDENCE_DIR = Path("/mnt/c/hub/frappe-sandbox/validation-evidence")
DEFAULT_USER = "michael.king@plusonerobotics.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    return parser.parse_args()


def exception_payload(exc: Exception) -> dict:
    return {"class": exc.__class__.__name__, "message": str(exc)}


def main() -> int:
    args = parse_args()

    import frappe
    from inductone_tools.balloon_scoped_options import option_codes
    from inductone_tools.engineering_signoff import approve_signoff, request_signoff

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = args.evidence_dir / f"configuration_option_signoff_release_proof_{timestamp}.json"

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    frappe.set_user(args.user)

    results = []
    manual_release_block = {"passed": False}
    try:
        codes = option_codes()
        starting_statuses = {
            code: frappe.db.get_value("InductOne Configuration Option", {"option_code": code}, "status")
            for code in codes
        }
        non_draft = {code: status for code, status in starting_statuses.items() if status != "Draft"}
        if non_draft:
            payload = {
                "site": args.site,
                "generated_at_utc": timestamp,
                "user": args.user,
                "passed": False,
                "starting_statuses": starting_statuses,
                "fatal": f"All DEV options must start Draft before signoff proof. Non-Draft: {non_draft}",
            }
            evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            print(f"FAIL starting status gate: {payload['fatal']}")
            print(f"Evidence: {evidence_path}")
            return 1

        first_code = codes[0]
        first_name = frappe.db.get_value(
            "InductOne Configuration Option", {"option_code": first_code}, "name"
        )
        try:
            doc = frappe.get_doc("InductOne Configuration Option", first_name)
            doc.status = "Released"
            doc.save()
            manual_release_block = {
                "passed": False,
                "option_code": first_code,
                "detail": "manual Draft->Released save unexpectedly succeeded",
            }
        except Exception as exc:
            frappe.db.rollback()
            manual_release_block = {
                "passed": True,
                "option_code": first_code,
                "exception": exception_payload(exc),
            }

        for code in codes:
            docname = frappe.db.get_value("InductOne Configuration Option", {"option_code": code}, "name")
            row = {
                "option_code": code,
                "docname": docname,
                "passed": True,
                "steps": {},
                "findings": [],
            }

            try:
                req = request_signoff("InductOne Configuration Option", docname)
                row["steps"]["request_from_draft"] = req
                signoff_name = req["signoff_name"]
            except Exception as exc:
                row["passed"] = False
                row["findings"].append({"request_from_draft_failed": exception_payload(exc)})
                results.append(row)
                continue

            try:
                approval = approve_signoff(
                    signoff_name,
                    notes="Candidate validation: DEV option signoff release proof.",
                )
                row["steps"]["approve"] = approval
            except Exception as exc:
                row["passed"] = False
                row["findings"].append({"approve_failed": exception_payload(exc)})
                results.append(row)
                continue

            status = frappe.db.get_value("InductOne Configuration Option", docname, "status")
            signoff_status = frappe.db.get_value("Engineering Signoff", signoff_name, "status")
            current = frappe.db.get_value("Engineering Signoff", signoff_name, "is_current")
            release_comments = frappe.get_all(
                "Comment",
                filters={
                    "reference_doctype": "InductOne Configuration Option",
                    "reference_name": docname,
                    "content": ["like", "%Configuration Option released by Engineering Signoff%"],
                },
                pluck="name",
            )

            row["steps"]["post_approval_state"] = {
                "option_status": status,
                "signoff_status": signoff_status,
                "signoff_is_current": current,
                "release_comment_count": len(release_comments),
            }
            if status != "Released":
                row["passed"] = False
                row["findings"].append(f"expected option Released, found {status!r}")
            if signoff_status != "Approved":
                row["passed"] = False
                row["findings"].append(f"expected signoff Approved, found {signoff_status!r}")
            if not release_comments:
                row["passed"] = False
                row["findings"].append("release side-effect comment not found")

            try:
                released_doc = frappe.get_doc("InductOne Configuration Option", docname)
                released_doc.internal_notes = (released_doc.internal_notes or "") + "\nIMMUTABILITY TEST"
                released_doc.save()
                row["passed"] = False
                row["findings"].append("Released option edit unexpectedly succeeded")
            except Exception as exc:
                frappe.db.rollback()
                row["steps"]["released_immutability_block"] = exception_payload(exc)

            try:
                request_signoff("InductOne Configuration Option", docname)
                row["passed"] = False
                row["findings"].append("request_signoff on Released option unexpectedly succeeded")
            except Exception as exc:
                frappe.db.rollback()
                row["steps"]["non_draft_request_rejected"] = exception_payload(exc)

            results.append(row)
    finally:
        frappe.destroy()

    payload = {
        "site": args.site,
        "generated_at_utc": timestamp,
        "user": args.user,
        "manual_release_block": manual_release_block,
        "option_count": len(results),
        "passed": manual_release_block.get("passed") and all(row["passed"] for row in results),
        "results": results,
    }
    evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print(("PASS" if manual_release_block.get("passed") else "FAIL"), "manual Draft->Released block")
    for row in results:
        status = "PASS" if row["passed"] else "FAIL"
        print(f"{status} {row['option_code']}: {row['findings'] or ''}")
    print(f"Evidence: {evidence_path}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
