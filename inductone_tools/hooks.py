app_name = "inductone_tools"
app_title = "InductOne Tools"
app_publisher = "Plus One Robotics"
app_description = "InductOne configuration and BOM tooling"
app_email = ""
app_license = "MIT"

doc_events = {
    "InductOne Configuration Order": {
        "after_insert": "inductone_tools.inductone_tools.doctype.inductone_configuration_order.inductone_configuration_order.enqueue_flat_bom_generation"
    }
}

fixtures = [
    {
        "dt": "DocType",
        "filters": [
            ["name", "in", [
                "InductOne Configuration Order",
                "InductOne Configuration Order Delta Line",
                "InductOne Configuration Order Document Index"
            ]]
        ]
    },
    {
        "dt": "Custom DocPerm",
        "filters": [
            ["parent", "in", [
                "InductOne Configuration Order",
                "InductOne Configuration Order Delta Line",
                "InductOne Configuration Order Document Index"
            ]]
        ]
    },
    {
        "dt": "Custom Field",
        "filters": [
            ["dt", "in", [
                "InductOne Configuration Order",
                "InductOne Configuration Order Delta Line",
                "InductOne Configuration Order Document Index"
            ]]
        ]
    },
    {
        "dt": "Property Setter",
        "filters": [
            ["doc_type", "in", [
                "InductOne Configuration Order",
                "InductOne Configuration Order Delta Line",
                "InductOne Configuration Order Document Index"
            ]]
        ]
    }
]
