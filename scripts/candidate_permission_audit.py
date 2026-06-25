"""Audit effective permissions for target candidate personas.

The output is JSON Lines so it can be diffed between runs.
"""

from __future__ import annotations

import argparse
import json
import sys

from role_validation_config import AUDIT_DOCTYPES, AUDIT_USERS, PERMISSION_TYPES


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--users", nargs="*", default=AUDIT_USERS)
    parser.add_argument("--doctypes", nargs="*", default=AUDIT_DOCTYPES)
    return parser.parse_args()


def main():
    args = parse_args()
    import frappe
    from frappe.permissions import has_permission

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        for user in args.users:
            if not frappe.db.exists("User", user):
                print(json.dumps({"type": "missing-user", "user": user}))
                continue

            print(
                json.dumps(
                    {
                        "type": "user",
                        "user": user,
                        "roles": sorted(frappe.get_roles(user)),
                        "role_profile": frappe.db.get_value("User", user, "role_profile_name"),
                    },
                    sort_keys=True,
                )
            )

            for doctype in args.doctypes:
                if not frappe.db.exists("DocType", doctype):
                    continue

                permissions = {
                    ptype: bool(has_permission(doctype, ptype=ptype, user=user))
                    for ptype in PERMISSION_TYPES
                }
                print(
                    json.dumps(
                        {
                            "type": "permission",
                            "user": user,
                            "doctype": doctype,
                            "permissions": permissions,
                        },
                        sort_keys=True,
                    )
                )
    finally:
        frappe.destroy()


if __name__ == "__main__":
    sys.exit(main())
