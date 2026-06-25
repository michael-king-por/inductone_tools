import frappe
from frappe import _

from inductone_tools.instance.creation import (
    create_instance_from_as_built,
)


def _require_completion_accept_role():
    roles = set(frappe.get_roles(frappe.session.user))
    if not {"InductOne Manager", "InductOne Process Architect", "System Manager"} & roles:
        frappe.throw(
            _("This action requires the 'InductOne Manager' role."),
            frappe.PermissionError,
        )


@frappe.whitelist()
def accept_completion_create_as_built(completion_name, as_built_notes=None):
    """
    Atomic operation:
      1. Create InductOne As-Built Record (auto-locked)
      2. Copy serials from Build Completion to As-Built
      3. Set Build Completion status to Accepted
      4. Update parent Build with as_built_record link and completion_status
      5. Transition CO to Closed
      6. Create the InductOne Instance (the deployed-unit record)

    Step 6 is new. The Instance is the entity Support will reference for
    the life of the unit. It is created here, in the same transaction, so
    that acceptance is never partially complete.
    """
    _require_completion_accept_role()

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

    # Precondition for Instance creation downstream: the Build must have a
    # system_serial allocated. Fail loudly here, before mutating anything.
    if not getattr(build, "system_serial", None):
        frappe.throw(_(
            "InductOne Build {0} has no system_serial. The stenciled serial "
            "must be allocated at builder release before acceptance can complete. "
            "Open the Build and use 'Allocate Serial' from the Builder Tranche."
        ).format(build_name))

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

    # Mirror system_serial onto As-Built so the printed record carries it.
    if getattr(build, "system_serial", None) and hasattr(as_built, "system_serial"):
        as_built.system_serial = build.system_serial

    if as_built_notes:
        as_built.notes = as_built_notes

    as_built.status = "Locked"
    as_built.lock_notes = "Auto-locked at acceptance by {0} on {1}".format(user, now)

    # Copy serials with source traceability. component_label carries the
    # workbook label (e.g. "Robot 1 Gripper Upper"); it is populated for
    # rows that came from the auto-parsed builder workbook and may be empty
    # for rows that were added manually before workbook import. It is only
    # set when the source row has it, for forward/backward compatibility.
    for src_row in completion.serials:
        row_data = {
            "item_code": src_row.item_code,
            "item_name": src_row.item_name,
            "serial_number": src_row.serial_number,
            "source_completion_row": src_row.name,
            "notes": src_row.notes,
        }
        src_label = getattr(src_row, "component_label", None)
        if src_label:
            row_data["component_label"] = src_label
        as_built.append("serials", row_data)

    as_built.insert(ignore_permissions=True)

    # 3: Update Build Completion.
    # The transition to 'Accepted' is gated server-side (see
    # build_completion.validate_build_completion): a direct write to
    # 'Accepted' is refused UNLESS this flag is set, which guarantees the
    # As-Built / Instance / CO-close side effects can never be bypassed.
    completion.status = "Accepted"
    if hasattr(completion, "reviewed_by") and not completion.reviewed_by:
        completion.reviewed_by = user
    if hasattr(completion, "reviewed_at") and not completion.reviewed_at:
        completion.reviewed_at = now

    frappe.flags.io_acceptance_in_progress = True
    try:
        completion.save(ignore_permissions=True)
    finally:
        frappe.flags.io_acceptance_in_progress = False

    # 4: Update parent Build
    build_updates = {
        "as_built_record": as_built.name,
        "completion_status": "Accepted",
        "completed_at": now,
        "latest_build_completion": completion.name,
        "build_status": "COMPLETED"
    }
    for field, value in build_updates.items():
        if hasattr(build, field):
            setattr(build, field, value)
    build.save(ignore_permissions=True)

    # 5: Transition CO to Closed.
    # This is part of the ATOMIC acceptance. If it fails, the whole
    # operation must fail and roll back — we must never report success while
    # leaving the CO open. There is deliberately NO broad try/except here:
    # an exception propagates, the request transaction rolls back (nothing
    # above has been committed yet), and the caller sees a real error.
    co = frappe.get_doc("InductOne Configuration Order", co_name)
    if not hasattr(co, "co_status"):
        frappe.throw(_(
            "Configuration Order {0} has no co_status field; cannot close it."
        ).format(co_name))
    co.co_status = "Closed"
    co.save(ignore_permissions=True)

    # 6: Create the InductOne Instance
    instance_name = create_instance_from_as_built(as_built.name, user=user)

    frappe.db.commit()

    # Report the PERSISTED CO status, read back from the database, rather
    # than asserting a hardcoded value. If anything above had failed we
    # would not have reached this point.
    final_co_status = frappe.db.get_value(
        "InductOne Configuration Order", co_name, "co_status"
    )

    return {
        "ok": True,
        "as_built_name": as_built.name,
        "completion_name": completion.name,
        "build_name": build_name,
        "configuration_order": co_name,
        "co_status": final_co_status,
        "instance_name": instance_name,
    }
