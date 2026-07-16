app_name = "inductone_tools"
app_title = "InductOne Tools"
app_publisher = "Plus One Robotics"
app_description = "InductOne configuration and BOM tooling"
app_email = ""
app_license = "MIT"

app_include_js = [
    "/assets/inductone_tools/js/guidance.js",
]

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

    "Engineering Signoff": {
        "before_insert": "inductone_tools.engineering_signoff.before_insert_signoff",
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

    "InductOne Field Change Request": {
        "validate": "inductone_tools.field_change.validate_field_change_request",
    },

    "InductOne Field Change": {
        "validate": "inductone_tools.field_change.validate_field_change",
    },

    "POR Physical Location": {
        "before_validate": "inductone_tools.physical_location.validate_por_physical_location",
    },

    "InductOne Builder Tranche": {
        "validate": "inductone_tools.serial_allocation.tranche.validate_tranche",
    },

    "InductOne Build Completion": {
        "validate": "inductone_tools.build_completion.validate_build_completion",
    },
}

after_migrate = "inductone_tools.guidance.after_migrate"

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
    "InductOne Configuration Order": "inductone_tools.external_builder_permissions.restrict_configuration_order_permission",
    "InductOne Build Completion": "inductone_tools.external_builder_permissions.restrict_build_completion_permission",
}

fixtures = [
    {
        "dt": "Module Def",
        "filters": [
            ["name", "in", [
                "Finance - POR"
            ]]
        ]
    },
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
                "inductone-csa-owner-handbook",
                "inductone-csa-quality-system",
                "inductone-csa-controlled-records-index",
                "3hmhgl7qdu",
                "3hmdga44m5",
                "3hmiq2lbi9",
                "3hngf036ne",
                "3hmtouafd5",
                "82vdqj03n2",
                "3hmbhanak2",
                "eo88s4k9ui",
                "3hmeksuks8",
                "inductone-field-change-fco-register"
            ]]
        ]
    },
    {
        "dt": "Workspace",
        "filters": [
            ["name", "in", [
                "Operations",
                "Engineering",
                "Builder Portal",
                "Financial Reports",
                "Home",
                "Manufacturing",
                "Payables",
                "Receivables",
                "Selling",
                "Stock",
                "Welcome Workspace"
            ]]
        ]
    },
    {
        "dt": "Custom HTML Block",
        "filters": [
            ["name", "in", [
                "Builder Banner",
                "Builder Guidance Panel",
                "Help and contact",
                "Operations Banner",
                "Operations Guidance Panel",
                "Engineering Banner",
                "Engineering Banner Info",
                "Engineering Banner Workflows",
                "Engineering Banner Reference",
                "Engineering Banner Resources",
                "Branded Banner",
                "Roll Callout cards",
                "URL",
                "Whats New Banner"
            ]]
        ]
    },
    {
        "dt": "Module Onboarding",
        "filters": [
            ["name", "in", [
                "InductOne External Builder Onboarding"
            ]]
        ]
    },
    {
        "dt": "Onboarding Step",
        "filters": [
            ["name", "in", [
                "Receive an InductOne Build",
                "Download the release package",
                "Upload the builder serial workbook",
                "Respond to a rejected Build Completion"
            ]]
        ]
    },
    {
        "dt": "Report",
        "filters": [
            ["name", "in", [
                "Electrical Balloon Callouts",
                "Configured Snapshot Diff",
                "FCO Assignments Pending Review",
                "SUP-FCO-R01 Field Change Register",
                "Delivery Note by PO"
            ]]
        ]
    },
    {
        "dt": "Print Format",
        "filters": [
            ["name", "in", [
                "InductOne Options Catalog",
                "InductOne Options Catalog - Comprehensive",
                "CO-ATTACHED-README",
                "InductOne Configuration Order - Builder Release"
            ]]
        ]
    },
    {
        "dt": "Number Card",
        "filters": [
            ["name", "in", [
                "Builder - Awaiting Acknowledgement",
                "Builder - Completed",
                "Builder - In Progress",
                "Builder - Submitted",
                "InductOne - Accepted",
                "InductOne - Configuring",
                "InductOne - Needs Review",
                "InductOne — At builder",
                "InductOne — Awaiting ack",
                "InductOne — Ready to release"
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
                "InductOne Options Catalog",
                "InductOne Build Option Selection",
                "InductOne Configuration Option Mapping",
                "InductOne Build Completion",
                "InductOne Build Completion Serial",
                "InductOne As-Built Record",
                "InductOne As-Built Serial",
                "InductOne Instance",
                "InductOne Field Change Request",
                "InductOne Field Change",
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
                "Configured BOM Snapshot Structural Effect",
                "InductOne Configuration Option Mapping",
                "Item",
                "Product Bundle"
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
                "InductOne Configuration Option Review Button",
                "InductOne Guidance - Configuration Order",
                "InductOne Guidance - Build Completion",
                "InductOne Guidance - Operations Build",
                "InductOne Guidance - Engineering Signoff",
                "InductOne Guidance - Configuration Option",
                "InductOne FCO JotForm Import Button"
            ]]
        ]
    }
]
