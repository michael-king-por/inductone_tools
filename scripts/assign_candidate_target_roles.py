"""Assign target roles in a candidate sandbox.

Safety:
- Dry-run by default.
- Requires --confirm-candidate to mutate.
- Refuses to run if the site name does not contain "candidate" unless
  --allow-non-candidate is explicitly passed.

Run inside the bench Python environment, for example:

    env/bin/python /path/to/scripts/assign_candidate_target_roles.py \
      --site inductone-candidate.localhost \
      --sites-path /home/.../candidate-bench/sites \
      --confirm-candidate --remove-legacy
"""

from __future__ import annotations

import argparse
import sys

from role_validation_config import (
    BROAD_PROFILE_ROLES_TO_REMOVE_IN_STRICT_CANDIDATE_TESTS,
    EXTERNAL_BUILDERS,
    FOUNDATIONAL_ROLES_TO_KEEP,
    LEGACY_ROLES_TO_REMOVE_IN_CANDIDATE,
    TARGET_ROLE_ASSIGNMENTS,
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--confirm-candidate", action="store_true")
    parser.add_argument("--allow-non-candidate", action="store_true")
    parser.add_argument("--remove-legacy", action="store_true")
    parser.add_argument(
        "--strict-target-roles",
        action="store_true",
        help=(
            "Candidate-only: remove broad old profile roles so persona tests prove "
            "the target roles, not inherited/sandwiched roles."
        ),
    )
    parser.add_argument("--clear-role-profile", action="store_true", default=True)
    return parser.parse_args()


def assert_safe(args):
    if "candidate" not in args.site and not args.allow_non_candidate:
        raise SystemExit(
            f"Refusing to mutate non-candidate site {args.site!r}. "
            "Pass --allow-non-candidate only after explicit approval."
        )


def has_child_role(user_doc, role):
    return any(row.role == role for row in user_doc.roles)


def remove_child_role(user_doc, role):
    user_doc.roles = [row for row in user_doc.roles if row.role != role]


def ensure_supplier_permission(user, supplier, dry_run):
    import frappe

    if not frappe.db.exists("Supplier", supplier):
        print(f"WARN supplier missing for {user}: {supplier}")
        return

    exists = frappe.db.exists(
        "User Permission",
        {
            "user": user,
            "allow": "Supplier",
            "for_value": supplier,
        },
    )
    if exists:
        print(f"OK supplier permission exists: {user} -> {supplier}")
        return

    print(f"ADD supplier permission: {user} -> {supplier}")
    if not dry_run:
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": user,
                "allow": "Supplier",
                "for_value": supplier,
                "apply_to_all_doctypes": 1,
            }
        ).insert(ignore_permissions=True)


def main():
    args = parse_args()
    dry_run = not args.confirm_candidate
    if not dry_run:
        assert_safe(args)

    import frappe

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        for user, roles in TARGET_ROLE_ASSIGNMENTS.items():
            if not frappe.db.exists("User", user):
                print(f"SKIP missing user: {user}")
                continue

            doc = frappe.get_doc("User", user)
            print(f"\nUSER {user}")
            print(f"  role_profile_before={doc.role_profile_name!r}")

            if args.clear_role_profile and doc.role_profile_name:
                print("  CLEAR role_profile_name")
                if not dry_run:
                    doc.role_profile_name = ""

            if args.remove_legacy:
                for legacy in sorted(LEGACY_ROLES_TO_REMOVE_IN_CANDIDATE):
                    if has_child_role(doc, legacy):
                        print(f"  REMOVE legacy role {legacy}")
                        if not dry_run:
                            remove_child_role(doc, legacy)

            if args.strict_target_roles:
                roles_to_remove = (
                    BROAD_PROFILE_ROLES_TO_REMOVE_IN_STRICT_CANDIDATE_TESTS
                    - set(roles)
                    - FOUNDATIONAL_ROLES_TO_KEEP
                )
                for role_to_remove in sorted(roles_to_remove):
                    if has_child_role(doc, role_to_remove):
                        print(f"  REMOVE broad/profile role {role_to_remove}")
                        if not dry_run:
                            remove_child_role(doc, role_to_remove)

            for role in roles:
                if has_child_role(doc, role):
                    print(f"  OK role {role}")
                else:
                    print(f"  ADD role {role}")
                    if not dry_run:
                        doc.append("roles", {"role": role})

            if user in EXTERNAL_BUILDERS:
                for role in ["Builder", "Manufacturing User"]:
                    if has_child_role(doc, role):
                        print(f"  REMOVE external-builder broad role {role}")
                        if not dry_run:
                            remove_child_role(doc, role)

            if not dry_run:
                doc.save(ignore_permissions=True)

        for user, supplier in EXTERNAL_BUILDERS.items():
            if frappe.db.exists("User", user):
                ensure_supplier_permission(user, supplier, dry_run)

        if not dry_run:
            frappe.db.commit()
            frappe.clear_cache()
            print("\nCOMMITTED candidate role assignments")
        else:
            print("\nDRY RUN ONLY. Re-run with --confirm-candidate to apply.")
    finally:
        frappe.destroy()


if __name__ == "__main__":
    sys.exit(main())
