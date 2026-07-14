"""Attach repo-managed CSA Wiki pages to the existing Wiki Space.

The Wiki app renders public page routes through the owning Wiki Space. A
fixture-managed ``Wiki Page`` record can exist in Desk but still fail public
rendering if no ``Wiki Group Item`` child row links it to a ``Wiki Space``.

This patch deliberately does not fixture-manage the entire Wiki Space/sidebar.
It appends only the CSA pages owned by this app, preserving the rest of the
database-managed Wiki navigation.
"""

from __future__ import annotations

import frappe


SPACE_ROUTE = "plus-one-ops-manual"

MANAGED_WIKI_PAGES = [
    {
        "wiki_page": "9n8bvqedso",
        "parent_label": "Engineering",
    },
    {
        "wiki_page": "d0v7dsi9lu",
        "parent_label": "Engineering",
    },
    {
        "wiki_page": "3hnmdg9m5q",
        "parent_label": "InductOne",
    },
    {
        "wiki_page": "inductone-csa-owner-handbook",
        "parent_label": "InductOne",
    },
    {
        "wiki_page": "inductone-csa-quality-system",
        "parent_label": "InductOne",
    },
    {
        "wiki_page": "inductone-csa-controlled-records-index",
        "parent_label": "InductOne",
    },
    {
        "wiki_page": "3hmhgl7qdu",
        "parent_label": "InductOne",
    },
    {
        "wiki_page": "3hmdga44m5",
        "parent_label": "InductOne",
    },
    {
        "wiki_page": "3hmiq2lbi9",
        "parent_label": "InductOne",
    },
    {
        "wiki_page": "3hngf036ne",
        "parent_label": "InductOne",
    },
    {
        "wiki_page": "3hmtouafd5",
        "parent_label": "InductOne",
    },
    {
        "wiki_page": "82vdqj03n2",
        "parent_label": "InductOne",
    },
    {
        "wiki_page": "3hmbhanak2",
        "parent_label": "InductOne",
    },
    {
        "wiki_page": "eo88s4k9ui",
        "parent_label": "Engineering",
    },
    {
        "wiki_page": "3hmeksuks8",
        "parent_label": "Engineering",
    },
]


def execute() -> None:
    if not frappe.db.exists("DocType", "Wiki Space"):
        return

    space_name = frappe.db.get_value("Wiki Space", {"route": SPACE_ROUTE}, "name")
    if not space_name:
        frappe.logger(__name__).warning(
            "Wiki CSA space-link patch skipped: Wiki Space route %s not found",
            SPACE_ROUTE,
        )
        return

    space = frappe.get_doc("Wiki Space", space_name)
    existing_pages = {row.wiki_page for row in space.get("wiki_sidebars", []) if row.wiki_page}
    changed = False

    for item in MANAGED_WIKI_PAGES:
        wiki_page = item["wiki_page"]
        if wiki_page in existing_pages:
            continue
        if not frappe.db.exists("Wiki Page", wiki_page):
            frappe.logger(__name__).warning(
                "Wiki CSA space-link patch skipped missing Wiki Page %s",
                wiki_page,
            )
            continue

        space.append(
            "wiki_sidebars",
            {
                "parent_label": item["parent_label"],
                "wiki_page": wiki_page,
                "hide_on_sidebar": 0,
            },
        )
        existing_pages.add(wiki_page)
        changed = True

    if changed:
        space.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.clear_cache()
