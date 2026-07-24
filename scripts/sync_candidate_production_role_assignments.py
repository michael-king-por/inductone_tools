"""Align candidate sandbox users to verified production role assignments.

This is candidate-only validation tooling. It clears stale Role Profiles and
role sprawl from restored candidate users so baseline-vs-candidate regression
diffs measure the intended production state rather than backup contamination.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import frappe


DEFAULT_EVIDENCE_DIR = Path("/mnt/c/hub/frappe-sandbox/validation-evidence")

ROLE_ASSIGNMENTS = {
    "ian.deliz@plusonerobotics.com": ["System Manager"],
    "matt.speer@plusonerobotics.com": ["Global Viewer"],
    "matthew.mcmillan@plusonerobotics.com": ["Procurement User"],
    "patty.gomez@plusonerobotics.com": ["Operations Manager", "Inventory Operator"],
    "ryan.hannon@plusonerobotics.com": ["Operations Manager"],
    "nathaniel.pantuso@plusonerobotics.com": [
        "Operations Manager",
        "Inventory Operator",
        "Gripper Manufacturer",
    ],
    "jim.haws@plusonerobotics.com": ["InductOne Manager", "Operations Manager"],
    "christina.gt@plusonerobotics.com": [
        "Engineering User",
        "InductOne Manager",
        "Operations Manager",
    ],
    "david.brain@plusonerobotics.com": [
        "Engineering User",
        "InductOne Manager",
        "Operations Manager",
    ],
    "david.moreno@plusonerobotics.com": [
        "Engineering User",
        "Operations Viewer",
    ],
    "shaun.edwards@plusonerobotics.com": ["Engineering User"],
    "jason.minica@plusonerobotics.com": ["Engineering User", "Operations Viewer"],
    "wayne.kirk@plusonerobotics.com": ["Engineering User", "Operations Viewer"],
    "michael.king@plusonerobotics.com": [
        "Engineering User",
        "Inventory Operator",
        "InductOne Process Architect",
        "Operations Manager",
    ],
    "lam@plusonerobotics.com": ["InductOne External Builder"],
    "motion.builder@plusonerobotics.com": ["InductOne External Builder"],
    "austin.dominguez@plusonerobotics.com": ["Operations Viewer"],
    "ben.garishodge@plusonerobotics.com": ["Operations Viewer"],
    "gilbert.bailey@plusonerobotics.com": ["Operations Viewer"],
    "james.nelson@plusonerobotics.com": ["Operations Viewer"],
    "manuel.carvalho@plusonerobotics.com": ["Operations Viewer"],
    "manuel.cortez@plusonerobotics.com": ["Operations Viewer"],
    "mariafernanda.amaya@plusonerobotics.com": ["Operations Viewer"],
    "marina.lobo@plusonerobotics.com": ["Operations Viewer"],
    "zohair.naqvi@plusonerobotics.com": ["Operations Viewer"],
}

DISABLE_USERS = [
    "alyza.salinas@plusonerobotics.com",
    "quickbooks.integration@plusonerobotics.com",
]

UNDECIDED_USERS = ["hana.macinnis@plusonerobotics.com"]


def replace_roles(user: str, roles: list[str]) -> dict:
    before = {
        "enabled": frappe.db.get_value("User", user, "enabled"),
        "role_profile_name": frappe.db.get_value("User", user, "role_profile_name"),
        "roles": frappe.get_roles(user) if frappe.db.exists("User", user) else [],
    }
    if not frappe.db.exists("User", user):
        return {"user": user, "missing": True, "before": before, "after": None}

    frappe.db.set_value("User", user, "enabled", 1)
    frappe.db.set_value("User", user, "role_profile_name", "")
    frappe.db.delete("Has Role", {"parent": user, "parenttype": "User"})
    for idx, role in enumerate(roles, start=1):
        frappe.get_doc(
            {
                "doctype": "Has Role",
                "parent": user,
                "parenttype": "User",
                "parentfield": "roles",
                "idx": idx,
                "role": role,
            }
        ).insert(ignore_permissions=True)
    frappe.clear_cache(user=user)
    after = {
        "enabled": frappe.db.get_value("User", user, "enabled"),
        "role_profile_name": frappe.db.get_value("User", user, "role_profile_name"),
        "roles": frappe.get_roles(user),
    }
    return {"user": user, "target_roles": roles, "before": before, "after": after}


def disable_user(user: str) -> dict:
    before = {
        "exists": bool(frappe.db.exists("User", user)),
        "enabled": frappe.db.get_value("User", user, "enabled"),
        "role_profile_name": frappe.db.get_value("User", user, "role_profile_name"),
        "roles": frappe.get_roles(user) if frappe.db.exists("User", user) else [],
    }
    if frappe.db.exists("User", user):
        frappe.db.set_value("User", user, "enabled", 0)
        frappe.clear_cache(user=user)
    after = {
        "enabled": frappe.db.get_value("User", user, "enabled"),
        "role_profile_name": frappe.db.get_value("User", user, "role_profile_name"),
        "roles": frappe.get_roles(user) if frappe.db.exists("User", user) else [],
    }
    return {"user": user, "before": before, "after": after}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", required=True)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument(
        "--confirm-candidate",
        action="store_true",
        help="Required safety flag; this script mutates only candidate sandboxes.",
    )
    args = parser.parse_args()

    if not args.confirm_candidate or "candidate" not in args.site:
        raise SystemExit("Refusing to mutate non-candidate site. Pass --confirm-candidate on candidate only.")

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        role_results = [replace_roles(user, roles) for user, roles in ROLE_ASSIGNMENTS.items()]
        disabled_results = [disable_user(user) for user in DISABLE_USERS]
        undecided = [
            {
                "user": user,
                "exists": bool(frappe.db.exists("User", user)),
                "enabled": frappe.db.get_value("User", user, "enabled"),
                "role_profile_name": frappe.db.get_value("User", user, "role_profile_name"),
                "roles": frappe.get_roles(user) if frappe.db.exists("User", user) else [],
                "action": "left unchanged for owner decision",
            }
            for user in UNDECIDED_USERS
        ]
        frappe.db.commit()
    finally:
        frappe.destroy()

    payload = {
        "site": args.site,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assigned": role_results,
        "disabled": disabled_results,
        "undecided": undecided,
    }
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    out = args.evidence_dir / (
        "candidate_production_role_assignment_sync_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Updated {len(role_results)} users; disabled {len(disabled_results)} users.")
    print(f"Undecided left unchanged: {', '.join(UNDECIDED_USERS)}")
    print(f"Evidence: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
