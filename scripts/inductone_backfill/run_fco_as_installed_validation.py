#!/usr/bin/env python3
"""Validate the InductOne as-installed/FCO integration gates in candidate."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import frappe
from frappe.permissions import has_permission
from openpyxl import load_workbook


LOCATION_DOCTYPE = "POR Physical Location"
INSTANCE_DOCTYPE = "InductOne Instance"
REQUEST_DOCTYPE = "InductOne Field Change Request"
FIELD_CHANGE_DOCTYPE = "InductOne Field Change"
NEW_DOCTYPES = [REQUEST_DOCTYPE, FIELD_CHANGE_DOCTYPE, "InductOne Field Change Serial"]


class GateRunner:
    def __init__(self):
        self.gates = []

    def check(self, gate: str, condition: bool, details=None):
        status = "PASS" if condition else "FAIL"
        self.gates.append({"gate": gate, "status": status, "details": details})
        print(status, gate, json.dumps(details, default=str) if details is not None else "")
        return condition

    @property
    def ok(self):
        return all(gate["status"] == "PASS" for gate in self.gates)


def workbook_rows(path: Path, sheet: str):
    wb = load_workbook(path, data_only=True, read_only=True)
    ws = wb[sheet]
    iterator = ws.iter_rows(values_only=True)
    headers = [str(value).strip() if value is not None else "" for value in next(iterator)]
    return [dict(zip(headers, row)) for row in iterator if any(value is not None for value in row)]


def gate_location_tree(runner: GateRunner, seed_dir: Path):
    seed = workbook_rows(seed_dir / "location_tree_seed.xlsx", "POR Physical Location")
    missing, parent_errors, leaf_errors, path_errors = [], [], [], []
    for row in seed:
        code = row["location_code"]
        name = frappe.db.get_value(LOCATION_DOCTYPE, {"location_code": code}, "name")
        if not name:
            missing.append(code)
            continue
        doc = frappe.get_doc(LOCATION_DOCTYPE, name)
        parent_code = row.get("parent_location_code")
        if parent_code:
            parent_name = frappe.db.get_value(LOCATION_DOCTYPE, {"location_code": parent_code}, "name")
            if doc.parent_por_physical_location != parent_name:
                parent_errors.append({"location_code": code, "expected_parent": parent_code, "actual": doc.parent_por_physical_location})
        if row["location_type"] == "Cell" and (int(doc.rgt or 0) - int(doc.lft or 0) != 1):
            leaf_errors.append({"location_code": code, "lft": doc.lft, "rgt": doc.rgt})
        if doc.full_path != row.get("full_path"):
            path_errors.append({"location_code": code, "expected": row.get("full_path"), "actual": doc.full_path})
    return runner.check(
        "Location tree integrity",
        not (missing or parent_errors or leaf_errors or path_errors),
        {"seed_rows": len(seed), "missing": missing, "parent_errors": parent_errors, "leaf_errors": leaf_errors, "path_errors": path_errors},
    )


def gate_instance_locations(runner: GateRunner, seed_dir: Path):
    seed = workbook_rows(seed_dir / "instance_backfill_seed.xlsx", "Instances")
    seeded_serials = [row["system_serial"] for row in seed]
    rows = frappe.get_all(
        INSTANCE_DOCTYPE,
        filters={"name": ["in", seeded_serials]},
        fields=["name", "origin", "physical_location", "deployment_site"],
    )
    failures = []
    for row in rows:
        if row.origin == "Internal-Reference":
            continue
        if not row.physical_location:
            failures.append({"instance": row.name, "issue": "missing physical_location"})
            continue
        loc = frappe.get_doc(LOCATION_DOCTYPE, row.physical_location)
        if loc.location_type != "Cell":
            failures.append({"instance": row.name, "issue": "physical_location is not Cell", "location": row.physical_location, "type": loc.location_type})
        if row.deployment_site != loc.full_path:
            failures.append({"instance": row.name, "issue": "deployment_site mismatch", "expected": loc.full_path, "actual": row.deployment_site})
    missing = sorted(set(seeded_serials) - {row.name for row in rows})
    failures.extend({"instance": name, "issue": "seeded instance missing"} for name in missing)
    return runner.check("Seeded Instances linked to Cell physical locations", not failures, {"checked": len(rows), "seed_rows": len(seed), "failures": failures})


def gate_field_changes_resolve(runner: GateRunner):
    rows = frappe.get_all(FIELD_CHANGE_DOCTYPE, fields=["name", "instance"])
    failures = []
    for row in rows:
        instance = frappe.get_doc(INSTANCE_DOCTYPE, row.instance)
        if not instance.physical_location:
            failures.append({"field_change": row.name, "instance": row.instance, "issue": "instance missing physical_location"})
            continue
        loc = frappe.get_doc(LOCATION_DOCTYPE, instance.physical_location)
        if loc.location_type != "Cell":
            failures.append({"field_change": row.name, "instance": row.instance, "location": loc.name, "type": loc.location_type})
    return runner.check("Backfilled Field Changes resolve through Instance to Cell", not failures, {"checked": len(rows), "failures": failures})


def gate_fco_map_represented(runner: GateRunner, seed_dir: Path):
    seed = workbook_rows(seed_dir / "fco_instance_map.xlsx", "FCO -> Instance Map")
    missing_requests, missing_instances, spawned = [], [], []
    pending_or_organic = []
    for row in seed:
        fco = row["FCO #"]
        if not frappe.db.exists(REQUEST_DOCTYPE, fco):
            missing_requests.append(fco)
        serial = row.get("PRIMARY Unit (best guess) - serial")
        if serial and isinstance(serial, str) and serial.startswith(("IN", "IND", "REF")):
            if not frappe.db.exists(INSTANCE_DOCTYPE, serial):
                missing_instances.append({"fco": fco, "serial": serial})
        else:
            pending_or_organic.append({"fco": fco, "serial": serial})
        if str(row.get("Spawns per-Instance FC") or "").upper().startswith("YES"):
            spawned.append(fco)
    fc_counts = {
        fco: frappe.db.count(FIELD_CHANGE_DOCTYPE, {"source_request": fco})
        for fco in spawned
    }
    spawn_ok = fc_counts.get("FCO-2025-007") == 2 and fc_counts.get("FCO-2025-010") == 2
    return runner.check(
        "FCO map represented with pending/organic exceptions",
        not missing_requests and not missing_instances and spawn_ok,
        {
            "map_rows": len(seed),
            "missing_requests": missing_requests,
            "missing_instances": missing_instances,
            "spawn_counts": fc_counts,
            "pending_or_organic": pending_or_organic,
        },
    )


def gate_as_installed_query(runner: GateRunner):
    rows = frappe.db.sql(
        """
        SELECT
          site.location_code AS site_code,
          inst.name AS instance,
          inst.status,
          inst.latest_field_change_date
        FROM `tabInductOne Instance` inst
        INNER JOIN `tabPOR Physical Location` cell ON cell.name = inst.physical_location
        LEFT JOIN `tabPOR Physical Location` lane ON lane.name = cell.parent_por_physical_location
        LEFT JOIN `tabPOR Physical Location` site ON site.name = lane.parent_por_physical_location
        WHERE site.location_type = 'Site'
        ORDER BY site.location_code, inst.name
        """,
        as_dict=True,
    )
    return runner.check("As-installed Site query returns installed fleet context", bool(rows), {"row_count": len(rows), "sample": rows[:5]})


def gate_reassignment_mechanism(runner: GateRunner):
    request_name = frappe.db.get_value(REQUEST_DOCTYPE, {"assignment_confidence": "Low"}, "name")
    instances = frappe.get_all(INSTANCE_DOCTYPE, pluck="name", limit=2)
    if not request_name or len(instances) < 2:
        return runner.check("Reassignment mechanism", False, {"issue": "not enough test data"})

    doc = frappe.get_doc(REQUEST_DOCTYPE, request_name)
    original = doc.instance
    target = next(name for name in instances if name != original)
    before_versions = frappe.db.count("Version", {"ref_doctype": REQUEST_DOCTYPE, "docname": request_name})

    rejected_without_reason = False
    try:
        doc.instance = target
        doc.assignment_change_reason = ""
        doc.save()
    except Exception:
        rejected_without_reason = True
        frappe.db.rollback()

    doc = frappe.get_doc(REQUEST_DOCTYPE, request_name)
    doc.instance = target
    doc.assignment_change_reason = "Validation proof: reassignment requires reason."
    doc.save()
    doc = frappe.get_doc(REQUEST_DOCTYPE, request_name)
    doc.instance = original
    doc.assignment_change_reason = "Validation cleanup: restore original assignment."
    doc.save()
    frappe.db.commit()
    after_versions = frappe.db.count("Version", {"ref_doctype": REQUEST_DOCTYPE, "docname": request_name})

    low_conf_count = frappe.db.count(REQUEST_DOCTYPE, {"assignment_confidence": ["in", ["Low", "Backfill-guess"]], "assignment_reviewed": 0})
    return runner.check(
        "Reassignment mechanism rejects missing reason and records Version",
        rejected_without_reason and after_versions > before_versions and low_conf_count > 0,
        {"request": request_name, "before_versions": before_versions, "after_versions": after_versions, "low_confidence_unreviewed": low_conf_count},
    )


def gate_external_builder_denial(runner: GateRunner):
    users = ["motion.builder@plusonerobotics.com", "lam@plusonerobotics.com"]
    failures = []
    original_user = frappe.session.user
    for user in users:
        if not frappe.db.exists("User", user):
            failures.append({"user": user, "issue": "missing user"})
            continue
        frappe.set_user(user)
        for doctype in NEW_DOCTYPES:
            for ptype in ["read", "create"]:
                allowed = has_permission(doctype, ptype=ptype, user=user)
                if allowed:
                    failures.append({"user": user, "doctype": doctype, "ptype": ptype})
    frappe.set_user(original_user)
    return runner.check("External builders denied new FCO DocTypes", not failures, {"failures": failures})


def gate_ignore_permissions_clean(runner: GateRunner, app_path: Path):
    new_files = [app_path / "inductone_tools" / "field_change.py"]
    hits = []
    for path in new_files:
        if not path.exists():
            hits.append({"file": str(path), "issue": "missing"})
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"ignore_permissions\\s*=\\s*True", text):
            hits.append({"file": str(path), "offset": match.start()})
    return runner.check("No ignore_permissions=True in new whitelisted methods", not hits, {"hits": hits})


def run(args):
    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        runner = GateRunner()
        gate_location_tree(runner, args.seed_dir)
        gate_instance_locations(runner, args.seed_dir)
        gate_field_changes_resolve(runner)
        gate_fco_map_represented(runner, args.seed_dir)
        gate_as_installed_query(runner)
        gate_reassignment_mechanism(runner)
        gate_external_builder_denial(runner)
        gate_ignore_permissions_clean(runner, args.app_path)
        payload = {
            "site": args.site,
            "generated_at_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "ok": runner.ok,
            "gates": runner.gates,
        }
        return payload
    finally:
        frappe.destroy()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--seed-dir", type=Path, default=Path(__file__).resolve().parent / "seeds")
    parser.add_argument("--app-path", type=Path, default=Path.cwd() / "apps" / "inductone_tools")
    parser.add_argument("--evidence-dir", type=Path, default=Path("/mnt/c/hub/frappe-sandbox/validation-evidence"))
    args = parser.parse_args()
    args.evidence_dir.mkdir(parents=True, exist_ok=True)

    payload = run(args)
    path = args.evidence_dir / "fco_as_installed_validation.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Evidence: {path}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
