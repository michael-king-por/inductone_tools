"""Create candidate-only synthetic persona users for permission validation.

These users are deliberately under example.invalid and this script refuses to
run unless the target site name contains "candidate".
"""

from __future__ import annotations

import argparse
import sys

from role_validation_config import TARGET_ROLE_ASSIGNMENTS


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--password", default="InductOne-Sandbox-Test-2026!")
    parser.add_argument("--confirm-candidate", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if "candidate" not in args.site or not args.confirm_candidate:
        raise SystemExit("Refusing to create users unless --confirm-candidate is used on a candidate site.")

    import frappe

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        for user, roles in TARGET_ROLE_ASSIGNMENTS.items():
            if not user.endswith("@example.invalid"):
                continue
            if not frappe.db.exists("User", user):
                print(f"CREATE {user}")
                doc = frappe.get_doc(
                    {
                        "doctype": "User",
                        "email": user,
                        "first_name": "Candidate",
                        "last_name": user.split("@", 1)[0].replace("candidate.", "").replace(".", " ").title(),
                        "enabled": 1,
                        "user_type": "System User",
                        "send_welcome_email": 0,
                        "roles": [{"role": role} for role in ["Desk User", *roles]],
                    }
                )
                doc.insert(ignore_permissions=True)
            else:
                print(f"OK exists {user}")
                doc = frappe.get_doc("User", user)
                doc.enabled = 1
                doc.user_type = "System User"
                existing = {row.role for row in doc.roles}
                for role in ["Desk User", *roles]:
                    if role not in existing:
                        doc.append("roles", {"role": role})
                doc.save(ignore_permissions=True)
            frappe.utils.password.update_password(user, args.password)
        frappe.db.commit()
        frappe.clear_cache()
    finally:
        frappe.destroy()


if __name__ == "__main__":
    sys.exit(main())
