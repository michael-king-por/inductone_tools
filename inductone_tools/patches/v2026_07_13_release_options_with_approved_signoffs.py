"""Release Draft configuration options that already passed Engineering Signoff.

Engineering Signoff approval is the release gate for InductOne Configuration
Options. Production briefly allowed an impossible state: a current Approved
signoff on an option that remained Draft. This patch reconciles those records
so release-readiness and the catalog agree with the audit trail.
"""

from __future__ import annotations

import frappe


OPTION_DOCTYPE = "InductOne Configuration Option"
SIGNOFF_DOCTYPE = "Engineering Signoff"


def execute() -> None:
    reconcile_approved_signoff_releases()


def reconcile_approved_signoff_releases() -> None:
    if not (
        frappe.db.table_exists(f"tab{OPTION_DOCTYPE}")
        and frappe.db.table_exists(f"tab{SIGNOFF_DOCTYPE}")
    ):
        return

    frappe.db.sql(
        f"""
        UPDATE `tab{OPTION_DOCTYPE}` opt
        INNER JOIN `tab{SIGNOFF_DOCTYPE}` signoff
                ON signoff.target_doctype = %(option_doctype)s
               AND signoff.target_docname = opt.name
               AND signoff.is_current = 1
               AND signoff.status = 'Approved'
           SET opt.status = 'Released',
               opt.modified = opt.modified
         WHERE opt.status = 'Draft'
        """,
        {"option_doctype": OPTION_DOCTYPE},
    )

    frappe.db.sql(
        f"""
        UPDATE `tab{SIGNOFF_DOCTYPE}` signoff
        INNER JOIN `tab{OPTION_DOCTYPE}` opt
                ON signoff.target_doctype = %(option_doctype)s
               AND signoff.target_docname = opt.name
               AND signoff.is_current = 1
               AND signoff.status = 'Approved'
           SET signoff.target_revision_id = CAST(opt.modified AS CHAR),
               signoff.target_description = REPLACE(
                   COALESCE(signoff.target_description, opt.name),
                   'Status: Draft',
                   'Status: Released'
               ),
               signoff.modified = signoff.modified
         WHERE opt.status = 'Released'
           AND COALESCE(signoff.target_description, '') LIKE '%%Status: Draft%%'
        """,
        {"option_doctype": OPTION_DOCTYPE},
    )

    frappe.clear_cache(doctype=OPTION_DOCTYPE)
    frappe.clear_cache(doctype=SIGNOFF_DOCTYPE)
