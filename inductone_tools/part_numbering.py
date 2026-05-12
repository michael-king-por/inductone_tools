import re

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, nowdate


CONTROLLED_FAMILY_PREFIX = {
    "Part": "1",
    "Assembly": "2",
    "Software": "3",
    "Service": "4",
}

VALID_FAMILIES = set(CONTROLLED_FAMILY_PREFIX.keys()) | {"Custom"}

VALID_ASSIGNMENT_STATUSES = {
    "Reserved",
    "In Development",
    "Released",
    "Cancelled",
    "Superseded",
}

VALID_REQUEST_STATUSES = {
    "Draft",
    "Allocated",
    "Cancelled",
}

CONTROLLED_NUMBER_RE = re.compile(r"^[1-4][0-9]+$")


def _has_part_number_manager_role() -> bool:
    roles = set(frappe.get_roles(frappe.session.user))
    return bool({"System Manager", "Part Number Manager"} & roles)


def _require_part_number_manager():
    if not _has_part_number_manager_role():
        frappe.throw(
            _("Only users with Part Number Manager or System Manager role may allocate part numbers."),
            frappe.PermissionError,
        )


def _get_db_lock(lock_name: str, timeout_seconds: int = 10):
    """
    Uses MariaDB named locks, which are appropriate for a small but real allocation
    critical section. If this ever runs on a database that does not support GET_LOCK,
    the unique part_number constraint still remains the final protection.
    """
    try:
        result = frappe.db.sql(
            "SELECT GET_LOCK(%s, %s)",
            (lock_name, timeout_seconds),
        )
        if not result or result[0][0] != 1:
            frappe.throw(_("Could not acquire allocation lock. Try again."))
    except Exception as exc:
        # Do not silently continue on lock failure. The allocator should be
        # deliberately conservative.
        frappe.throw(_("Could not acquire allocation lock: {0}").format(str(exc)))


def _release_db_lock(lock_name: str):
    try:
        frappe.db.sql("SELECT RELEASE_LOCK(%s)", (lock_name,))
    except Exception:
        # Do not mask the actual allocation result with an unlock issue.
        pass


def _extract_sequence(part_number: str):
    """
    Controlled tranche numbers are:
        1000476
        2000477
        3000478
        4000479

    First digit is family.
    Remaining digits are the shared global sequence.
    """
    if not part_number:
        return None

    value = str(part_number).strip()

    if not CONTROLLED_NUMBER_RE.match(value):
        return None

    try:
        return int(value[1:])
    except Exception:
        return None


def _get_current_max_sequence() -> int:
    """
    Finds the highest shared sequence suffix across all controlled numbers.

    Example:
        1000472 -> 472
        2000475 -> 475

    Current max = 475
    Next sequence = 476
    """
    rows = frappe.get_all(
        "Part Number Assignment",
        fields=["part_number"],
        limit_page_length=0,
    )

    max_sequence = 0

    for row in rows:
        sequence = _extract_sequence(row.part_number)
        if sequence is not None and sequence > max_sequence:
            max_sequence = sequence

    return max_sequence


def _make_part_number(number_family: str, sequence: int) -> str:
    if number_family not in CONTROLLED_FAMILY_PREFIX:
        frappe.throw(_("Cannot auto-allocate numbers for family: {0}").format(number_family))

    prefix = CONTROLLED_FAMILY_PREFIX[number_family]
    return f"{prefix}{sequence:06d}"


def _validate_request_lines(doc):
    if not doc.get("requested_numbers"):
        frappe.throw(_("Requested Numbers table must have at least one row."))

    total = 0

    for row in doc.get("requested_numbers"):
        family = row.get("number_family")
        qty = cint(row.get("quantity_requested"))

        if family not in VALID_FAMILIES:
            frappe.throw(_("Invalid number family on row {0}: {1}").format(row.idx, family))

        if family == "Custom":
            frappe.throw(
                _(
                    "Custom numbers cannot be batch auto-allocated. "
                    "Create Custom Part Number Assignment records manually with justification."
                )
            )

        if qty <= 0:
            frappe.throw(_("Quantity Requested must be greater than zero on row {0}.").format(row.idx))

        total += qty

    return total


def validate_allocation_request(doc, method=None):
    """
    Hooked on Part Number Allocation Request.validate.
    Keeps the request sane before allocation.
    """
    if doc.status not in VALID_REQUEST_STATUSES:
        frappe.throw(_("Invalid allocation request status: {0}").format(doc.status))

    if doc.status == "Draft":
        total = _validate_request_lines(doc)
        doc.total_numbers_requested = total

    if doc.status == "Allocated":
        if not doc.get("allocation_results"):
            frappe.throw(_("Allocated requests must have allocation results."))

        doc.total_numbers_allocated = len(doc.get("allocation_results"))

    old_doc = doc.get_doc_before_save()

    if old_doc and old_doc.status == "Allocated":
        if not getattr(frappe.flags, "part_number_allocation_update", False):
            if not _has_part_number_manager_role():
                frappe.throw(_("Allocated part number requests cannot be edited."))


def validate_part_number_assignment(doc, method=None):
    """
    Hooked on Part Number Assignment.validate.
    Enforces the core ledger rules.
    """
    if not doc.part_number:
        frappe.throw(_("Part Number is required."))

    doc.part_number = str(doc.part_number).strip()

    if not doc.number_family:
        frappe.throw(_("Number Family is required."))

    if doc.number_family not in VALID_FAMILIES:
        frappe.throw(_("Invalid number family: {0}").format(doc.number_family))

    if doc.status not in VALID_ASSIGNMENT_STATUSES:
        frappe.throw(_("Invalid assignment status: {0}").format(doc.status))

    if doc.number_family in CONTROLLED_FAMILY_PREFIX:
        expected_prefix = CONTROLLED_FAMILY_PREFIX[doc.number_family]

        if not CONTROLLED_NUMBER_RE.match(doc.part_number):
            frappe.throw(
                _(
                    "{0} numbers must be controlled numeric tranche numbers beginning with {1}."
                ).format(doc.number_family, expected_prefix)
            )

        if not doc.part_number.startswith(expected_prefix):
            frappe.throw(
                _(
                    "{0} number {1} must begin with prefix {2}."
                ).format(doc.number_family, doc.part_number, expected_prefix)
            )

    if doc.number_family == "Custom":
        if not doc.is_custom_number:
            doc.is_custom_number = 1

        if not doc.custom_number_justification:
            frappe.throw(_("Custom numbers require Custom Number Justification."))

    if doc.status == "Released":
        if not doc.gitlab_ec_url:
            frappe.throw(_("Released part number assignments require a GitLab EC URL."))

        if doc.number_family in {"Part", "Assembly"}:
            if not doc.released_item:
                frappe.throw(_("{0} assignments require Released Item before status can be Released.").format(doc.number_family))

    old_doc = doc.get_doc_before_save()

    if old_doc and old_doc.status == "Released":
        if not getattr(frappe.flags, "part_number_allocation_update", False):
            if not getattr(doc, "allow_admin_override", False):
                frappe.throw(
                    _(
                        "Released Part Number Assignments are locked. "
                        "Use an admin override only for controlled correction."
                    )
                )


@frappe.whitelist()
def allocate_numbers(allocation_request: str):
    """
    Allocates controlled numbers from a Part Number Allocation Request.

    Sequence behavior:
        last assigned: 2000475

        request:
            Part x2
            Assembly x1
            Software x1

        result:
            1000476
            1000477
            2000478
            3000479
    """
    _require_part_number_manager()

    if not allocation_request:
        frappe.throw(_("Allocation Request is required."))

    request_doc = frappe.get_doc("Part Number Allocation Request", allocation_request)

    if request_doc.status != "Draft":
        frappe.throw(_("Only Draft allocation requests can be allocated."))

    total_requested = _validate_request_lines(request_doc)

    lock_name = "part_number_allocation_global_sequence"

    created = []

    _get_db_lock(lock_name)

    try:
        current_sequence = _get_current_max_sequence()
        next_sequence = current_sequence + 1

        request_doc.set("allocation_results", [])

        for line in request_doc.get("requested_numbers"):
            family = line.number_family
            qty = cint(line.quantity_requested)

            for _i in range(qty):
                part_number = _make_part_number(family, next_sequence)

                description = line.description_hint or request_doc.request_reason or ""

                assignment = frappe.get_doc(
                    {
                        "doctype": "Part Number Assignment",
                        "part_number": part_number,
                        "number_family": family,
                        "status": "Reserved",
                        "reserved_by": request_doc.requested_by or frappe.session.user,
                        "reserved_for": request_doc.reserved_for,
                        "date_reserved": request_doc.date_requested or nowdate(),
                        "description_requested": description,
                        "request_notes": request_doc.request_reason,
                        "gitlab_ec_url": request_doc.gitlab_ec_url,
                        "gitlab_reference": request_doc.gitlab_reference,
                        "allocation_batch_id": request_doc.name,
                    }
                )

                assignment.insert()

                request_doc.append(
                    "allocation_results",
                    {
                        "number_family": family,
                        "part_number": part_number,
                        "part_number_assignment": assignment.name,
                        "description_requested": description,
                        "status": "Reserved",
                    },
                )

                created.append(
                    {
                        "number_family": family,
                        "part_number": part_number,
                        "assignment": assignment.name,
                    }
                )

                next_sequence += 1

        request_doc.status = "Allocated"
        request_doc.allocated_on = now_datetime()
        request_doc.allocated_by = frappe.session.user
        request_doc.total_numbers_requested = total_requested
        request_doc.total_numbers_allocated = len(created)
        request_doc.allocation_batch_id = request_doc.name

        frappe.flags.part_number_allocation_update = True
        request_doc.save()
        frappe.flags.part_number_allocation_update = False

    except Exception:
        frappe.flags.part_number_allocation_update = False
        raise

    finally:
        _release_db_lock(lock_name)

    frappe.db.commit()

    return {
        "allocation_request": request_doc.name,
        "total_allocated": len(created),
        "created": created,
    }