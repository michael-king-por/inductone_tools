"""Retire GUI-maintained Server Scripts now owned by app code or obsolete.

This patch is intentionally conservative: it disables only named scripts that
were identified during the 2026-07-15 GUI-vs-fixture outlier audit.

- ``POR Physical Locations`` is replaced by ``inductone_tools.physical_location``.
- ``Builder Bom Permissions`` references the retired generic ``Builder`` role;
  external-builder raw Item/BOM denial is now app-owned in hooks.py.
- The remaining two scripts were already disabled legacy/stub scripts. Keeping
  them disabled makes candidate restores self-cleaning without deleting history.
"""

from __future__ import annotations

import frappe


SERVER_SCRIPTS_TO_DISABLE = [
    "Builder Bom Permissions",
    "POR Physical Locations",
    "InductOne Configuration Option Validation/Gatekeep",
    "POR-Generated-BOM-Snapshot",
]


def execute():
    for script_name in SERVER_SCRIPTS_TO_DISABLE:
        if frappe.db.exists("Server Script", script_name):
            frappe.db.set_value(
                "Server Script",
                script_name,
                "disabled",
                1,
                update_modified=False,
            )

    frappe.clear_cache()
