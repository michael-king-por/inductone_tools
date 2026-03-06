import frappe


def enqueue_flat_bom_generation(doc, method=None):
    """
    Called automatically after insert via hooks.py.
    Enqueues background generation of snapshot-based flat BOM CSV.
    """

    # Set Pending/Running quickly in-db (avoid conflicts)
    frappe.db.set_value(doc.doctype, doc.name, {
        "flat_bom_status": "Pending",
        "flat_bom_error": ""
    })

    # Enqueue background job
    frappe.enqueue(
        "inductone_tools.inductone_tools.configured_bom.flat_bom.build_and_attach_flat_bom_for_config_order",
        queue="short",
        job_name=f"flat_bom_csv::{doc.name}",
        config_order_name=doc.name
    )