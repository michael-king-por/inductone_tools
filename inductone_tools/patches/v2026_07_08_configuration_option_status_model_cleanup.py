"""Collapse InductOne option statuses to Draft/Released/Deprecated.

The DEV balloon-scoped catalog was originally staged as ``Defined-Ops`` while
the active Engineering Signoff code only accepts ``Draft`` configuration
options for signoff. This patch moves the abandoned intermediate statuses back
to Draft before the status Select is trimmed, and removes the inactive legacy
workflow that defined those abandoned states.
"""

from __future__ import annotations

import frappe


OPTION_DOCTYPE = "InductOne Configuration Option"
LEGACY_WORKFLOW = "InductOne Option Cycle"
RETIRED_STATUSES = ("Defined-Ops", "Defined-Product")


def execute() -> None:
    if frappe.db.table_exists(f"tab{OPTION_DOCTYPE}"):
        frappe.db.sql(
            f"""
            UPDATE `tab{OPTION_DOCTYPE}`
               SET status = 'Draft',
                   modified = modified
             WHERE status IN %(retired_statuses)s
            """,
            {"retired_statuses": RETIRED_STATUSES},
        )

        if frappe.db.has_column(OPTION_DOCTYPE, "workflow_state"):
            frappe.db.sql(
                f"""
                UPDATE `tab{OPTION_DOCTYPE}`
                   SET workflow_state = NULL,
                       modified = modified
                 WHERE workflow_state IN %(retired_statuses)s
                """,
                {"retired_statuses": RETIRED_STATUSES},
            )

    if frappe.db.exists("Workflow", LEGACY_WORKFLOW):
        frappe.delete_doc("Workflow", LEGACY_WORKFLOW, ignore_permissions=True, force=True)

    frappe.clear_cache(doctype=OPTION_DOCTYPE)
    frappe.clear_cache(doctype="Workflow")
