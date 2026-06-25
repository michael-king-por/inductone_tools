#!/usr/bin/env python3
"""Update candidate Wiki Page role references to the hardened role vocabulary.

This script is intentionally candidate-scoped operational tooling. It does not
touch production and does not infer replacements with regex; every substitution
is an exact role-name string replacement.
"""

from __future__ import annotations

import argparse
import sys

import frappe


REPLACEMENTS = {
    "Engineering - Signoff": "Engineering User",
    "Engineering — Signoff": "Engineering User",
    "InductOne Process Manager": "InductOne Manager",
    "InductOne Architect": "InductOne Process Architect",
    "Engineering Signoff Delegate": "Engineering User",
    "Part Number Manager": "Engineering User",
    "OPS-INDUCTONE-GATEKEEP": "InductOne Manager",
    "PRODUCT-INDUCTONE-GATEKEEP": "InductOne Process Architect",
}


def run(site: str, sites_path: str) -> int:
    frappe.init(site=site, sites_path=sites_path)
    frappe.connect()

    pages = frappe.get_all("Wiki Page", fields=["name", "title", "route"])
    total_pages = 0
    total_substitutions = 0

    for page in pages:
        content = frappe.db.get_value("Wiki Page", page.name, "content") or ""
        updated_content = content
        page_substitutions = 0

        for old, new in REPLACEMENTS.items():
            count = updated_content.count(old)
            if count:
                updated_content = updated_content.replace(old, new)
                page_substitutions += count

        if updated_content != content:
            frappe.db.set_value("Wiki Page", page.name, "content", updated_content)
            total_pages += 1
            total_substitutions += page_substitutions
            print(
                f"UPDATED {page.name} | {page.title} | {page.route} | "
                f"{page_substitutions} substitutions"
            )

    frappe.db.commit()
    print(f"SUMMARY updated_pages={total_pages} substitutions={total_substitutions}")
    return 0


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
