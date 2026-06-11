app_name = "inductone_tools"
app_title = "InductOne Tools"
app_publisher = "Plus One Robotics"
app_description = "InductOne configuration and BOM tooling"
app_email = ""
app_license = "MIT"

doc_events = {
    "InductOne Configuration Order": {
        "after_insert": "inductone_tools.inductone_tools.doctype.inductone_configuration_order.inductone_configuration_order.enqueue_flat_bom_generation"
    },

    "BOM Export Package": {
        "before_save": "inductone_tools.bom_export.before_save"
    },

    "BOM": {
        "before_save": "inductone_tools.engineering_signoff.on_target_save",
        "after_insert": "inductone_tools.engineering_signoff.on_target_after_insert",
        "on_update": "inductone_tools.engineering_signoff.on_target_after_save",
    },

    "Product Bundle": {
        "before_save": "inductone_tools.engineering_signoff.on_target_save",
        "after_insert": "inductone_tools.engineering_signoff.on_target_after_insert",
        "validate": "inductone_tools.part_numbering.validate_product_bundle_part_number_control",
        "on_update": "inductone_tools.engineering_signoff.on_target_after_save",
    },

    "Item": {
        "validate": "inductone_tools.part_numbering.validate_item_part_number_control",
        "after_insert": [
            "inductone_tools.part_numbering.update_assignment_after_item_save",
            "inductone_tools.engineering_signoff.on_target_after_insert",
        ],
        "on_update": [
            "inductone_tools.part_numbering.update_assignment_after_item_save",
            "inductone_tools.engineering_signoff.on_target_after_save",
        ],
        "before_save": "inductone_tools.engineering_signoff.on_target_save",
    },

    "InductOne Configuration Option": {
        "before_save": "inductone_tools.engineering_signoff.on_target_save",
        "after_insert": "inductone_tools.engineering_signoff.on_target_after_insert",
        "on_update": "inductone_tools.engineering_signoff.on_target_after_save",
    },

    "Part Number Allocation Request": {
        "validate": "inductone_tools.part_numbering.validate_allocation_request",
    },

    "Part Number Assignment": {
        "validate": "inductone_tools.part_numbering.validate_part_number_assignment",
    },
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
                "InductOne Configuration Option",
                "InductOne Build Option Selection",
                "InductOne Configuration Option Mapping",
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
                "InductOne Configuration Order Document Index"
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
        "dt": "Client Script"
    }
]