"""
Server-side logic for InductOne Instance.

The Instance is a custom DocType. On Frappe Cloud, custom DocTypes do not
auto-load filesystem controllers — Frappe ignores any `class Instance(Document)`
subclass in a doctype folder. The pattern that DOES work is:

  1. Register validation functions in hooks.py's doc_events.
  2. Expose whitelisted methods at the module level.

Frappe will dispatch the hooks regardless of how the DocType was created.

This module owns both responsibilities for InductOne Instance.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime


# Valid forward transitions.
#   At Builder      -> Ready for Ship   (builder-intake unit becomes certified built)
#   Ready for Ship  -> Shipped
#   Shipped         -> Installed
# Once Installed, the unit's state lives in Salesforce and is not tracked
# here further. Backwards transitions are blocked.
#
# NOTE: 'At Builder' is a real status option on the Instance.status field
# (used by the at-builder intake path). It MUST appear here, or registering
# this validator would block every At Builder -> Ready for Ship transition.
ALLOWED_TRANSITIONS = {
    "At Builder": {"Ready for Ship"},
    "Ready for Ship": {"Shipped"},
    "Shipped": {"Installed"},
    "Installed": set(),
}

# All valid status values. Any of these is acceptable on creation — a
# backfill unit may arrive already Installed, and an intake unit may be
# created directly as 'At Builder'; we don't force a starting state.
VALID_STATUSES = set(ALLOWED_TRANSITIONS.keys())


def validate_instance(doc, method=None):
    """
    Validation entry point for InductOne Instance.

    Registered in hooks.py under doc_events["InductOne Instance"]["validate"].
    Runs on every save, including create. The `method` argument is the
    Frappe doc_event name (e.g., "validate"); we don't use it.
    """
    _validate_serial_format(doc)
    _validate_status_transition(doc)
    _stamp_status_transition_timestamps(doc)


def _validate_serial_format(doc):
    """Serial must match the IND-#### pattern. The upstream allocator already
    produces this format, but a manual edit path through bench/console or a
    direct API call could violate it. Defense in depth."""
    if not doc.system_serial:
        return
    s = doc.system_serial.strip()
    if not s.startswith("IND-"):
        frappe.throw(_(
            "System Serial must start with 'IND-' (got '{0}'). "
            "Serials are allocated by InductOne Builder Tranche."
        ).format(s))
    suffix = s[4:]
    if not suffix.isdigit():
        frappe.throw(_(
            "System Serial suffix must be all digits (got '{0}'). "
            "Expected format: IND-####"
        ).format(s))


def _validate_status_transition(doc):
    """Forward-only state machine. Blocks regressions and skipped states.

    On creation (doc.is_new()), any valid status is permitted. This allows
    backfill units to be created directly as 'Installed', and intake units
    to be created as 'At Builder', without walking the full lifecycle. The
    constraint being enforced here is 'don't create garbage states', not
    'always start at Ready for Ship'.

    On update, the new status must be in ALLOWED_TRANSITIONS[old_status].
    """
    if doc.is_new():
        if doc.status and doc.status not in VALID_STATUSES:
            frappe.throw(_(
                "'{0}' is not a valid Instance status. "
                "Valid values: {1}."
            ).format(doc.status, ", ".join(sorted(VALID_STATUSES))))
        return

    old_status = frappe.db.get_value(doc.doctype, doc.name, "status")
    new_status = doc.status

    if old_status == new_status:
        return

    allowed = ALLOWED_TRANSITIONS.get(old_status, set())
    if new_status not in allowed:
        frappe.throw(_(
            "Invalid status transition: '{0}' -> '{1}'. "
            "Allowed next states from '{0}': {2}."
        ).format(
            old_status, new_status,
            ", ".join(sorted(allowed)) if allowed else "(none — terminal state for Plus One tracking)"
        ))


def _stamp_status_transition_timestamps(doc):
    """Auto-stamp shipped_at and installed_at on the transitions they
    correspond to, if the user didn't supply them."""
    if doc.is_new():
        return

    old_status = frappe.db.get_value(doc.doctype, doc.name, "status")
    new_status = doc.status

    if old_status == new_status:
        return

    now = now_datetime()

    if new_status == "Shipped" and not doc.shipped_at:
        doc.shipped_at = now
    if new_status == "Installed" and not doc.installed_at:
        doc.installed_at = now


@frappe.whitelist()
def get_instance_for_as_built(as_built_name):
    """Lookup helper for the As-Built Record client script: returns the
    Instance name (if any) for a given As-Built. Used to render a 'View
    Instance' button on the As-Built form.

    Whitelisted module-level functions execute regardless of whether the
    DocType is custom; they're called by dotted path from the client.
    """
    if not as_built_name:
        return None
    name = frappe.db.get_value(
        "InductOne Instance",
        {"as_built_record": as_built_name},
        "name",
    )
    return name