import frappe
from frappe import _


@frappe.whitelist()
def accept_completion_create_as_built(completion_name, as_built_notes=None):
    """
    Atomic operation:
      1. Create InductOne As-Built Record (auto-locked)
      2. Copy serials from Build Completion to As-Built
      3. Set Build Completion status to Accepted
      4. Update parent Build with as_built_record link and completion_status
      5. Transition CO to Closed
    """
    if not completion_name:
        frappe.throw(_("completion_name is required."))

    completion = frappe.get_doc("InductOne Build Completion", completion_name)

    if completion.status != "Reviewed":
        frappe.throw(_(
            "Build Completion must be in status 'Reviewed' before acceptance. "
            "Current status: {0}"
        ).format(completion.status))

    if not (completion.serials or []):
        frappe.throw(_("Cannot accept: no serial rows present on Build Completion."))

    if not completion.inductone_build:
        frappe.throw(_("Build Completion is missing the parent InductOne Build link."))

    if not completion.configuration_order:
        frappe.throw(_("Build Completion is missing the Configuration Order link."))

    build_name = completion.inductone_build
    co_name = completion.configuration_order

    build = frappe.get_doc("InductOne Build", build_name)

    if getattr(build, "as_built_record", None):
        frappe.throw(_(
            "InductOne Build {0} already has an As-Built Record ({1}). "
            "A build can only have one As-Built Record."
        ).format(build_name, build.as_built_record))

    now = frappe.utils.now_datetime()
    user = frappe.session.user

    # 1 + 2: Create the As-Built Record with serials copied in
    as_built = frappe.new_doc("InductOne As-Built Record")
    as_built.inductone_build = build_name
    as_built.configuration_order = co_name
    as_built.build_completion = completion.name

    if getattr(completion, "configured_snapshot", None):
        as_built.configured_snapshot = completion.configured_snapshot

    if getattr(completion, "builder_supplier", None):
        as_built.builder_supplier = completion.builder_supplier

    as_built.created_at = now
    as_built.created_by = user
    as_built.accepted_at = now
    as_built.accepted_by = user

    if as_built_notes:
        as_built.notes = as_built_notes

    # Auto-lock on creation per design
    as_built.status = "Locked"
    as_built.lock_notes = "Auto-locked at acceptance by {0} on {1}".format(user, now)

    # Copy serials with source traceability
    for src_row in completion.serials:
        as_built.append("serials", {
            "item_code": src_row.item_code,
            "item_name": src_row.item_name,
            "serial_number": src_row.serial_number,
            "source_completion_row": src_row.name,
            "notes": src_row.notes
        })

    as_built.insert(ignore_permissions=True)

    # 3: Update Build Completion
    completion.status = "Accepted"
    if hasattr(completion, "reviewed_by") and not completion.reviewed_by:
        completion.reviewed_by = user
    if hasattr(completion, "reviewed_at") and not completion.reviewed_at:
        completion.reviewed_at = now
    completion.save(ignore_permissions=True)

    # 4: Update parent Build
    build_updates = {
        "as_built_record": as_built.name,
        "completion_status": "Accepted",
        "completed_at": now,
        "latest_build_completion": completion.name
    }
    for field, value in build_updates.items():
        if hasattr(build, field):
            setattr(build, field, value)
    build.save(ignore_permissions=True)

    # 5: Transition CO to Closed
    try:
        co = frappe.get_doc("InductOne Configuration Order", co_name)
        if hasattr(co, "co_status"):
            co.co_status = "Closed"
            co.save(ignore_permissions=True)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "accept_completion_create_as_built: CO status transition"
        )

    frappe.db.commit()

    return {
        "ok": True,
        "as_built_name": as_built.name,
        "completion_name": completion.name,
        "build_name": build_name,
        "configuration_order": co_name,
        "co_status": "Closed"
    }