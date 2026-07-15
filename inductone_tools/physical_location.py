"""Server-side validation for POR Physical Location records.

This replaces the former Desk Server Script named ``POR Physical Locations``.
Keeping this logic in the app makes the location hierarchy deployable,
reviewable, and repeatable across candidate restores and production deploys.
"""

from __future__ import annotations

import frappe
from frappe import _


AUTO_SET_ROBOT_LOCATION_CODE = True

NAMING_SERIES_BY_TYPE = {
    "Customer": "POR-CUST.####",
    "Site": "POR-SITE.####",
    "Lane": "POR-LANE.####",
    "Cell": "POR-CELL.####",
    "Robot": "POR-ROBOT.####",
}

PARENT_TYPE_BY_TYPE = {
    "Customer": None,
    "Site": "Customer",
    "Lane": "Site",
    "Cell": "Lane",
    "Robot": "Cell",
}


def _has_field(doc, fieldname: str) -> bool:
    return fieldname in doc.as_dict()


def _strip(value) -> str:
    return (value or "").strip()


def _throw(message: str) -> None:
    frappe.throw(_(message))


def _get_parent(doc):
    parent_name = doc.get("parent_por_physical_location")
    if not parent_name:
        return None
    return frappe.get_doc("POR Physical Location", parent_name)


def _get_ancestor(start_doc, target_type: str):
    cur = start_doc
    while cur:
        if cur.location_type == target_type:
            return cur
        parent_name = cur.get("parent_por_physical_location")
        cur = frappe.get_doc("POR Physical Location", parent_name) if parent_name else None
    return None


def _set_if_present(doc, fieldname: str, value) -> None:
    if _has_field(doc, fieldname):
        doc.set(fieldname, value)


def validate_por_physical_location(doc, method=None) -> None:
    """Validate hierarchy, naming helpers, and denormalized full path.

    Rules:
    - Customer has no parent.
    - Site parent must be Customer.
    - Lane parent must be Site.
    - Cell parent must be Lane.
    - Robot parent must be Cell.
    - Child customer must match parent customer when both are populated.
    - Robot numbers are unique within a cell.
    - ``full_path`` is regenerated from ancestor location codes.
    """

    location_type = _strip(doc.get("location_type"))

    if _has_field(doc, "naming_series") and location_type in NAMING_SERIES_BY_TYPE:
        doc.naming_series = NAMING_SERIES_BY_TYPE[location_type]

    if location_type not in PARENT_TYPE_BY_TYPE:
        _throw("Location Type must be Customer, Site, Lane, Cell, or Robot.")

    parent = _get_parent(doc)
    expected_parent_type = PARENT_TYPE_BY_TYPE[location_type]

    if expected_parent_type is None:
        if parent:
            _throw(f"A {location_type} cannot have a parent.")
    else:
        if not parent:
            _throw(f"A {location_type} must have a parent {expected_parent_type}.")
        if parent.location_type != expected_parent_type:
            _throw(f"A {location_type} must be under a {expected_parent_type}.")

        if parent.get("customer") and not doc.get("customer"):
            doc.customer = parent.customer
        if doc.get("customer") and parent.get("customer") and doc.customer != parent.customer:
            _throw("Child location customer must match parent customer.")

    if location_type == "Customer" and _has_field(doc, "customer") and not doc.get("customer"):
        doc.customer = _strip(doc.get("location_name")) or _strip(doc.get("location_code"))

    _set_if_present(doc, "is_group", 1 if location_type in {"Customer", "Site", "Lane"} else 0)

    location_code = _strip(doc.get("location_code"))
    if not location_code:
        _throw("Location Code is required.")
    doc.location_code = location_code

    if location_type == "Customer":
        pass
    elif location_type == "Site":
        _set_if_present(doc, "site_code", location_code)
    elif location_type == "Lane":
        _set_if_present(doc, "lane_code", location_code)
    elif location_type == "Cell":
        _set_if_present(doc, "cell_code", location_code)
    elif location_type == "Robot":
        _set_if_present(doc, "robot_code", location_code)

        if _has_field(doc, "robot_number"):
            if doc.robot_number in (None, ""):
                _throw("Robot Number is required for Robot locations.")

            try:
                robot_number = int(doc.robot_number)
            except Exception:
                _throw("Robot Number must be an integer.")

            if robot_number < 1 or robot_number > 50:
                _throw("Robot Number must be between 1 and 50.")

            duplicate = frappe.db.exists(
                "POR Physical Location",
                {
                    "parent_por_physical_location": doc.parent_por_physical_location,
                    "location_type": "Robot",
                    "robot_number": robot_number,
                    "name": ["!=", doc.name or ""],
                },
            )
            if duplicate:
                _throw(
                    f"Robot Number {robot_number} already exists under this Cell ({duplicate})."
                )

            if AUTO_SET_ROBOT_LOCATION_CODE:
                doc.location_code = f"R{robot_number}"
                _set_if_present(doc, "robot_code", doc.location_code)

    if _has_field(doc, "full_path"):
        parts = []
        customer = _get_ancestor(doc, "Customer")
        site = _get_ancestor(doc, "Site")
        lane = _get_ancestor(doc, "Lane")
        cell = _get_ancestor(doc, "Cell")

        for ancestor in (customer, site, lane, cell):
            if ancestor:
                parts.append(
                    _strip(ancestor.get("location_name"))
                    or _strip(ancestor.get("location_code"))
                )

        if location_type == "Robot":
            parts.append(_strip(doc.get("location_name")) or _strip(doc.get("location_code")))
        elif location_type == "Site":
            parts = [
                part
                for part in [
                    _strip(customer.get("location_name")) if customer else None,
                    _strip(doc.get("location_name")) or _strip(doc.location_code),
                ]
                if part
            ]
        elif location_type == "Customer":
            parts = [_strip(doc.get("location_name")) or _strip(doc.location_code)]

        doc.full_path = " / ".join([part for part in parts if part])
