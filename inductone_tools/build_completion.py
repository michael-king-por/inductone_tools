import frappe
from frappe import _
from frappe.utils import now_datetime


@frappe.whitelist()
def create_completion_from_upload(
    build_name,
    completion_file_url,
    submitted_by_name=None,
    builder_reference=None,
    completion_notes=None
):
    """
    Create an InductOne Build Completion record from an uploaded builder workbook.
    
    Called from the Upload Builder Completion dialog on the InductOne Build form.
    
    Behavior:
      - Validates the parent build and its CO are in the right state
      - Creates a Build Completion record with status='Submitted'
      - Inherits builder_supplier from the parent build for User Permission scoping
      - Attaches the uploaded workbook file as evidence
      - Stamps parent Build with latest_build_completion link
      - Leaves serials table empty - Ops transcribes during review
    """
    if not build_name:
        frappe.throw(_("build_name is required."))
    if not completion_file_url:
        frappe.throw(_("completion_file_url is required."))

    build = frappe.get_doc("InductOne Build", build_name)

    if not build.latest_config_order:
        frappe.throw(_(
            "Build {0} has no Configuration Order. Cannot create a completion record."
        ).format(build_name))

    co_name = build.latest_config_order
    co = frappe.get_doc("InductOne Configuration Order", co_name)

    expected_status = "Awaiting Completion"
    if co.co_status != expected_status:
        frappe.throw(_(
            "Configuration Order {0} is in status '{1}'. "
            "Build completion can only be uploaded when CO is in '{2}'."
        ).format(co_name, co.co_status, expected_status))

    snapshot_name = build.selected_snapshot or build.latest_snapshot

    completion = frappe.new_doc("InductOne Build Completion")
    completion.inductone_build = build_name
    completion.configuration_order = co_name

    if snapshot_name and hasattr(completion, "configured_snapshot"):
        completion.configured_snapshot = snapshot_name

    if hasattr(completion, "builder_supplier") and getattr(build, "builder_supplier", None):
        completion.builder_supplier = build.builder_supplier

    completion.status = "Submitted"

    if hasattr(completion, "submitted_at"):
        completion.submitted_at = now_datetime()

    if submitted_by_name and hasattr(completion, "submitted_by_name"):
        completion.submitted_by_name = submitted_by_name
    if builder_reference and hasattr(completion, "builder_reference"):
        completion.builder_reference = builder_reference
    if completion_notes and hasattr(completion, "completion_notes"):
        completion.completion_notes = completion_notes

    completion.insert(ignore_permissions=True)

    # Attach the workbook file to the completion record
    if completion_file_url:
        try:
            file_doc = frappe.get_doc({
                "doctype": "File",
                "file_url": completion_file_url,
                "attached_to_doctype": "InductOne Build Completion",
                "attached_to_name": completion.name,
                "is_private": 1
            })
            file_doc.insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                "create_completion_from_upload: file attach"
            )

    # Update parent Build to point at this completion
    build_updates = {
        "latest_build_completion": completion.name,
        "completion_status": "Submitted"
    }
    for field, value in build_updates.items():
        if hasattr(build, field):
            setattr(build, field, value)
    build.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "ok": True,
        "completion_name": completion.name,
        "build_name": build_name,
        "configuration_order": co_name
    }