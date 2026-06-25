"""Permission gates for external InductOne builders.

The external builder accounts are intentionally allowed to see generated
handoff artifacts, not the live ERPNext source records used to create those
artifacts. The checks in this module keep that boundary in code so it can be
reviewed, tested, and deployed repeatably.
"""

import frappe


EXTERNAL_BUILDER_ROLE = "InductOne External Builder"

RAW_ACCESS_ROLES = {
    "System Manager",
    "InductOne Process Architect",
    "Operations Manager",
    "Inventory Operator",
    "Finance Viewer",
    "Procurement User",
    "Manufacturing User",
    "Manufacturing Manager",
    "Stock User",
    "Stock Manager",
    "Item Manager",
    "Purchase User",
    "Purchase Manager",
    "Sales User",
    "Sales Manager",
}


def _is_external_builder_only(user=None):
    """Return True only for users operating as external builders.

    If an internal user temporarily also has the external builder role, do not
    strip their normal internal access. The hard deny applies only when the
    user does not also carry a role that legitimately owns raw ERPNext records.
    """

    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    return EXTERNAL_BUILDER_ROLE in roles and not bool(roles & RAW_ACCESS_ROLES)


def _supplier_values(user=None):
    user = user or frappe.session.user
    return [
        value
        for value in frappe.get_all(
            "User Permission",
            filters={"user": user, "allow": "Supplier"},
            pluck="for_value",
            limit_page_length=500,
        )
        if value
    ]


def _supplier_in_condition(doctype, user=None):
    suppliers = _supplier_values(user)
    if not suppliers:
        return "1=0"

    escaped_suppliers = ", ".join(frappe.db.escape(supplier) for supplier in suppliers)
    return f"`tab{doctype}`.`builder_supplier` in ({escaped_suppliers})"


def deny_raw_item_for_external_builder(user=None):
    if _is_external_builder_only(user):
        return "1=0"
    return None


def deny_raw_bom_for_external_builder(user=None):
    if _is_external_builder_only(user):
        return "1=0"
    return None


def restrict_configuration_order_for_external_builder(user=None):
    if _is_external_builder_only(user):
        return _supplier_in_condition("InductOne Configuration Order", user)
    return None


def restrict_bom_export_package_for_external_builder(user=None):
    if _is_external_builder_only(user):
        return _supplier_in_condition("BOM Export Package", user)
    return None


def restrict_build_completion_for_external_builder(user=None):
    if _is_external_builder_only(user):
        return _supplier_in_condition("InductOne Build Completion", user)
    return None


def restrict_configured_snapshot_for_external_builder(user=None):
    """Allow snapshots only when linked to the user's assigned handoff records."""

    if not _is_external_builder_only(user):
        return None

    suppliers = _supplier_values(user)
    if not suppliers:
        return "1=0"

    escaped_suppliers = ", ".join(frappe.db.escape(supplier) for supplier in suppliers)
    return f"""(
        exists (
            select 1
            from `tabInductOne Configuration Order` co
            where co.snapshot = `tabConfigured BOM Snapshot`.name
              and co.builder_supplier in ({escaped_suppliers})
        )
        or exists (
            select 1
            from `tabBOM Export Package` bep
            where bep.configured_snapshot = `tabConfigured BOM Snapshot`.name
              and bep.builder_supplier in ({escaped_suppliers})
        )
    )"""


def deny_raw_item_permission(doc=None, user=None, permission_type=None):
    if _is_external_builder_only(user):
        return False
    return None


def deny_raw_bom_permission(doc=None, user=None, permission_type=None):
    if _is_external_builder_only(user):
        return False
    return None
