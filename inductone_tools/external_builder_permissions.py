"""Permission gates for external InductOne builders.

The external builder accounts are intentionally allowed to see generated
handoff artifacts, not the live ERPNext source records used to create those
artifacts. The checks in this module keep that boundary in code so it can be
reviewed, tested, and deployed repeatably.
"""

import frappe


EXTERNAL_BUILDER_ROLE = "InductOne External Builder"

BUILDER_VISIBLE_CONFIGURATION_ORDER_STATUSES = {
    "Released",
    "Awaiting Completion",
    "Closed",
    # Kept as an alias for owner-facing language. The current DocType field
    # uses Closed, but this keeps the gate safe if the label is later renamed.
    "Completed",
}

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


def _visible_configuration_order_status_condition(alias="`tabInductOne Configuration Order`"):
    escaped_statuses = ", ".join(
        frappe.db.escape(status)
        for status in sorted(BUILDER_VISIBLE_CONFIGURATION_ORDER_STATUSES)
    )
    return f"{alias}.`co_status` in ({escaped_statuses})"


def _doc_builder_supplier(doc):
    if not doc:
        return None
    if isinstance(doc, str):
        return None
    if isinstance(doc, dict):
        return doc.get("builder_supplier")
    return getattr(doc, "builder_supplier", None)


def _builder_can_see_supplier(doc, user=None):
    supplier = _doc_builder_supplier(doc)
    if not supplier:
        return False
    return supplier in set(_supplier_values(user))


def _configuration_order_is_builder_visible(doc):
    if not doc:
        return False
    status = doc.get("co_status") if isinstance(doc, dict) else getattr(doc, "co_status", None)
    return status in BUILDER_VISIBLE_CONFIGURATION_ORDER_STATUSES


def _completion_configuration_order_is_builder_visible(doc):
    co_name = doc.get("configuration_order") if isinstance(doc, dict) else getattr(doc, "configuration_order", None)
    if not co_name:
        return False
    co_status = frappe.db.get_value("InductOne Configuration Order", co_name, "co_status")
    return co_status in BUILDER_VISIBLE_CONFIGURATION_ORDER_STATUSES


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
        return " and ".join([
            _supplier_in_condition("InductOne Configuration Order", user),
            _visible_configuration_order_status_condition("`tabInductOne Configuration Order`"),
        ])
    return None


def restrict_bom_export_package_for_external_builder(user=None):
    if _is_external_builder_only(user):
        return _supplier_in_condition("BOM Export Package", user)
    return None


def restrict_build_completion_for_external_builder(user=None):
    if _is_external_builder_only(user):
        suppliers = _supplier_values(user)
        if not suppliers:
            return "1=0"

        escaped_suppliers = ", ".join(frappe.db.escape(supplier) for supplier in suppliers)
        return f"""(
            `tabInductOne Build Completion`.`builder_supplier` in ({escaped_suppliers})
            and exists (
                select 1
                from `tabInductOne Configuration Order` co
                where co.name = `tabInductOne Build Completion`.`configuration_order`
                  and {_visible_configuration_order_status_condition("co")}
            )
        )"""
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


def restrict_configuration_order_permission(doc=None, user=None, permission_type=None):
    if not _is_external_builder_only(user):
        return None
    return _builder_can_see_supplier(doc, user) and _configuration_order_is_builder_visible(doc)


def restrict_build_completion_permission(doc=None, user=None, permission_type=None):
    if not _is_external_builder_only(user):
        return None
    return (
        _builder_can_see_supplier(doc, user)
        and _completion_configuration_order_is_builder_visible(doc)
    )
