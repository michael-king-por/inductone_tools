import frappe
from frappe.utils import now_datetime


@frappe.whitelist()
def create_as_built_from_completion(completion_name: str):
    """
    Create an InductOne As-Built Record from an InductOne Build Completion.

    Expected doctypes / fields:
      - InductOne Build Completion
          - inductone_build
          - configuration_order
          - configured_snapshot (optional)
          - builder_supplier (optional)
          - status
          - serials (child table)
              - item_code
              - serial_number
              - notes (optional)

      - InductOne As-Built Record
          - inductone_build
          - configuration_order
          - build_completion
          - configured_snapshot (optional)
          - builder_supplier (optional)
          - status
          - created_at
          - created_by
          - accepted_at (optional)
          - accepted_by (optional)
          - serials (child table)
              - item_code
              - serial_number
              - source_completion_row (optional)
              - notes (optional)

      - InductOne Build
          - latest_build_completion (optional)
          - as_built_record (optional)
          - completion_status (optional)
          - completed_at (optional)

      - InductOne Configuration Order
          - build_completion (optional)
          - as_built_record (optional)

    Behavior:
      - loads completion
      - creates as-built record
      - copies serial rows
      - updates completion/build/config order links and status
      - returns created as-built record name
    """

    if not completion_name:
        frappe.throw("completion_name is required.")

    completion = frappe.get_doc("InductOne Build Completion", completion_name)

    if not completion.inductone_build:
        frappe.throw("InductOne Build Completion must have InductOne Build.")

    if not completion.configuration_order:
        frappe.throw("InductOne Build Completion must have Configuration Order.")

    if not completion.serials or len(completion.serials) == 0:
        frappe.throw("InductOne Build Completion must contain at least one serial row.")

    # Prevent duplicate creation if the completion is already linked from an existing As-Built record
    existing = frappe.get_all(
        "InductOne As-Built Record",
        filters={"build_completion": completion.name},
        fields=["name"],
        limit=1,
    )
    if existing:
        return {
            "ok": True,
            "as_built_record": existing[0]["name"],
            "already_exists": True,
        }

    now_dt = now_datetime()
    current_user = frappe.session.user

    # Create As-Built record
    as_built = frappe.new_doc("InductOne As-Built Record")
    as_built.inductone_build = completion.inductone_build
    as_built.configuration_order = completion.configuration_order
    as_built.build_completion = completion.name

    if hasattr(as_built, "configured_snapshot"):
        as_built.configured_snapshot = getattr(completion, "configured_snapshot", None)

    if hasattr(as_built, "builder_supplier"):
        as_built.builder_supplier = getattr(completion, "builder_supplier", None)

    if hasattr(as_built, "status"):
        as_built.status = "Draft"

    if hasattr(as_built, "created_at"):
        as_built.created_at = now_dt

    if hasattr(as_built, "created_by"):
        as_built.created_by = current_user

    # Copy serial rows
    for row in completion.serials or []:
        child = {
            "item_code": getattr(row, "item_code", None),
            "serial_number": getattr(row, "serial_number", None),
        }

        if hasattr(row, "notes"):
            child["notes"] = getattr(row, "notes", "") or ""

        if "source_completion_row" in [df.fieldname for df in as_built.meta.get_field("serials").options and frappe.get_meta(as_built.meta.get_field("serials").options).fields]:
            child["source_completion_row"] = getattr(row, "name", "")

        as_built.append("serials", child)

    as_built.insert(ignore_permissions=True)

    # Update completion
    completion.status = "Accepted"
    if hasattr(completion, "reviewed_at") and not getattr(completion, "reviewed_at", None):
        completion.reviewed_at = now_dt
    if hasattr(completion, "reviewed_by") and not getattr(completion, "reviewed_by", None):
        completion.reviewed_by = current_user
    completion.save(ignore_permissions=True)

    # Update InductOne Build
    build = frappe.get_doc("InductOne Build", completion.inductone_build)

    if hasattr(build, "latest_build_completion"):
        build.latest_build_completion = completion.name

    if hasattr(build, "as_built_record"):
        build.as_built_record = as_built.name

    if hasattr(build, "completion_status"):
        build.completion_status = "Accepted"

    if hasattr(build, "completed_at"):
        build.completed_at = now_dt

    build.save(ignore_permissions=True)

    # Update Configuration Order
    config_order = frappe.get_doc("InductOne Configuration Order", completion.configuration_order)

    if hasattr(config_order, "build_completion"):
        config_order.build_completion = completion.name

    if hasattr(config_order, "as_built_record"):
        config_order.as_built_record = as_built.name

    config_order.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "ok": True,
        "as_built_record": as_built.name,
        "already_exists": False,
    }