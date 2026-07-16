#!/usr/bin/env python3
"""Candidate validation for Engineering Signoff invocation wiring."""

from __future__ import annotations

import argparse
import json
import sys
from io import BytesIO
from pathlib import Path

import frappe
from pypdf import PdfWriter


TARGET_DOCTYPES = ["Item", "BOM", "Product Bundle"]
REQUEST_ROLES = ["Engineering User", "InductOne Process Architect", "System Manager"]


class Runner:
    def __init__(self):
        self.results = []
        self.created = {}

    def check(self, label, ok, details=None):
        details = details or {}
        self.results.append({"label": label, "ok": bool(ok), "details": details})
        print(("PASS" if ok else "FAIL"), label, json.dumps(details, default=str))
        return ok

    def remember(self, doctype, name):
        self.created.setdefault(doctype, []).append(name)


def first_value(doctype, filters=None, fieldname="name"):
    value = frappe.db.get_value(doctype, filters or {}, fieldname)
    if not value:
        raise RuntimeError(f"No {doctype} found for filters {filters or {}}")
    return value


def make_item(runner, code, is_stock_item=1):
    item_group = first_value("Item Group", {"is_group": 0})
    uom = "Nos" if frappe.db.exists("UOM", "Nos") else first_value("UOM")
    doc = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": code,
            "item_name": code,
            "item_group": item_group,
            "stock_uom": uom,
            "is_stock_item": is_stock_item,
        }
    )
    meta = frappe.get_meta("Item")
    if meta.has_field("custom_item_code_display"):
        doc.custom_item_code_display = code
    doc.insert()
    runner.remember("Item", doc.name)
    frappe.db.commit()
    return doc.name


def make_bom(runner, parent_item, component_item):
    uom = frappe.db.get_value("Item", parent_item, "stock_uom") or "Nos"
    doc = frappe.get_doc(
        {
            "doctype": "BOM",
            "item": parent_item,
            "quantity": 1,
            "uom": uom,
            "is_active": 1,
            "is_default": 0,
            "items": [{"item_code": component_item, "qty": 1, "uom": uom}],
        }
    )
    doc.insert()
    runner.remember("BOM", doc.name)
    frappe.db.commit()
    return doc.name


def make_product_bundle(runner, parent_item, component_item):
    doc = frappe.get_doc(
        {
            "doctype": "Product Bundle",
            "new_item_code": parent_item,
            "description": f"Signoff validation bundle for {parent_item}",
            "items": [{"item_code": component_item, "qty": 1}],
        }
    )
    doc.insert()
    runner.remember("Product Bundle", doc.name)
    frappe.db.commit()
    return doc.name


def current_signoff(target_doctype, target_docname):
    return frappe.db.get_value(
        "Engineering Signoff",
        {
            "target_doctype": target_doctype,
            "target_docname": target_docname,
            "is_current": 1,
        },
        ["name", "status", "target_revision_id"],
        as_dict=True,
    )


def count_current(target_doctype, target_docname):
    return frappe.db.count(
        "Engineering Signoff",
        {
            "target_doctype": target_doctype,
            "target_docname": target_docname,
            "is_current": 1,
        },
    )


def validate_client_scripts(runner):
    rows = frappe.get_all(
        "Client Script",
        filters={"name": ["in", [
            "BOM Engineering Signoff Banner",
            "Product Bundle Engineering Signoff Banner",
            "Engineering Signoff Banner - Item",
            "InductOne Configuration Option Review Button",
        ]]},
        fields=["name", "dt", "script"],
    )
    by_dt = {row.dt: row for row in rows}
    for dt in TARGET_DOCTYPES:
        row = by_dt.get(dt)
        script = row.script if row else ""
        runner.check(
            f"{dt} client script has gated request button",
            bool(
                row
                and "Request Engineering Signoff" in script
                and "request_signoff" in script
                and all(role in script for role in REQUEST_ROLES)
            ),
            {"script": row.name if row else None},
        )


def validate_manual_insert(runner, target_doctype, target_docname):
    before = current_signoff(target_doctype, target_docname)
    if before and before.status == "Pending":
        from inductone_tools.engineering_signoff import approve_signoff

        approve_signoff(before.name, "Candidate validation: normalize target before manual insert")
        frappe.db.commit()
        before = current_signoff(target_doctype, target_docname)

    doc = frappe.get_doc(
        {
            "doctype": "Engineering Signoff",
            "target_doctype": target_doctype,
            "target_docname": target_docname,
        }
    )
    doc.insert()
    runner.remember("Engineering Signoff", doc.name)
    frappe.db.commit()
    after = current_signoff(target_doctype, target_docname)
    runner.check(
        "Manual Engineering Signoff insert normalizes through current-record logic",
        bool(
            after
            and after.name == doc.name
            and after.status == "Pending"
            and count_current(target_doctype, target_docname) == 1
            and (not before or before.name != after.name)
        ),
        {"before": before, "after": after, "current_count": count_current(target_doctype, target_docname)},
    )


def validate_manual_form_fields(runner):
    meta = frappe.get_meta("Engineering Signoff")
    target_doctype = meta.get_field("target_doctype")
    target_docname = meta.get_field("target_docname")
    runner.check(
        "Engineering Signoff manual target fields are usable",
        bool(
            target_doctype
            and target_doctype.fieldtype == "Select"
            and target_docname
            and target_docname.fieldtype == "Dynamic Link"
            and target_docname.options == "target_doctype"
            and not target_docname.read_only
        ),
        {
            "target_doctype": target_doctype.as_dict() if target_doctype else None,
            "target_docname": target_docname.as_dict() if target_docname else None,
        },
    )


def make_native_file(runner, attached_to_doctype, attached_to_name, suffix):
    filename = f"{attached_to_name}-{suffix}.pdf"
    file_path = Path(frappe.get_site_path("private", "files", filename))
    file_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = PdfWriter()
    pdf.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    pdf.write(buffer)
    file_path.write_bytes(buffer.getvalue())
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": filename,
            "file_url": f"/private/files/{filename}",
            "is_private": 1,
            "attached_to_doctype": attached_to_doctype,
            "attached_to_name": attached_to_name,
        }
    )
    file_doc.insert()
    runner.remember("File", file_doc.name)
    frappe.db.commit()
    return file_doc


def validate_native_attachment_collection(runner, item_code, bom_name):
    from inductone_tools.bom_export import collect_attachments_for_rows

    item_file = make_native_file(runner, "Item", item_code, "native-item-attachment")
    bom_file = make_native_file(runner, "BOM", bom_name, "native-bom-attachment")
    rows = [{"item_code": item_code, "bom_used": bom_name}]
    attachments = collect_attachments_for_rows(
        rows,
        include_item_attachments=True,
        include_bom_attachments=True,
        exts=[".pdf"],
    )
    item_hit = attachments.get(("Item", item_code), {}).get(".pdf")
    bom_hit = attachments.get(("BOM", bom_name), {}).get(".pdf")
    runner.check(
        "BOM export attachment collection uses native Item/BOM File records",
        bool(
            item_hit
            and item_hit.get("name") == item_file.name
            and bom_hit
            and bom_hit.get("name") == bom_file.name
        ),
        {
            "item_file": item_file.as_dict(),
            "bom_file": bom_file.as_dict(),
            "item_hit": item_hit,
            "bom_hit": bom_hit,
        },
    )


def validate_builder_release_gate_import(runner):
    from inductone_tools.builder_release import check_builder_release_readiness

    build = frappe.db.get_value("InductOne Build", {}, "name")
    if not build:
        runner.check("Builder-release gate import/regression check skipped", True, {"reason": "no InductOne Build in site"})
        return

    try:
        result = check_builder_release_readiness(build)
        runner.check(
            "Builder-release readiness gate still executes",
            isinstance(result, dict),
            {"build": build, "ok": result.get("ok") if isinstance(result, dict) else None},
        )
    except Exception as exc:
        runner.check(
            "Builder-release readiness gate still executes",
            False,
            {"build": build, "exception": repr(exc)},
        )


def validate_no_new_whitelisted_permission_bypass(runner):
    path = Path(__file__).resolve().parents[1] / "inductone_tools"
    allowed_existing = {
        "inductone_tools/bom_export.py",
        "inductone_tools/build_completion.py",
        "inductone_tools/build_completion_accept.py",
        "inductone_tools/builder_release.py",
        "inductone_tools/engineering_signoff.py",
        "inductone_tools/field_change.py",
        "inductone_tools/part_numbering.py",
        "inductone_tools/serial_allocation/tranche.py",
        "inductone_tools/snapshot/hierarchy.py",
    }
    hits = []
    for file in path.rglob("*.py"):
        text = file.read_text(encoding="utf-8", errors="ignore")
        bypass_token = "ignore_permissions" + "=True"
        if "@frappe.whitelist" not in text or bypass_token not in text:
            continue
        hits.append(str(file.relative_to(path.parent)).replace("\\", "/"))
    unexpected = sorted(set(hits) - allowed_existing)
    runner.check(
        "No new whitelisted permission-bypass paths introduced by this tranche",
        not unexpected,
        {
            "allowed_existing": sorted(allowed_existing & set(hits)),
            "unexpected": unexpected,
        },
    )


def run(site, sites_path, evidence_dir):
    frappe.init(site=site, sites_path=sites_path)
    frappe.connect()
    frappe.set_user("Administrator")
    runner = Runner()
    try:
        validate_client_scripts(runner)
        validate_manual_form_fields(runner)

        stamp = frappe.utils.now_datetime().strftime("%Y%m%d%H%M%S")
        item_parent = make_item(runner, f"ZZ-SIGNOFF-ITEM-{stamp}", is_stock_item=1)
        item_component = make_item(runner, f"ZZ-SIGNOFF-COMP-{stamp}", is_stock_item=1)
        runner.check(
            "Item insert auto-created Pending signoff",
            bool((current_signoff("Item", item_parent) or {}).get("status") == "Pending"),
            {"item": item_parent, "current": current_signoff("Item", item_parent)},
        )
        validate_manual_insert(runner, "Item", item_parent)

        bom_name = make_bom(runner, item_parent, item_component)
        runner.check(
            "BOM insert auto-created Pending signoff",
            bool((current_signoff("BOM", bom_name) or {}).get("status") == "Pending"),
            {"bom": bom_name, "current": current_signoff("BOM", bom_name)},
        )
        validate_native_attachment_collection(runner, item_component, bom_name)

        bundle_parent = make_item(runner, f"ZZ-SIGNOFF-BUNDLE-{stamp}", is_stock_item=0)
        bundle_name = make_product_bundle(runner, bundle_parent, item_component)
        runner.check(
            "Product Bundle insert auto-created Pending signoff",
            bool((current_signoff("Product Bundle", bundle_name) or {}).get("status") == "Pending"),
            {"product_bundle": bundle_name, "current": current_signoff("Product Bundle", bundle_name)},
        )

        validate_builder_release_gate_import(runner)
        validate_no_new_whitelisted_permission_bypass(runner)
    finally:
        evidence = {
            "site": site,
            "generated_at_utc": frappe.utils.now_datetime().isoformat(),
            "results": runner.results,
            "created_records": runner.created,
        }
        out_dir = Path(evidence_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"engineering_signoff_invocation_validation_{frappe.utils.now_datetime().strftime('%Y%m%dT%H%M%SZ')}.json"
        out.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
        print(f"Evidence: {out}")
        frappe.destroy()

    return 0 if all(row["ok"] for row in runner.results) else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--evidence-dir", default="/mnt/c/hub/frappe-sandbox/validation-evidence")
    args = parser.parse_args()
    return run(args.site, args.sites_path, args.evidence_dir)


if __name__ == "__main__":
    sys.exit(main())
