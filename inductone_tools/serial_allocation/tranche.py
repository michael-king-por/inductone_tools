"""
Server-side logic for InductOne Builder Tranche, plus the serial allocator.

InductOne Builder Tranche is a custom DocType. On Frappe Cloud, custom
DocTypes do not auto-load filesystem controllers. Validation is wired via
hooks.py doc_events. Whitelisted methods are exposed at the module level.

This module owns:
  - validate_tranche: doc_events validate hook for InductOne Builder Tranche
  - allocate_next_serial: the atomic serial-allocation primitive (module-level
      function called by serial_allocation/release.py)
  - preview_next_serial: whitelisted read-only preview for client scripts
  - format_serial: helper for producing the IND-#### string from an integer
"""

import frappe
from frappe import _
from frappe.utils import now_datetime


# ============================================================
#  Validation — registered via hooks.py doc_events
# ============================================================

def validate_tranche(doc, method=None):
    """
    Validation entry point for InductOne Builder Tranche.

    Registered in hooks.py under
    doc_events["InductOne Builder Tranche"]["validate"].

    Enforces:
      - tranche_end >= tranche_start
      - next_serial in [tranche_start, tranche_end + 1]
      - no overlap with any other tranche, active or retired
    """
    _validate_range_sanity(doc)
    _validate_next_serial_within_range(doc)
    _validate_no_overlap_with_other_tranches(doc)


def _validate_range_sanity(doc):
    if doc.tranche_start is None or doc.tranche_end is None:
        return
    if doc.tranche_end < doc.tranche_start:
        frappe.throw(_(
            "Tranche End ({0}) cannot be less than Tranche Start ({1})."
        ).format(doc.tranche_end, doc.tranche_start))


def _validate_next_serial_within_range(doc):
    if doc.next_serial is None or doc.tranche_start is None or doc.tranche_end is None:
        return
    # next_serial == tranche_end + 1 means the tranche is exhausted; that's
    # legitimate state, not an error. Anything below start or above end+1 is wrong.
    if doc.next_serial < doc.tranche_start:
        frappe.throw(_(
            "Next Serial ({0}) is below Tranche Start ({1})."
        ).format(doc.next_serial, doc.tranche_start))
    if doc.next_serial > doc.tranche_end + 1:
        frappe.throw(_(
            "Next Serial ({0}) is above Tranche End + 1 ({1})."
        ).format(doc.next_serial, doc.tranche_end + 1))


def _validate_no_overlap_with_other_tranches(doc):
    if doc.tranche_start is None or doc.tranche_end is None:
        return

    # Find any other tranche whose range intersects this one. Retired tranches
    # still count for overlap purposes — we never want two tranches that
    # could ever have produced the same serial number, even historically.
    overlapping = frappe.db.sql(
        """
        SELECT name, tranche_start, tranche_end, builder_supplier, status
        FROM `tabInductOne Builder Tranche`
        WHERE name != %(self_name)s
          AND tranche_start <= %(end)s
          AND tranche_end >= %(start)s
        """,
        {
            "self_name": doc.name or "",
            "start": doc.tranche_start,
            "end": doc.tranche_end,
        },
        as_dict=True,
    )

    if overlapping:
        other = overlapping[0]
        frappe.throw(_(
            "Tranche range [{0}, {1}] overlaps with existing tranche {2} "
            "(range [{3}, {4}], builder {5}, status {6}). "
            "Serial ranges must be globally unique across all tranches, "
            "active or retired."
        ).format(
            doc.tranche_start, doc.tranche_end,
            other["name"], other["tranche_start"], other["tranche_end"],
            other["builder_supplier"], other["status"],
        ))


# ============================================================
#  Allocation primitives
# ============================================================

def format_serial(integer_value, prefix="IND"):
    """Format an integer as the stenciled serial, e.g. 2042 -> 'IND-2042'."""
    prefix = (prefix or "IND").strip()
    return "{0}-{1}".format(prefix, integer_value)


def is_exhausted(tranche_doc):
    """True if the tranche has allocated its last serial."""
    if tranche_doc.next_serial is None or tranche_doc.tranche_end is None:
        return False
    return tranche_doc.next_serial > tranche_doc.tranche_end


def allocate_next_serial(builder_supplier, user=None):
    """
    Atomically allocate the next serial number for a given builder.

    Locks the active tranche row for update, increments next_serial, records
    the allocation, and returns the formatted serial string (e.g. "IND-2042").

    Raises if:
      - the builder has no active tranche
      - the active tranche is exhausted (and no other active tranche exists)

    This function MUST be called inside a transaction that will be committed
    by the caller. Do not call frappe.db.commit() here; it would prematurely
    end a larger atomic operation.
    """
    if not builder_supplier:
        frappe.throw(_("builder_supplier is required to allocate a serial."))

    user = user or frappe.session.user

    # Find active tranches for this builder, with row-level lock.
    # Ordering by tranche_start ensures deterministic selection if a builder
    # ever has more than one active tranche (e.g., a top-up range).
    rows = frappe.db.sql(
        """
        SELECT name
        FROM `tabInductOne Builder Tranche`
        WHERE builder_supplier = %(supplier)s
          AND status = 'Active'
        ORDER BY tranche_start ASC
        FOR UPDATE
        """,
        {"supplier": builder_supplier},
        as_dict=True,
    )

    if not rows:
        frappe.throw(_(
            "Builder {0} has no active InductOne Builder Tranche. "
            "Create one before releasing a build to this builder."
        ).format(builder_supplier))

    # Walk active tranches in order; use the first non-exhausted one.
    chosen_tranche = None
    exhausted_names = []
    for row in rows:
        tranche = frappe.get_doc("InductOne Builder Tranche", row["name"])
        if is_exhausted(tranche):
            exhausted_names.append(tranche.name)
            continue
        chosen_tranche = tranche
        break

    if chosen_tranche is None:
        frappe.throw(_(
            "Builder {0} has no available serial numbers — all active tranches "
            "are exhausted ({1}). Create a new tranche or extend the existing one."
        ).format(builder_supplier, ", ".join(exhausted_names) or "none"))

    allocated_int = chosen_tranche.next_serial
    formatted = format_serial(allocated_int, chosen_tranche.serial_prefix)

    # Increment and stamp audit fields
    chosen_tranche.next_serial = allocated_int + 1
    chosen_tranche.allocation_count = (chosen_tranche.allocation_count or 0) + 1
    chosen_tranche.last_allocated_at = now_datetime()
    chosen_tranche.last_allocated_by = user
    chosen_tranche.save(ignore_permissions=True)

    return {
        "serial": formatted,
        "serial_int": allocated_int,
        "tranche_name": chosen_tranche.name,
    }


@frappe.whitelist()
def preview_next_serial(builder_supplier):
    """
    Read-only preview of what serial would be allocated for this builder.
    Does not mutate state. Safe to call from client scripts.

    Whitelisted so the Build form's confirmation dialog can show the user
    the serial they're about to commit to.
    """
    if not builder_supplier:
        return {"ok": False, "error": "builder_supplier required"}

    tranches = frappe.get_all(
        "InductOne Builder Tranche",
        filters={"builder_supplier": builder_supplier, "status": "Active"},
        fields=["name", "tranche_start", "tranche_end", "next_serial", "serial_prefix"],
        order_by="tranche_start asc",
    )

    if not tranches:
        return {"ok": False, "error": "no active tranche for builder"}

    for t in tranches:
        if t["next_serial"] <= t["tranche_end"]:
            return {
                "ok": True,
                "serial": format_serial(t["next_serial"], t["serial_prefix"]),
                "tranche_name": t["name"],
            }

    return {"ok": False, "error": "all active tranches for this builder are exhausted"}
