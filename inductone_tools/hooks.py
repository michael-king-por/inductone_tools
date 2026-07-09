app_name = "inductone_tools"
app_title = "InductOne Tools"
app_publisher = "Plus One Robotics"
app_description = "InductOne configuration and BOM tooling"
app_email = ""
app_license = "MIT"

# Frappe's `bench version` first checks for a branch-specific hook version
# (for this deployment branch, `main_version`) and then falls back to
# inductone_tools.__version__. Keep this in sync with pyproject.toml.
main_version = "3.0.0"

doc_events = {
    "InductOne Configuration Order": {
        "after_insert": "inductone_tools.inductone_tools.doctype.inductone_configuration_order.inductone_configuration_order.enqueue_flat_bom_generation"
    },

    "BOM Export Package": {
        "before_save": "inductone_tools.bom_export.before_save"
    },

    "BOM": {
        "after_insert": "inductone_tools.engineering_signoff.on_target_after_insert",
    },

    "Product Bundle": {
        "after_insert": "inductone_tools.engineering_signoff.on_target_after_insert",
        "validate": "inductone_tools.part_numbering.validate_product_bundle_part_number_control",
    },

    "Item": {
        "validate": "inductone_tools.part_numbering.validate_item_part_number_control",
        "after_insert": [
            "inductone_tools.part_numbering.update_assignment_after_item_save",
            "inductone_tools.engineering_signoff.on_target_after_insert",
        ],
        "on_update": "inductone_tools.part_numbering.update_assignment_after_item_save",
    },

    "InductOne Configuration Option": {
        "before_save": "inductone_tools.engineering_signoff.on_target_save",
    },

    "Part Number Allocation Request": {
        "validate": "inductone_tools.part_numbering.validate_allocation_request",
    },

    "Part Number Assignment": {
        "validate": "inductone_tools.part_numbering.validate_part_number_assignment",
    },

    # ============================================================
    # ADDED 2026-06 — server-side validation that was never wired.
    # These three entries are the fix for audit findings C3 and C4.
    # DO NOT deploy this file until the functions they point at exist
    # in the repo (see notes from Claude). All ship in ONE release.
    # ============================================================
    "InductOne Instance": {
        "validate": "inductone_tools.instance.hooks.validate_instance",
    },

    "InductOne Builder Tranche": {
        "validate": "inductone_tools.serial_allocation.tranche.validate_tranche",
    },

    "InductOne Build Completion": {
        "validate": "inductone_tools.build_completion.validate_build_completion",
    },
}

permission_query_conditions = {
    "Item": "inductone_tools.external_builder_permissions.deny_raw_item_for_external_builder",
    "BOM": "inductone_tools.external_builder_permissions.deny_raw_bom_for_external_builder",
    "InductOne Configuration Order": "inductone_tools.external_builder_permissions.restrict_configuration_order_for_external_builder",
    "BOM Export Package": "inductone_tools.external_builder_permissions.restrict_bom_export_package_for_external_builder",
    "InductOne Build Completion": "inductone_tools.external_builder_permissions.restrict_build_completion_for_external_builder",
    "Configured BOM Snapshot": "inductone_tools.external_builder_permissions.restrict_configured_snapshot_for_external_builder",
}

has_permission = {
    "Item": "inductone_tools.external_builder_permissions.deny_raw_item_permission",
    "BOM": "inductone_tools.external_builder_permissions.deny_raw_bom_permission",
}

fixtures = [
    {
        "dt": "DocType",
        "filters": [
            ["module", "in", [
                "Operations - POR",
                "InductOne Tools"
            ]]
        ]
    },
    {
        "dt": "Role",
        "filters": [
            ["name", "in", [
                "InductOne External Builder",
                "InductOne Manager",
                "InductOne Process Architect",
                "Operations Viewer",
                "Operations Manager",
                "Inventory Operator",
                "Gripper Manufacturer",
                "Engineering User",
                "Finance Viewer",
                "Procurement User"
            ]]
        ]
    },
    {
        "dt": "Role Profile",
        "filters": [
            ["name", "in", [
                "InductOne External Builder",
                "InductOne Manager",
                "InductOne Process Architect",
                "Operations Viewer",
                "Operations Manager",
                "Inventory Operator",
                "Gripper Manufacturer",
                "Engineering User",
                "Finance Viewer",
                "Procurement User"
            ]]
        ]
    },
    {
        "dt": "Wiki Page",
        "filters": [
            ["name", "in", [
                "d0v7dsi9lu",
                "9n8bvqedso",
                "3hnmdg9m5q",
                "inductone-csa-owner-handbook"
            ]]
        ]
    },
    {
        "dt": "Workspace",
        "filters": [
            ["name", "in", [
                "Operations"
            ]]
        ]
    },
    {
        "dt": "Report",
        "filters": [
            ["name", "in", [
                "Electrical Balloon Callouts"
            ]]
        ]
    },
    {
        "dt": "InductOne Configuration Option",
        "filters": [["option_code", "like", "DEV-%"]]
    },
    {
        "dt": "Custom DocPerm",
        "filters": [
            ["parent", "in", [
                "InductOne Build",
                "BOM Export Package",
                "POR Physical Location",
                "BOM Export Package Item",
                "Configured BOM Snapshot",
                "Configured BOM Snapshot Item",
                "InductOne Build Execution Log",
                "InductOne Builder Tranche",
                "InductOne Configuration Option",
                "InductOne Build Option Selection",
                "InductOne Configuration Option Mapping",
                "InductOne Build Completion",
                "InductOne Build Completion Serial",
                "InductOne As-Built Record",
                "InductOne As-Built Serial",
                "InductOne Instance",
                "InductOne Configuration Order",
                "InductOne Configuration Order Delta Line",
                "InductOne Configuration Order Selected Option",
                "InductOne Configuration Order Document Index",
                "Engineering Signoff",
                "Part Number Allocation Request",
                "Part Number Assignment",
                "Fixture Export Control"
            ]]
        ]
    },
    {
        "dt": "Custom Field",
        "filters": [
            ["dt", "in", [
                "InductOne Build",
                "BOM Export Package",
                "Configured BOM Snapshot",
                "InductOne Build Completion",
                "InductOne Build Completion Serial",
                "InductOne As-Built Record",
                "InductOne As-Built Serial",
                "InductOne Configuration Order",
                "InductOne Configuration Order Delta Line",
                "InductOne Configuration Order Selected Option",
                "InductOne Configuration Order Document Index",
                "BOM Item",
                "Configured BOM Snapshot Structural Effect"
            ]]
        ]
    },
    {
        "dt": "Property Setter",
        "filters": [
            ["doc_type", "in", [
                "InductOne Build",
                "BOM Export Package",
                "Configured BOM Snapshot",
                "InductOne Build Completion",
                "InductOne Build Completion Serial",
                "InductOne As-Built Record",
                "InductOne As-Built Serial",
                "InductOne Configuration Order",
                "InductOne Configuration Order Delta Line",
                "InductOne Configuration Order Selected Option",
                "InductOne Configuration Order Document Index"
            ]]
        ]
    },
    {
        "dt": "Client Script",
        "filters": [
            ["name", "in", [
                "minimal",
                "Attachment_display",
                "generate_zip",
                "InductOne Selection Prevention",
                "Sales Order Build Button",
                "Load Catalog Options - Enforce Group-of Exclusivity",
                "InductOne Configuration Export Package",
                "InductOne As-Built Record Script",
                "Options Catalog Print Button",
                "InductOne Build Script",
                "InductOne Build Completion Script",
                "Fixture Export Control Script",
                "InductOne List Formatting",
                "InductOne Build HTML Controls",
                "InductOne Build Supplier Population",
                "Engineering Signoff Actions",
                "BOM Engineering Signoff Banner",
                "Product Bundle Engineering Signoff Banner",
                "InductOne Instance Script",
                "Part Number Allocation Request - Allocate Numbers Button",
                "Item Part Number Integration",
                "Product Bundle Part Number Allocation Script",
                "InductOne Configuration Option styling",
                "Engineering Signoff Banner - Item",
                "Engineering Signoff Banner - Configuration Option",
                "InductOne Configuration Option Review Button"
            ]]
        ]
    }
]
