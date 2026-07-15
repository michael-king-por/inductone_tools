"""Role-aware in-app guidance for InductOne workflows.

This module is intentionally read-only. It provides small, permission-aware
payloads that Desk client scripts and Workspace blocks can render without
duplicating workflow language in every surface.
"""

from __future__ import annotations

import frappe
from frappe import _


BRAND = {
    "blue": "#1794CE",
    "grey_900": "#101828",
    "grey_700": "#344054",
    "grey_600": "#475467",
    "grey_500": "#667085",
    "border": "#EAECF0",
    "surface": "#F9FAFB",
    "font_family": "Arial, sans-serif",
}

CANONICAL_TERMS = [
    "Build",
    "Build Completion",
    "Configuration Order",
    "release package",
    "builder serial workbook",
    "document index",
    "Engineering Signoff",
    "Configuration Option",
    "As-Built Record",
    "InductOne Instance",
]

TOUCHED_DOCTYPES = {
    "InductOne Configuration Order",
    "InductOne Build Completion",
    "InductOne Build",
    "Engineering Signoff",
    "InductOne Configuration Option",
}

GUIDANCE_WORKSPACES = [
    "Builder Portal",
    "Operations",
    "Engineering",
]

GUIDANCE_CUSTOM_HTML_BLOCKS = [
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
]


def after_migrate():
    """Cache-bust repo-managed guidance surfaces after fixture import.

    Frappe Desk can retain Workspace and Custom HTML Block content aggressively.
    Fixture import preserves the ``modified`` value from fixture JSON, so a
    deploy can update block content without changing the timestamp Desk uses to
    decide whether a cached Workspace is stale. This hook runs after fixtures
    import and touches only app-owned guidance records.
    """

    for workspace in GUIDANCE_WORKSPACES:
        if frappe.db.exists("Workspace", workspace):
            frappe.db.set_value("Workspace", workspace, "modified_by", "Administrator", update_modified=False)
            frappe.db.set_value("Workspace", workspace, "modified", frappe.utils.now(), update_modified=False)

    for block in GUIDANCE_CUSTOM_HTML_BLOCKS:
        if frappe.db.exists("Custom HTML Block", block):
            frappe.db.set_value("Custom HTML Block", block, "modified_by", "Administrator", update_modified=False)
            frappe.db.set_value("Custom HTML Block", block, "modified", frappe.utils.now(), update_modified=False)

    if frappe.db.exists("DocType", "InductOne Field Change Request"):
        from inductone_tools.field_change import refresh_display_labels

        refresh_display_labels()

    frappe.clear_cache()


def _roles() -> set[str]:
    return set(frappe.get_roles(frappe.session.user))


def _has(role: str) -> bool:
    return role in _roles()


def _has_any(roles: set[str]) -> bool:
    return bool(_roles() & roles)


def _doc_url(doctype: str, name: str | None) -> str | None:
    if not name:
        return None
    return f"/app/{frappe.scrub(doctype).replace('_', '-')}/{name}"


@frappe.whitelist()
def get_brand_tokens():
    """Return reusable POR brand tokens for client-side rendering."""

    return {
        "brand": BRAND,
        "canonical_terms": CANONICAL_TERMS,
    }


@frappe.whitelist()
def get_builder_portal_guidance():
    """Return the builder landing-page task model for the current user.

    The queries use ``frappe.get_list`` so normal DocPerm and query-condition
    restrictions remain active. External builders only see records scoped to
    their supplier user permissions.
    """

    if not _has("InductOne External Builder"):
        frappe.throw(
            _("Builder Portal guidance requires the InductOne External Builder role."),
            frappe.PermissionError,
        )

    configuration_orders = frappe.get_list(
        "InductOne Configuration Order",
        fields=[
            "name",
            "co_status",
            "inductone_build",
            "builder_supplier",
            "system_serial",
            "modified",
        ],
        filters={"co_status": ["in", ["Released", "Awaiting Completion", "Closed", "Completed"]]},
        order_by="modified desc",
        limit_page_length=20,
    )

    completions = frappe.get_list(
        "InductOne Build Completion",
        fields=[
            "name",
            "status",
            "inductone_build",
            "configuration_order",
            "builder_supplier",
            "modified",
        ],
        filters={"status": ["in", ["Draft", "Submitted", "Reviewed", "Rejected"]]},
        order_by="modified desc",
        limit_page_length=20,
    )

    tasks = []
    for co in configuration_orders:
        status = co.get("co_status")
        if status == "Released":
            tasks.append(
                {
                    "priority": 10,
                    "type": "configuration_order",
                    "title": "Acknowledge the released Build",
                    "detail": (
                        "Open the Configuration Order, review the document index, "
                        "download the release package, and confirm receipt."
                    ),
                    "record": co.get("name"),
                    "doctype": "InductOne Configuration Order",
                    "status": status,
                    "url": _doc_url("InductOne Configuration Order", co.get("name")),
                }
            )
        elif status == "Awaiting Completion":
            tasks.append(
                {
                    "priority": 20,
                    "type": "completion_upload",
                    "title": "Complete the build package and return the workbook",
                    "detail": (
                        "Use the builder serial workbook from the document index. "
                        "When the unit is complete, upload the filled workbook as a Build Completion."
                    ),
                    "record": co.get("name"),
                    "doctype": "InductOne Configuration Order",
                    "status": status,
                    "url": _doc_url("InductOne Configuration Order", co.get("name")),
                }
            )
        elif status in {"Closed", "Completed"}:
            tasks.append(
                {
                    "priority": 50,
                    "type": "completed_reference",
                    "title": "Completed Build available for reference",
                    "detail": (
                        "This Configuration Order remains available as handoff history. "
                        "No action is needed unless Plus One contacts you."
                    ),
                    "record": co.get("name"),
                    "doctype": "InductOne Configuration Order",
                    "status": status,
                    "url": _doc_url("InductOne Configuration Order", co.get("name")),
                }
            )

    for completion in completions:
        status = completion.get("status")
        if status == "Rejected":
            tasks.append(
                {
                    "priority": 5,
                    "type": "rejected_completion",
                    "title": "Fix a rejected Build Completion",
                    "detail": (
                        "Open the rejected Build Completion, read the review notes, "
                        "then upload a corrected workbook through the assigned Build workflow."
                    ),
                    "record": completion.get("name"),
                    "doctype": "InductOne Build Completion",
                    "status": status,
                    "url": _doc_url("InductOne Build Completion", completion.get("name")),
                }
            )
        elif status in {"Submitted", "Reviewed"}:
            tasks.append(
                {
                    "priority": 40,
                    "type": "waiting_review",
                    "title": "Waiting on Plus One review",
                    "detail": "Your Build Completion has been submitted. No action is needed unless it is rejected.",
                    "record": completion.get("name"),
                    "doctype": "InductOne Build Completion",
                    "status": status,
                    "url": _doc_url("InductOne Build Completion", completion.get("name")),
                }
            )

    tasks.sort(key=lambda row: (row["priority"], row["record"] or ""))

    return {
        "audience": "builder",
        "empty_state": not tasks,
        "tasks": tasks[:10],
        "counts": {
            "configuration_orders": len(configuration_orders),
            "open_completions": len(completions),
            "actionable_tasks": len([t for t in tasks if t["priority"] < 40]),
        },
        "sections": [
            {
                "title": "Download your build package",
                "body": "Open the Configuration Order and use the document index. It contains the release package, manifest, hierarchy workbook, balloon callout report, and builder serial workbook.",
            },
            {
                "title": "Upload completion workbook",
                "body": "Return the filled builder serial workbook through the Build Completion upload flow. Leave notes if any serials or labels need review.",
            },
            {
                "title": "If a build is rejected",
                "body": "Read the Review Notes, correct the workbook, and upload a new completion. The previous rejected record stays as audit history.",
            },
        ],
    }


@frappe.whitelist()
def get_form_guidance(doctype: str, docname: str | None = None, doc: str | None = None):
    """Return status, next action, and checklist guidance for a touched form."""

    if doctype not in TOUCHED_DOCTYPES:
        frappe.throw(_("No InductOne guidance is registered for {0}.").format(doctype))

    document = None
    if docname:
        document = frappe.get_doc(doctype, docname)
        document.check_permission("read")
    elif doc:
        document = frappe.parse_json(doc)

    if doctype == "InductOne Configuration Order":
        return _configuration_order_guidance(document)
    if doctype == "InductOne Build Completion":
        return _build_completion_guidance(document)
    if doctype == "InductOne Build":
        return _build_guidance(document)
    if doctype == "Engineering Signoff":
        return _engineering_signoff_guidance(document)
    if doctype == "InductOne Configuration Option":
        return _configuration_option_guidance(document)

    frappe.throw(_("Unhandled guidance doctype {0}.").format(doctype))


def _status(document, fieldname: str, default: str = "Draft") -> str:
    if not document:
        return default
    if isinstance(document, dict):
        return document.get(fieldname) or default
    return getattr(document, fieldname, None) or default


def _base_payload(audience: str, title: str, status: str, next_action: str, checklist: list[dict]):
    return {
        "brand": BRAND,
        "audience": audience,
        "title": title,
        "status": status,
        "next_action": next_action,
        "checklist": checklist,
        "canonical_terms": CANONICAL_TERMS,
    }


def _configuration_order_guidance(document):
    status = _status(document, "co_status")
    builder = _has("InductOne External Builder")
    audience = "builder" if builder else "operations"

    if status == "Released":
        next_action = (
            "Builder: review the document index, download the release package, and acknowledge receipt."
            if builder
            else "Operations: wait for builder acknowledgement or record received acknowledgement evidence."
        )
    elif status == "Awaiting Completion":
        next_action = (
            "Builder: complete the unit and upload the filled builder serial workbook."
            if builder
            else "Operations: wait for the returned Build Completion workbook."
        )
    elif status == "Closed":
        next_action = "This Configuration Order is closed. Use it as audit history."
    else:
        next_action = "Operations owns this record until it is released to the assigned builder."

    checklist = [
        {"label": "Document index available", "done": bool(getattr(document, "documents", None) if document else True)},
        {"label": "Release package reviewed", "done": status in {"Released", "Awaiting Completion", "Closed"}},
        {"label": "Builder serial workbook included", "done": status in {"Released", "Awaiting Completion", "Closed"}},
    ]
    return _base_payload(audience, "Configuration Order guidance", status, next_action, checklist)


def _build_completion_guidance(document):
    status = _status(document, "status")
    builder = _has("InductOne External Builder")
    audience = "builder" if builder else "operations"

    actions = {
        "Draft": "Attach the completed builder serial workbook and submit the Build Completion.",
        "Submitted": "Plus One is reviewing the submitted workbook. No builder action is needed right now.",
        "Reviewed": "Review is complete. Plus One can accept the completion and create the As-Built Record.",
        "Accepted": "Accepted. This record is locked as accepted build evidence.",
        "Rejected": "Read Review Notes, correct the workbook, and upload a new Build Completion.",
    }
    checklist = [
        {"label": "Configuration Order linked", "done": bool(getattr(document, "configuration_order", None) if document else True)},
        {"label": "Workbook serial rows present", "done": bool(getattr(document, "serials", None) if document else status in {"Draft"})},
        {"label": "Review notes checked if rejected", "done": status != "Rejected" or bool(getattr(document, "review_notes", None))},
    ]
    return _base_payload(audience, "Build Completion guidance", status, actions.get(status, "Review the current status."), checklist)


def _build_guidance(document):
    status = _status(document, "build_status", "DRAFT")
    completion = _status(document, "completion_status", "Open")
    next_action = "Load released Configuration Options, generate a snapshot, create the Configuration Order, allocate serial, prepare handoff, then release."
    if status == "RELEASED_TO_BUILDER":
        next_action = "Monitor acknowledgement and completion upload from the assigned builder."
    elif completion == "Submitted":
        next_action = "Open the Build Completion, review the returned workbook, and accept or reject it."
    elif status == "COMPLETED":
        next_action = "Completed. Use the As-Built Record and Instance for audit and support."
    checklist = [
        {"label": "Released Configuration Options selected", "done": bool(getattr(document, "selections", None) if document else True)},
        {"label": "Configured snapshot exists", "done": bool(getattr(document, "selected_snapshot", None) or getattr(document, "latest_snapshot", None) if document else True)},
        {"label": "Configuration Order exists", "done": bool(getattr(document, "latest_config_order", None) if document else True)},
        {"label": "IND serial allocated", "done": bool(getattr(document, "system_serial", None) if document else True)},
    ]
    return _base_payload("operations", "Build workflow guidance", f"{status} / {completion}", next_action, checklist)


def _engineering_signoff_guidance(document):
    status = _status(document, "status", "Pending")
    next_action = {
        "Pending": "Engineering User reviews the target document and approves or rejects the signoff.",
        "Approved": "Approved. If this targets a Configuration Option, the signoff gate releases the option for build use.",
        "Rejected": "Rejected. Correct the target document or option, then create a new signoff when ready.",
        "Superseded": "Superseded. Use the current signoff record instead.",
    }.get(status, "Review the signoff state.")
    checklist = [
        {"label": "Target document linked", "done": bool(getattr(document, "target_docname", None) if document else True)},
        {"label": "Current signoff", "done": bool(getattr(document, "is_current", 1) if document else True)},
        {"label": "Decision captured", "done": status in {"Approved", "Rejected", "Superseded"}},
    ]
    return _base_payload("engineering", "Engineering Signoff guidance", status, next_action, checklist)


def _configuration_option_guidance(document):
    status = _status(document, "status", "Draft")
    next_action = {
        "Draft": "Draft options are for ideation only. They are not build-usable until approved by Engineering Signoff.",
        "Released": "Released options can be loaded into Builds and selected for snapshots.",
        "Deprecated": "Deprecated options remain for audit history and should not be selected for new Builds.",
    }.get(status, "Review the option status.")
    checklist = [
        {"label": "Option group assigned", "done": bool(getattr(document, "option_group", None) if document else True)},
        {"label": "Builder description written", "done": bool(getattr(document, "builder_description", None) if document else True)},
        {"label": "Mapping complete", "done": (getattr(document, "mapping_status", None) == "Complete") if document else True},
    ]
    return _base_payload("engineering", "Configuration Option guidance", status, next_action, checklist)
