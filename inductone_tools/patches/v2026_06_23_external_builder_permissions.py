"""Move InductOne users onto a scoped role model.

This patch is intentionally idempotent. It can be run repeatedly in a restored
sandbox while validating the handoff without accumulating duplicate role rows.
"""

import frappe


EXTERNAL_BUILDERS = {
    "motion.builder@plusonerobotics.com": "Motion Controls",
    "lam@plusonerobotics.com": "LAM",
}

PROCESS_MANAGERS = {
    "michael.king@plusonerobotics.com",
    "christina.gt@plusonerobotics.com",
    "jim.haws@plusonerobotics.com",
    "david.brain@plusonerobotics.com",
}

ENGINEERING_APPROVERS = {
    "shaun.edwards@plusonerobotics.com",
    "jason.minica@plusonerobotics.com",
    "wayne.kirk@plusonerobotics.com",
    "david.moreno@plusonerobotics.com",
}

ENGINEERING_DELEGATES = {
    "michael.king@plusonerobotics.com",
    "christina.gt@plusonerobotics.com",
    "david.brain@plusonerobotics.com",
}

PART_NUMBER_MANAGERS = {
    "michael.king@plusonerobotics.com",
    "christina.gt@plusonerobotics.com",
    "david.brain@plusonerobotics.com",
} | ENGINEERING_APPROVERS

TARGET_ROLES = {
    "InductOne External Builder",
    "InductOne Manager",
    "InductOne Process Architect",
    "Operations Viewer",
    "Operations Manager",
    "Inventory Operator",
    "Gripper Manufacturer",
    "Engineering User",
    "Finance Viewer",
    "Procurement User",
}

LEGACY_INDUCTONE_ROLES = {
    "InductOne Process Manager",
    "InductOne Architect",
    "Engineering Signoff Delegate",
    "Part Number Manager",
    "OPS-INDUCTONE-GATEKEEP",
    "PRODUCT-INDUCTONE-GATEKEEP",
}

ROLE_ASSIGNMENTS = {
    "InductOne External Builder": set(EXTERNAL_BUILDERS),
    "InductOne Manager": PROCESS_MANAGERS,
    "InductOne Process Architect": {"michael.king@plusonerobotics.com"},
    "Engineering User": PART_NUMBER_MANAGERS | ENGINEERING_DELEGATES,
}


def execute():
    ensure_roles()
    ensure_role_profiles()
    ensure_role_assignments()
    remove_unintended_new_role_assignments()
    remove_legacy_builder_assignments()
    remove_external_builder_raw_scope()
    remove_legacy_builder_docperms()
    ensure_target_docperms()
    ensure_external_builder_workspace_access()
    frappe.clear_cache()


def ensure_roles():
    for role in TARGET_ROLES:
        if frappe.db.exists("Role", role):
            continue

        frappe.get_doc(
            {
                "doctype": "Role",
                "role_name": role,
                "desk_access": 1,
                "is_custom": 1,
            }
        ).insert(ignore_permissions=True)


def ensure_role_profiles():
    """Ensure single-purpose role profiles exist for audited user assignment."""

    for role_profile in TARGET_ROLES:
        if frappe.db.exists("Role Profile", role_profile):
            doc = frappe.get_doc("Role Profile", role_profile)
            doc.set("roles", [])
        else:
            doc = frappe.get_doc(
                {
                    "doctype": "Role Profile",
                    "role_profile": role_profile,
                }
            )

        doc.append("roles", {"role": role_profile})
        doc.save(ignore_permissions=True)


def ensure_external_builder_role_profile():
    """Backward-compatible wrapper retained for old patch callers."""

    role_profile = "InductOne External Builder"
    if frappe.db.exists("Role Profile", role_profile):
        doc = frappe.get_doc("Role Profile", role_profile)
        doc.set("roles", [])
    else:
        doc = frappe.get_doc(
            {
                "doctype": "Role Profile",
                "role_profile": role_profile,
            }
        )

    doc.append("roles", {"role": "InductOne External Builder"})
    doc.save(ignore_permissions=True)


def ensure_role_assignments():
    for role, users in ROLE_ASSIGNMENTS.items():
        for user in sorted(users):
            add_role(user, role)


def remove_unintended_new_role_assignments():
    """Keep newly introduced InductOne roles scoped to the approved users."""

    for role, intended_users in ROLE_ASSIGNMENTS.items():
        existing_users = frappe.get_all(
            "Has Role",
            fields=["parent"],
            filters={"parenttype": "User", "role": role},
            limit_page_length=5000,
        )
        for row in existing_users:
            if row.parent not in intended_users:
                remove_role(row.parent, role)


def add_role(user, role):
    if not frappe.db.exists("User", user):
        return

    user_doc = frappe.get_doc("User", user)
    if any(row.role == role for row in user_doc.roles):
        return

    user_doc.add_roles(role)


def remove_role(user, role):
    if not frappe.db.exists("User", user):
        return

    frappe.db.delete(
        "Has Role",
        {"parenttype": "User", "parent": user, "role": role},
    )


def remove_legacy_builder_assignments():
    """Stop using the generic Builder role for InductOne supplier access."""

    users = frappe.get_all(
        "Has Role",
        fields=["parent"],
        filters={"parenttype": "User", "role": "Builder"},
        limit_page_length=5000,
    )
    for row in users:
        remove_role(row.parent, "Builder")

    for role in LEGACY_INDUCTONE_ROLES:
        for row in frappe.get_all(
            "Has Role",
            fields=["parent"],
            filters={"parenttype": "User", "role": role},
            limit_page_length=5000,
        ):
            remove_role(row.parent, role)


def remove_external_builder_raw_scope():
    for user, supplier in EXTERNAL_BUILDERS.items():
        if frappe.db.exists("User", user):
            frappe.db.set_value("User", user, "role_profile_name", "InductOne External Builder")
        remove_role(user, "Manufacturing User")
        remove_role(user, "Builder")
        add_role(user, "InductOne External Builder")

        frappe.db.delete(
            "User Permission",
            {
                "user": user,
                "allow": "Item Group",
            },
        )

        if frappe.db.exists("Supplier", supplier):
            ensure_supplier_user_permission(user, supplier)


def ensure_external_builder_workspace_access():
    """Move builder-facing workspaces from the old Builder role to the new role."""

    if frappe.db.exists("Workspace", "Builder Portal"):
        doc = frappe.get_doc("Workspace", "Builder Portal")
        doc.is_hidden = 0
        doc.set("roles", [])
        doc.append("roles", {"role": "InductOne External Builder"})
        doc.save(ignore_permissions=True)

    # Build is deprecated. Do not use it as the external supplier landing page.
    if frappe.db.exists("Workspace", "Build"):
        doc = frappe.get_doc("Workspace", "Build")
        doc.is_hidden = 1
        doc.set("roles", [])
        doc.save(ignore_permissions=True)


def ensure_supplier_user_permission(user, supplier):
    if not frappe.db.exists("User", user):
        return

    if frappe.db.exists(
        "User Permission",
        {
            "user": user,
            "allow": "Supplier",
            "for_value": supplier,
            "applicable_for": "",
        },
    ) or frappe.db.exists(
        "User Permission",
        {
            "user": user,
            "allow": "Supplier",
            "for_value": supplier,
            "applicable_for": ["is", "not set"],
        },
    ):
        return

    frappe.get_doc(
        {
            "doctype": "User Permission",
            "user": user,
            "allow": "Supplier",
            "for_value": supplier,
            "apply_to_all_doctypes": 1,
        }
    ).insert(ignore_permissions=True)


def remove_legacy_builder_docperms():
    for doctype in [
        "Item",
        "BOM",
        "InductOne Configuration Order",
        "BOM Export Package",
        "Configured BOM Snapshot",
        "InductOne Build Completion",
    ]:
        frappe.db.delete(
            "Custom DocPerm",
            {"parent": doctype, "role": "Builder", "permlevel": 0},
        )

    for role in LEGACY_INDUCTONE_ROLES | {"Manufacturing User", "Project Manager", "Projects Manager"}:
        for doctype in [
            "InductOne Build",
            "InductOne Configuration Order",
            "BOM Export Package",
            "Configured BOM Snapshot",
            "InductOne Build Completion",
            "InductOne As-Built Record",
            "InductOne Instance",
            "InductOne Configuration Option",
            "Engineering Signoff",
            "Part Number Allocation Request",
            "Part Number Assignment",
            "InductOne Builder Tranche",
            "Fixture Export Control",
        ]:
            frappe.db.delete(
                "Custom DocPerm",
                {"parent": doctype, "role": role, "permlevel": 0},
            )


def ensure_target_docperms():
    external_read = {"read": 1, "report": 1, "export": 1, "print": 1}
    for doctype in [
        "InductOne Configuration Order",
        "BOM Export Package",
        "Configured BOM Snapshot",
    ]:
        ensure_custom_docperm(doctype, "InductOne External Builder", **external_read)

    ensure_custom_docperm(
        "InductOne Build Completion",
        "InductOne External Builder",
        read=1,
        write=1,
        export=1,
    )

    process = {
        "read": 1,
        "write": 1,
        "create": 1,
        "delete": 0,
        "report": 1,
        "export": 1,
        "print": 1,
        "share": 1,
    }
    for doctype in [
        "InductOne Build",
        "InductOne Configuration Order",
        "BOM Export Package",
        "Configured BOM Snapshot",
        "InductOne Build Completion",
        "InductOne As-Built Record",
        "InductOne Instance",
    ]:
        ensure_custom_docperm(doctype, "InductOne Manager", **process)

    architect = {
        "read": 1,
        "write": 1,
        "create": 1,
        "delete": 1,
        "report": 1,
        "export": 1,
        "print": 1,
        "share": 1,
        "email": 1,
    }
    for doctype in [
        "InductOne Builder Tranche",
        "Fixture Export Control",
        "InductOne Build",
        "InductOne Configuration Order",
        "BOM Export Package",
        "Configured BOM Snapshot",
        "InductOne Build Completion",
        "InductOne As-Built Record",
        "InductOne Instance",
    ]:
        ensure_custom_docperm(doctype, "InductOne Process Architect", **architect)

    signoff = {
        "read": 1,
        "write": 1,
        "create": 1,
        "delete": 0,
        "report": 1,
        "export": 1,
        "print": 1,
        "share": 1,
        "email": 1,
    }
    ensure_custom_docperm("Engineering Signoff", "Engineering User", **signoff)

    part_number = {
        "read": 1,
        "write": 1,
        "create": 1,
        "delete": 0,
        "report": 1,
        "export": 1,
        "print": 1,
        "share": 1,
    }
    for doctype in ["Part Number Allocation Request", "Part Number Assignment"]:
        ensure_custom_docperm(doctype, "Engineering User", **part_number)

    read_only = {"read": 1, "report": 1, "export": 1, "print": 1}
    for doctype in [
        "InductOne Build",
        "InductOne Configuration Order",
        "BOM Export Package",
        "Configured BOM Snapshot",
        "InductOne Build Completion",
        "InductOne As-Built Record",
        "InductOne Instance",
        "InductOne Configuration Option",
        "Engineering Signoff",
        "Part Number Allocation Request",
        "Part Number Assignment",
        "InductOne Builder Tranche",
    ]:
        ensure_custom_docperm(doctype, "Operations Viewer", **read_only)
        ensure_custom_docperm(doctype, "Finance Viewer", **read_only)

    for doctype in [
        "InductOne Build",
        "InductOne Configuration Order",
        "BOM Export Package",
        "Configured BOM Snapshot",
        "InductOne Build Completion",
        "InductOne As-Built Record",
        "InductOne Instance",
        "InductOne Configuration Option",
    ]:
        ensure_custom_docperm(doctype, "Engineering User", **read_only)
        ensure_custom_docperm(doctype, "Operations Manager", **read_only)

    for role in [
        "Operations Viewer",
        "Finance Viewer",
        "InductOne Manager",
        "Engineering User",
        "Operations Manager",
        "Inventory Operator",
        "Gripper Manufacturer",
        "Procurement User",
    ]:
        frappe.db.delete(
            "Custom DocPerm",
            {"parent": "Fixture Export Control", "role": role, "permlevel": 0},
        )

    fixture_export_architect_rows = frappe.get_all(
        "Custom DocPerm",
        filters={
            "parent": "Fixture Export Control",
            "role": "InductOne Process Architect",
            "permlevel": 0,
        },
        pluck="name",
        order_by="modified desc",
    )
    for duplicate_name in fixture_export_architect_rows[1:]:
        frappe.delete_doc(
            "Custom DocPerm",
            duplicate_name,
            ignore_permissions=True,
            force=True,
        )


def ensure_custom_docperm(doctype, role, **perms):
    if not frappe.db.exists("DocType", doctype):
        return

    existing = frappe.db.get_value(
        "Custom DocPerm",
        {"parent": doctype, "role": role, "permlevel": 0},
        "name",
    )
    fields = default_permission_fields()
    fields.update(perms)

    if existing:
        doc = frappe.get_doc("Custom DocPerm", existing)
        for fieldname, value in fields.items():
            setattr(doc, fieldname, value)
        doc.save(ignore_permissions=True)
        return

    frappe.get_doc(
        {
            "doctype": "Custom DocPerm",
            "parent": doctype,
            "parenttype": "DocType",
            "parentfield": "permissions",
            "role": role,
            "permlevel": 0,
            **fields,
        }
    ).insert(ignore_permissions=True)


def default_permission_fields():
    return {
        "read": 0,
        "write": 0,
        "create": 0,
        "delete": 0,
        "submit": 0,
        "cancel": 0,
        "amend": 0,
        "report": 0,
        "export": 0,
        "share": 0,
        "print": 0,
        "email": 0,
        "if_owner": 0,
    }
