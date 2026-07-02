#!/usr/bin/env python3
"""Create candidate metadata needed for BOM Item per-line User Notes.

This script is intentionally candidate/sandbox oriented. It creates the
standard ERPNext BOM Item Custom Field and app-owned child DocFields so the
resulting fixtures can be exported from a real Frappe site rather than
hand-edited into large JSON blobs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import frappe


BOM_ITEM_FIELDS = [
    {
        "dt": "BOM Item",
        "fieldname": "custom_electrical_unit",
        "label": "Electrical Unit",
        "fieldtype": "Data",
        "insert_after": "custom_balloon_numbers",
        "translatable": 1,
        "no_copy": 0,
    },
    {
        "dt": "BOM Item",
        "fieldname": "custom_source_electrical_bom_rev",
        "label": "Source Electrical BOM Rev",
        "fieldtype": "Data",
        "insert_after": "custom_electrical_unit",
        "translatable": 1,
        "no_copy": 0,
    },
    {
        "dt": "BOM Item",
        "fieldname": "custom_user_notes",
        "label": "User Notes",
        "fieldtype": "Small Text",
        "insert_after": "custom_source_electrical_bom_rev",
        "translatable": 0,
        "no_copy": 0,
    },
]


APP_CHILD_FIELDS = [
    {
        "doctype": "Configured BOM Snapshot Hierarchy",
        "fieldname": "user_notes",
        "label": "User Notes",
        "fieldtype": "Small Text",
        "after": "source_electrical_bom_rev",
    },
    {
        "doctype": "BOM Export Package Item",
        "fieldname": "user_notes",
        "label": "User Notes",
        "fieldtype": "Small Text",
        "after": "qty",
    },
]


def ensure_custom_field(defn: dict[str, Any]) -> dict[str, Any]:
    name = f"{defn['dt']}-{defn['fieldname']}"
    existing = frappe.db.exists("Custom Field", name)
    if existing:
        doc = frappe.get_doc("Custom Field", name)
        changed = False
        for field in ("label", "fieldtype", "insert_after", "translatable", "no_copy"):
            if doc.get(field) != defn.get(field):
                doc.set(field, defn.get(field))
                changed = True
        if changed:
            doc.save(ignore_permissions=True)
        return {"name": name, "status": "updated" if changed else "exists"}

    doc = frappe.get_doc({"doctype": "Custom Field", **defn})
    doc.insert(ignore_permissions=True)
    return {"name": name, "status": "created"}


def ensure_docfield(defn: dict[str, Any]) -> dict[str, Any]:
    doctype = defn["doctype"]
    fieldname = defn["fieldname"]
    doc = frappe.get_doc("DocType", doctype)

    for field in doc.fields:
        if field.fieldname == fieldname:
            changed = False
            for attr in ("label", "fieldtype"):
                if field.get(attr) != defn.get(attr):
                    field.set(attr, defn.get(attr))
                    changed = True
            if changed:
                doc.save(ignore_permissions=True)
            return {"doctype": doctype, "fieldname": fieldname, "status": "updated" if changed else "exists"}

    insert_after = defn.get("after")
    new_row = {
        "fieldname": fieldname,
        "label": defn["label"],
        "fieldtype": defn["fieldtype"],
    }

    if insert_after:
        inserted = False
        rebuilt = []
        for field in doc.fields:
            rebuilt.append(field)
            if field.fieldname == insert_after:
                new = frappe.new_doc("DocField")
                new.update(new_row)
                rebuilt.append(new)
                inserted = True
        if inserted:
            doc.set("fields", rebuilt)
        else:
            doc.append("fields", new_row)
    else:
        doc.append("fields", new_row)

    doc.save(ignore_permissions=True)
    return {"doctype": doctype, "fieldname": fieldname, "status": "created"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--evidence", default="")
    args = parser.parse_args()

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    frappe.flags.in_patch = True

    actions = []
    try:
        for defn in BOM_ITEM_FIELDS:
            actions.append(ensure_custom_field(defn))
        for defn in APP_CHILD_FIELDS:
            actions.append(ensure_docfield(defn))
        frappe.clear_cache()
        frappe.db.commit()
    finally:
        frappe.destroy()

    result = {"site": args.site, "actions": actions}
    print(json.dumps(result, indent=2))
    if args.evidence:
        out = Path(args.evidence)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
