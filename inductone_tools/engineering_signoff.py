import frappe
from frappe import _


SIGNOFF_ENABLED_DOCTYPES = [
    "BOM",
    "Product Bundle",
    "Item",
    "InductOne Configuration Option",
]

CONFIG_OPTION_DOCTYPE = "InductOne Configuration Option"
CONFIG_OPTION_DRAFT_STATUS = "Draft"
CONFIG_OPTION_RELEASED_STATUS = "Released"


# ---------- Public whitelisted methods ----------

@frappe.whitelist()
def request_signoff(target_doctype: str, target_docname: str):
    """
    Create a Pending signoff request for the given target.

    If a current signoff already exists for this target, it is invalidated
    and a new Pending record becomes current.

    Idempotent: if a current Pending record already exists for the target's
    current revision, return it without creating a duplicate.
    """
    _validate_target(target_doctype, target_docname)

    target_revision_id = _get_target_revision_id(target_doctype, target_docname)
    target_description = _get_target_description(target_doctype, target_docname)

    existing_current = frappe.get_all(
        "Engineering Signoff",
        filters={
            "target_doctype": target_doctype,
            "target_docname": target_docname,
            "is_current": 1,
        },
        fields=["name", "status", "target_revision_id"],
        limit=1,
    )

    if existing_current:
        cur = existing_current[0]

        if cur["status"] == "Pending" and cur["target_revision_id"] == target_revision_id:
            return {
                "ok": True,
                "signoff_name": cur["name"],
                "status": "Pending",
                "already_existed": True,
            }

        frappe.db.set_value("Engineering Signoff", cur["name"], "is_current", 0)

    signoff = frappe.new_doc("Engineering Signoff")
    signoff.target_doctype = target_doctype
    signoff.target_docname = target_docname
    signoff.target_revision_id = target_revision_id
    signoff.target_description = target_description
    signoff.status = "Pending"
    signoff.is_current = 1
    signoff.requested_at = frappe.utils.now_datetime()
    signoff.requested_by = frappe.session.user
    signoff.insert(ignore_permissions=True)

    frappe.db.commit()

    return {
        "ok": True,
        "signoff_name": signoff.name,
        "status": "Pending",
        "already_existed": False,
    }


@frappe.whitelist()
def approve_signoff(signoff_name: str, notes: str = None):
    """
    Approve a Pending signoff. Restricted to Engineering - Signoff role.

    For InductOne Configuration Option, approval is also the release action:
    approval sets the target option status to Released.
    """
    _require_signoff_role()
    signoff = frappe.get_doc("Engineering Signoff", signoff_name)

    # ---- Configuration Option readiness gate ----
    if signoff.target_doctype == CONFIG_OPTION_DOCTYPE:
        mapping_status = frappe.db.get_value(
            CONFIG_OPTION_DOCTYPE,
            signoff.target_docname,
            "mapping_status",
        )
        if mapping_status != "Complete":
            frappe.throw(_(
                "Cannot approve: Configuration Option '{0}' has Mapping Status '{1}'. "
                "Mapping Status must be Complete before a signoff can be approved."
            ).format(signoff.target_docname, mapping_status or "not set"))

    if signoff.status != "Pending":
        frappe.throw(_(
            "Cannot approve: signoff is in status '{0}'. Only Pending signoffs can be approved."
        ).format(signoff.status))

    if not signoff.is_current:
        frappe.throw(_(
            "Cannot approve: this signoff is no longer current. The target has been modified since this request was created."
        ))

    current_revision = _get_target_revision_id(signoff.target_doctype, signoff.target_docname)
    if signoff.target_revision_id != current_revision:
        frappe.db.set_value("Engineering Signoff", signoff.name, "is_current", 0)
        frappe.db.commit()
        frappe.throw(_(
            "Cannot approve: target {0} {1} has been modified since this signoff was requested. "
            "A new signoff request will be created automatically; please review that one instead."
        ).format(signoff.target_doctype, signoff.target_docname))

    now = frappe.utils.now_datetime()
    user = frappe.session.user

    signoff.status = "Approved"
    signoff.reviewed_at = now
    signoff.reviewed_by = user
    if notes:
        signoff.notes = notes
    signoff.save(ignore_permissions=True)

    _apply_target_approval_side_effects(signoff)

    try:
        target = frappe.get_doc(signoff.target_doctype, signoff.target_docname)
        target.add_comment(
            "Comment",
            text=(
                f"<strong>Engineering Signoff — APPROVED</strong> by {user} at {now}<br>"
                f"Signoff record: {signoff.name}<br>"
                f"{frappe.utils.escape_html(notes) if notes else '<em>(no notes)</em>'}"
            ),
        )
    except Exception:
        pass

    frappe.db.commit()

    return {
        "ok": True,
        "signoff_name": signoff.name,
        "status": "Approved",
        "reviewed_by": user,
        "reviewed_at": now,
    }


@frappe.whitelist()
def reject_signoff(signoff_name: str, reason: str):
    """
    Reject a Pending signoff. Restricted to Engineering - Signoff role.
    Reason is required.
    """
    _require_signoff_role()

    if not reason or not reason.strip():
        frappe.throw(_("A rejection reason is required."))

    signoff = frappe.get_doc("Engineering Signoff", signoff_name)

    if signoff.status != "Pending":
        frappe.throw(_(
            "Cannot reject: signoff is in status '{0}'. Only Pending signoffs can be rejected."
        ).format(signoff.status))

    now = frappe.utils.now_datetime()
    user = frappe.session.user

    signoff.status = "Rejected"
    signoff.reviewed_at = now
    signoff.reviewed_by = user
    signoff.notes = reason.strip()
    signoff.save(ignore_permissions=True)

    try:
        target = frappe.get_doc(signoff.target_doctype, signoff.target_docname)
        target.add_comment(
            "Comment",
            text=(
                f"<strong>Engineering Signoff — REJECTED</strong> by {user} at {now}<br>"
                f"Signoff record: {signoff.name}<br>"
                f"<strong>Reason:</strong> {frappe.utils.escape_html(reason)}"
            ),
        )
    except Exception:
        pass

    frappe.db.commit()

    return {
        "ok": True,
        "signoff_name": signoff.name,
        "status": "Rejected",
        "reviewed_by": user,
        "reviewed_at": now,
    }


@frappe.whitelist()
def get_current_signoff_status(target_doctype: str, target_docname: str):
    """
    Return the current signoff status for the given target.

    Returns one of: Pending, Approved, Rejected, or None.
    """
    if not target_doctype or not target_docname:
        return None

    record = frappe.get_all(
        "Engineering Signoff",
        filters={
            "target_doctype": target_doctype,
            "target_docname": target_docname,
            "is_current": 1,
        },
        fields=["name", "status", "target_revision_id"],
        limit=1,
    )

    if not record:
        return None

    return record[0]["status"]


@frappe.whitelist()
def get_current_signoff_record(target_doctype: str, target_docname: str):
    """
    Return the full current signoff record for the given target, or None.
    """
    if not target_doctype or not target_docname:
        return None

    records = frappe.get_all(
        "Engineering Signoff",
        filters={
            "target_doctype": target_doctype,
            "target_docname": target_docname,
            "is_current": 1,
        },
        fields=[
            "name",
            "status",
            "target_revision_id",
            "target_description",
            "requested_at",
            "requested_by",
            "reviewed_at",
            "reviewed_by",
            "notes",
        ],
        limit=1,
    )

    if not records:
        return None

    return records[0]


# ---------- Hook handlers ----------

def on_target_save(doc, method=None):
    """
    before_save handler for signoff-enabled targets.

    Configuration Option behavior:
      - Draft -> Released cannot be done manually.
      - Engineering Signoff approval is the release mechanism.
      - Any signoff-invalidating edit to a Released option demotes it to Draft.
    """
    if doc.doctype not in SIGNOFF_ENABLED_DOCTYPES:
        return

    if doc.is_new():
        return

    try:
        previous = frappe.get_doc(doc.doctype, doc.name)
    except Exception:
        return

    if doc.doctype == CONFIG_OPTION_DOCTYPE:
        old_status = getattr(previous, "status", None)
        new_status = getattr(doc, "status", None)

        if (
            new_status == CONFIG_OPTION_RELEASED_STATUS
            and old_status != CONFIG_OPTION_RELEASED_STATUS
            and not getattr(frappe.flags, "engineering_signoff_release_in_progress", False)
        ):
            frappe.throw(_(
                "InductOne Configuration Option cannot be manually set to Released. "
                "Approve the current Engineering Signoff record to release this option."
            ))

    if not _signoff_invalidating_change(doc, previous):
        return

    current = frappe.get_all(
        "Engineering Signoff",
        filters={
            "target_doctype": doc.doctype,
            "target_docname": doc.name,
            "is_current": 1,
        },
        fields=["name", "status"],
        limit=1,
    )

    if current:
        cur = current[0]
        frappe.db.set_value("Engineering Signoff", cur["name"], "is_current", 0)

        if cur["status"] == "Approved":
            try:
                doc.add_comment(
                    "Comment",
                    text=(
                        f"<strong>Engineering signoff invalidated</strong> due to modification by "
                        f"{frappe.session.user}. Re-signoff required before release."
                    ),
                )
            except Exception:
                pass

    if doc.doctype == CONFIG_OPTION_DOCTYPE:
        if getattr(previous, "status", None) == CONFIG_OPTION_RELEASED_STATUS:
            doc.status = CONFIG_OPTION_DRAFT_STATUS
            try:
                doc.add_comment(
                    "Comment",
                    text=(
                        f"<strong>Configuration Option demoted from Released to Draft</strong> "
                        f"due to engineering-signoff-invalidating modification by {frappe.session.user}. "
                        f"Re-signoff required before release."
                    ),
                )
            except Exception:
                pass


def on_target_after_insert(doc, method=None):
    """
    after_insert handler. Auto-create a Pending signoff request.
    """
    if doc.doctype not in SIGNOFF_ENABLED_DOCTYPES:
        return

    signoff_required = int(getattr(doc, "signoff_required", 1) or 1)
    if not signoff_required:
        return

    try:
        request_signoff(doc.doctype, doc.name)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "engineering_signoff: auto-request on insert failed",
        )


def on_target_after_save(doc, method=None):
    """
    on_update handler. If before_save invalidated the current signoff,
    create a fresh Pending request after the target save completes.
    """
    if doc.doctype not in SIGNOFF_ENABLED_DOCTYPES:
        return

    if doc.is_new():
        return

    signoff_required = int(getattr(doc, "signoff_required", 1) or 1)
    if not signoff_required:
        return

    current = frappe.get_all(
        "Engineering Signoff",
        filters={
            "target_doctype": doc.doctype,
            "target_docname": doc.name,
            "is_current": 1,
        },
        limit=1,
    )

    if current:
        return

    try:
        request_signoff(doc.doctype, doc.name)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "engineering_signoff: auto-request on save failed",
        )


# ---------- Internal helpers ----------

def _validate_target(target_doctype, target_docname):
    if target_doctype not in SIGNOFF_ENABLED_DOCTYPES:
        frappe.throw(_(
            "Target doctype '{0}' is not enabled for engineering signoff. "
            "Enabled doctypes: {1}"
        ).format(target_doctype, ", ".join(SIGNOFF_ENABLED_DOCTYPES)))

    if not frappe.db.exists(target_doctype, target_docname):
        frappe.throw(_(
            "Target {0} '{1}' does not exist."
        ).format(target_doctype, target_docname))


def _get_target_revision_id(target_doctype, target_docname):
    modified = frappe.db.get_value(target_doctype, target_docname, "modified")
    return str(modified) if modified else ""


def _get_target_description(target_doctype, target_docname):
    if target_doctype == "BOM":
        bom = frappe.db.get_value(
            "BOM",
            target_docname,
            ["item", "item_name", "is_active", "is_default"],
            as_dict=True,
        ) or {}

        parts = []
        if bom.get("item_name"):
            parts.append(bom["item_name"])
        if bom.get("item"):
            parts.append(f"({bom['item']})")
        if bom.get("is_default"):
            parts.append("[Default]")
        if not bom.get("is_active"):
            parts.append("[INACTIVE]")

        return " ".join(parts) if parts else target_docname

    if target_doctype == "Product Bundle":
        bundle = frappe.db.get_value(
            "Product Bundle",
            target_docname,
            ["new_item_code", "description"],
            as_dict=True,
        ) or {}

        parts = []
        if bundle.get("description"):
            parts.append(bundle["description"])
        if bundle.get("new_item_code"):
            parts.append(f"({bundle['new_item_code']})")

        return " ".join(parts) if parts else target_docname

    if target_doctype == "Item":
        item = frappe.db.get_value(
            "Item",
            target_docname,
            ["item_code", "item_name", "item_group", "is_stock_item", "has_serial_no", "disabled"],
            as_dict=True,
        ) or {}

        parts = []
        if item.get("item_name"):
            parts.append(item["item_name"])
        if item.get("item_code"):
            parts.append(f"({item['item_code']})")
        if item.get("item_group"):
            parts.append(f"[{item['item_group']}]")
        if item.get("has_serial_no"):
            parts.append("[Serialized]")
        if item.get("disabled"):
            parts.append("[DISABLED]")

        return " ".join(parts) if parts else target_docname

    if target_doctype == CONFIG_OPTION_DOCTYPE:
        option = frappe.db.get_value(
            CONFIG_OPTION_DOCTYPE,
            target_docname,
            [
                "option_code",
                "option_name",
                "option_category",
                "option_group",
                "status",
                "mapping_status",
                "is_active",
            ],
            as_dict=True,
        ) or {}

        parts = []
        if option.get("option_code"):
            parts.append(option["option_code"])
        if option.get("option_name"):
            parts.append(f"— {option['option_name']}")
        if option.get("option_category"):
            parts.append(f"[{option['option_category']}]")
        if option.get("option_group"):
            parts.append(f"[{option['option_group']}]")
        if option.get("status"):
            parts.append(f"Status: {option['status']}")
        if option.get("mapping_status"):
            parts.append(f"Mapping: {option['mapping_status']}")
        if not option.get("is_active"):
            parts.append("[INACTIVE]")

        return " ".join(parts) if parts else target_docname

    return target_docname


def _signoff_invalidating_change(new_doc, old_doc):
    if new_doc.doctype == CONFIG_OPTION_DOCTYPE:
        return _config_option_invalidating_change(new_doc, old_doc)

    if new_doc.doctype == "Item":
        return _item_invalidating_change(new_doc, old_doc)

    if int(getattr(new_doc, "is_active", 0) or 0) != int(getattr(old_doc, "is_active", 0) or 0):
        return True

    new_items = _serialize_items_table(getattr(new_doc, "items", []) or [])
    old_items = _serialize_items_table(getattr(old_doc, "items", []) or [])

    if new_items != old_items:
        return True

    if new_doc.doctype == "BOM":
        new_ops = _serialize_items_table(getattr(new_doc, "operations", []) or [])
        old_ops = _serialize_items_table(getattr(old_doc, "operations", []) or [])
        if new_ops != old_ops:
            return True

    return False


def _config_option_invalidating_change(new_doc, old_doc):
    """
    Intentionally ignores status itself.
    Status is controlled by the signoff approval side effect.
    """
    scalar_fields = [
        "option_code",
        "option_name",
        "option_category",
        "option_group",
        "option_group_required",
        "is_default_selection",
        "is_active",
        "sort_order",
        "mapping_status",
        "effective_date",
        "owner_role",
        "requires_ops_approval",
        "internal_notes",
        "builder_description",
    ]

    for fieldname in scalar_fields:
        if _norm(getattr(new_doc, fieldname, None)) != _norm(getattr(old_doc, fieldname, None)):
            return True

    new_mappings = _serialize_config_option_mappings(getattr(new_doc, "mappings_table", []) or [])
    old_mappings = _serialize_config_option_mappings(getattr(old_doc, "mappings_table", []) or [])

    if new_mappings != old_mappings:
        return True

    return False


def _item_invalidating_change(new_doc, old_doc):
    """
    Item signoff does not change Item status/lifecycle.
    It only invalidates the Engineering Signoff when release-relevant fields change.
    """
    scalar_fields = [
        "item_code",
        "item_name",
        "item_group",
        "description",
        "stock_uom",
        "is_stock_item",
        "has_serial_no",
        "serial_no_series",
        "has_batch_no",
        "disabled",
        "include_item_in_manufacturing",
        "default_bom",
        "valuation_rate",
        "standard_rate",

        "custom_part_number_control",
        "custom_part_number",
        "custom_part_rev",
        "custom_revision",
        "custom_source",
        "custom_source_type",
        "custom_engineering_release_status",
        "custom_drawing_number",
        "custom_drawing_revision",
        "custom_manufacturer_part_number",
    ]

    for fieldname in scalar_fields:
        if _norm(getattr(new_doc, fieldname, None)) != _norm(getattr(old_doc, fieldname, None)):
            return True

    return False


def _serialize_items_table(items):
    out = []
    for row in items:
        out.append((
            getattr(row, "item_code", None),
            float(getattr(row, "qty", 0) or 0),
            getattr(row, "uom", None),
            getattr(row, "bom_no", None),
            float(getattr(row, "rate", 0) or 0) if hasattr(row, "rate") else 0,
        ))
    return tuple(out)


def _serialize_config_option_mappings(rows):
    out = []

    for row in rows:
        out.append((
            int(getattr(row, "idx", 0) or 0),
            _norm(getattr(row, "action", None)),
            _norm(getattr(row, "target_item", None)),
            _norm(getattr(row, "replace_with_item", None)),
            _norm(getattr(row, "replace_scope", None)),
            int(getattr(row, "replace_count", 0) or 0),
            _norm(getattr(row, "structural_effect_mode", None)),
            int(getattr(row, "preserve_target_item_identity", 0) or 0),
            _norm(getattr(row, "expand_mode", None)),
            _norm(getattr(row, "qty_source", None)),
            float(getattr(row, "qty_fixed", 0) or 0),
            _norm(getattr(row, "parameter_key", None)),
            int(getattr(row, "required_for_release", 0) or 0),
            int(getattr(row, "row_order", 0) or 0),
        ))

    return tuple(out)


def _apply_target_approval_side_effects(signoff):
    """
    Configuration Option approval is the release action.
    """
    if signoff.target_doctype != CONFIG_OPTION_DOCTYPE:
        return

    if not frappe.db.exists(CONFIG_OPTION_DOCTYPE, signoff.target_docname):
        return

    try:
        frappe.flags.engineering_signoff_release_in_progress = True

        frappe.db.set_value(
            CONFIG_OPTION_DOCTYPE,
            signoff.target_docname,
            {
                "status": CONFIG_OPTION_RELEASED_STATUS,
            },
            update_modified=True,
        )

        refreshed_revision = _get_target_revision_id(CONFIG_OPTION_DOCTYPE, signoff.target_docname)

        frappe.db.set_value(
            "Engineering Signoff",
            signoff.name,
            {
                "target_revision_id": refreshed_revision,
                "target_description": _get_target_description(CONFIG_OPTION_DOCTYPE, signoff.target_docname),
            },
            update_modified=False,
        )

        try:
            target = frappe.get_doc(CONFIG_OPTION_DOCTYPE, signoff.target_docname)
            target.add_comment(
                "Comment",
                text=(
                    f"<strong>Configuration Option released by Engineering Signoff</strong><br>"
                    f"Signoff record: {signoff.name}<br>"
                    f"Released by: {frappe.session.user}<br>"
                    f"Released at: {frappe.utils.now_datetime()}"
                ),
            )
        except Exception:
            pass

    finally:
        frappe.flags.engineering_signoff_release_in_progress = False


def _norm(value):
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, bool):
        return int(value)

    return value


def _require_signoff_role():
    user_roles = frappe.get_roles(frappe.session.user)
    if "Engineering - Signoff" not in user_roles and "System Manager" not in user_roles:
        frappe.throw(
            _("This action requires the 'Engineering - Signoff' role."),
            frappe.PermissionError,
        )
