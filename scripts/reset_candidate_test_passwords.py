"""Reset test passwords in a candidate sandbox only.

This is for local/candidate validation so API and GUI smoke tests can log in as
representative users. Do not run against production.
"""

from __future__ import annotations

import argparse
import sys

from role_validation_config import AUDIT_USERS


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--confirm-candidate", action="store_true")
    parser.add_argument("--allow-non-candidate", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.confirm_candidate:
        raise SystemExit("Dry-run not supported for password reset. Pass --confirm-candidate.")
    if "candidate" not in args.site and not args.allow_non_candidate:
        raise SystemExit(f"Refusing password reset on non-candidate site {args.site!r}.")

    import frappe
    from frappe.utils.password import update_password

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        for user in AUDIT_USERS:
            if not frappe.db.exists("User", user):
                print(f"SKIP missing user: {user}")
                continue
            update_password(user, args.password, logout_all_sessions=True)
            print(f"password reset: {user}")

        frappe.db.commit()
        frappe.clear_cache()
    finally:
        frappe.destroy()


if __name__ == "__main__":
    sys.exit(main())
