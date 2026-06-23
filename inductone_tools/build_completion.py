import frappe
from frappe import _
from frappe.utils import now_datetime

from inductone_tools.build_completion_workbook_parser import (
    parse_builder_workbook,
    validate_workbook_against_build,
    WorkbookParseError,
)


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
      - PARSES the workbook and populates the serials child table with
        one row per Section B-I label (component_label + serial_number;
        empty cells produce empty serial_number rows so missing entries
        are visible)
      - Cross-validates the workbook's IND serial against the Build's
        allocated system_serial; mismatches go into completion_notes as
        a prominent warning
      - Stamps parent Build with latest_build_completion link
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

    # --- Parse the workbook BEFORE creating any records ---
    # If the workbook is structurally broken, fail before we mutate state.
    # The file is already saved (the dialog uploaded it as an Attach field),
    # so we read it from disk via the file_url.
    workbook_bytes = _read_file_bytes_from_url(completion_file_url)

    try:
        parsed = parse_builder_workbook(workbook_bytes)
    except WorkbookParseError as e:
        frappe.throw(_(
            "Could not parse the uploaded workbook: {0}"
        ).format(str(e)))

    # Cross-validate the workbook's IND serial against the Build.
    # Mismatches are NON-fatal — the upload still goes through, but the
    # warning lands in completion_notes so ops sees it during review.
    serial_warnings = validate_workbook_against_build(
        parsed, getattr(build, "system_serial", None)
    )

    snapshot_name = build.selected_snapshot or build.latest_snapshot

    completion = frappe.new_doc("InductOne Build Completion")
    completion.inductone_build = build_name
    completion.configuration_order = co_name

    if snapshot_name and hasattr(completion, "configured_snapshot"):
        completion.configured_snapshot = snapshot_name

    if hasattr(completion, "builder_supplier") and getattr(build, "builder_supplier", None):
        completion.builder_supplier = build.builder_supplier

    if hasattr(completion, "builder_contact_name") and getattr(build, "builder_poc", None):
        contact = frappe.db.get_value(
            "Contact",
            build.builder_poc,
            ["full_name", "first_name", "last_name"],
            as_dict=True
        ) or {}

        name = contact.get("full_name")
        if not name:
            first = contact.get("first_name") or ""
            last = contact.get("last_name") or ""
            name = (first + " " + last).strip()

        if name:
            completion.builder_contact_name = name

    completion.status = "Submitted"

    if hasattr(completion, "submitted_at"):
        completion.submitted_at = now_datetime()

    if submitted_by_name and hasattr(completion, "submitted_by_name"):
        completion.submitted_by_name = submitted_by_name
    if builder_reference and hasattr(completion, "builder_reference"):
        completion.builder_reference = builder_reference

    # Combine user-supplied notes with serial-mismatch warnings if any.
    notes_parts = []
    if serial_warnings:
        notes_parts.append("=== WORKBOOK VALIDATION WARNINGS ===")
        notes_parts.extend(serial_warnings)
        notes_parts.append("")  # blank line separator
    if completion_notes:
        notes_parts.append(completion_notes)

    if notes_parts and hasattr(completion, "completion_notes"):
        completion.completion_notes = "\n".join(notes_parts)

    # --- Populate the serials child table from parsed workbook ---
    # One row per Section B-I label, including empty ones (per design:
    # missing serials should be visible in the table, not silently dropped).
    # item_code is left blank; component_label carries the workbook's
    # column-A text; serial_number is the column-B value.
    for component in parsed["components"]:
        row_data = {
            "serial_number": component["serial_number"],
        }
        # Both 'component_label' (new field) and 'item_name' are populated
        # with the workbook label for now. item_name is the legacy field
        # name; once it's deprecated, only component_label will be needed.
        if _completion_serial_has_field("component_label"):
            row_data["component_label"] = component["component_label"]
        if _completion_serial_has_field("item_name"):
            row_data["item_name"] = component["component_label"]
        completion.append("serials", row_data)

    completion.insert(ignore_permissions=True)

    # Attach the workbook file to the completion record (in addition to
    # the Build, where the dialog initially attached it).
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
        "configuration_order": co_name,
        "component_rows": len(parsed["components"]),
        "filled_rows": sum(1 for c in parsed["components"] if c["serial_number"]),
        "empty_rows": sum(1 for c in parsed["components"] if not c["serial_number"]),
        "serial_warnings": serial_warnings,
    }


def _read_file_bytes_from_url(file_url):
    """Read the raw bytes of a file from its Frappe file_url.

    The file_url is like '/private/files/foo.xlsx' or '/files/foo.xlsx'.
    Frappe's File doctype tracks these and frappe.utils.file_manager
    has helpers, but reading the file directly off disk is simpler and
    avoids permission edge cases inside an already-whitelisted endpoint.
    """
    from frappe.utils.file_manager import get_file_path

    # frappe.db.get_value on File by file_url is the canonical resolver
    file_doc_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not file_doc_name:
        frappe.throw(_(
            "Could not find File record for upload URL '{0}'. "
            "The file may not have been saved properly."
        ).format(file_url))

    file_doc = frappe.get_doc("File", file_doc_name)
    full_path = get_file_path(file_doc.file_url)

    with open(full_path, "rb") as f:
        return f.read()


_field_cache = {}

def _completion_serial_has_field(fieldname):
    """Memoized check: does the InductOne Build Completion Serial child
    table have a given fieldname? Used to keep the parser-import code
    forward-compatible: if `component_label` hasn't been added yet, we
    still populate `item_name`. Once it's added, both fields fill, and
    when item_name is eventually removed, only component_label fills."""
    if fieldname in _field_cache:
        return _field_cache[fieldname]
    meta = frappe.get_meta("InductOne Build Completion Serial")
    has = bool(meta.get_field(fieldname))
    _field_cache[fieldname] = has
    return has


# ============================================================
#  Server-side state machine + required-field guard
#  Registered in hooks.py:
#    doc_events["InductOne Build Completion"]["validate"]
#  ADDED 2026-06 — audit finding C4.
# ============================================================

# Forward-only Build Completion lifecycle.
#   Draft     -> Submitted
#   Submitted -> Reviewed | Rejected
#   Reviewed  -> Accepted | Rejected
#   Rejected  -> (terminal; the builder submits a NEW completion record)
#   Accepted  -> (terminal)
_COMPLETION_TRANSITIONS = {
    "Draft": {"Submitted"},
    "Submitted": {"Reviewed", "Rejected"},
    "Reviewed": {"Accepted", "Rejected"},
    "Rejected": set(),
    "Accepted": set(),
}


def validate_build_completion(doc, method=None):
    """
    Server-side guard for InductOne Build Completion.

    Why this exists: Mark Reviewed / Reject / Accept were previously
    enforced ONLY in the browser (client scripts). A save via the REST API,
    a data import, the bench console, or any alternate client could move a
    completion into Reviewed / Rejected / Accepted while skipping the
    serial requirement, the rejection-reason requirement, and — most
    importantly — the acceptance side effects (As-Built creation, Instance
    creation, CO close). This makes those rules authoritative on the
    server, for every client, on every save.
    """
    _validate_completion_transition(doc)
    _validate_completion_required_fields(doc)


def _validate_completion_transition(doc):
    """Enforce the forward-only lifecycle and the method-only path to
    'Accepted'."""
    if doc.is_new():
        allowed_initial_statuses = {"Draft", "Submitted"}
        if doc.status and doc.status not in allowed_initial_statuses:
            frappe.throw(_(
                "New Build Completions must start in status 'Draft' or 'Submitted' "
                "(got '{0}')."
            ).format(doc.status))
        return

    old_status = frappe.db.get_value("InductOne Build Completion", doc.name, "status")
    new_status = doc.status

    if old_status == new_status:
        return

    allowed = _COMPLETION_TRANSITIONS.get(old_status, set())
    if new_status not in allowed:
        frappe.throw(_(
            "Invalid Build Completion transition: '{0}' -> '{1}'. "
            "Allowed next states from '{0}': {2}."
        ).format(
            old_status, new_status,
            ", ".join(sorted(allowed)) if allowed else "(none — terminal state)"
        ))

    # 'Accepted' is reachable ONLY through accept_completion_create_as_built,
    # which sets this flag. A direct write to 'Accepted' from any other path
    # is refused so the As-Built / Instance / CO-close side effects can
    # never be bypassed.
    if new_status == "Accepted" and not frappe.flags.get("io_acceptance_in_progress"):
        frappe.throw(_(
            "A Build Completion can only be set to 'Accepted' through the "
            "'Accept Completion' action, which creates the locked As-Built "
            "Record and the InductOne Instance. Setting the status to "
            "'Accepted' directly is not permitted."
        ))


def _validate_completion_required_fields(doc):
    """Enforce gating that was previously browser-only, and stamp the
    reviewer on the server so it is authoritative rather than client-supplied."""
    if doc.status == "Reviewed" and not (doc.serials or []):
        frappe.throw(_(
            "Cannot mark this Build Completion as 'Reviewed': at least one "
            "serial row is required first."
        ))

    if doc.status == "Rejected" and not (getattr(doc, "review_notes", None) or "").strip():
        frappe.throw(_(
            "A rejection reason is required. Record it in Review Notes before "
            "rejecting this Build Completion."
        ))

    if doc.status in ("Reviewed", "Rejected"):
        if hasattr(doc, "reviewed_by") and not doc.reviewed_by:
            doc.reviewed_by = frappe.session.user
        if hasattr(doc, "reviewed_at") and not doc.reviewed_at:
            doc.reviewed_at = now_datetime()
