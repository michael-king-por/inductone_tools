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
CONFIG_OPTION_DEPRECATED_STATUS = "Deprecated"

# Doctypes that auto-create a Pending signoff on insert.
# Configuration Option is intentionally excluded: its signoff is triggered
# manually once the option has been released on GitLab and is ready for review.
AUTO_SIGNOFF_ON_INSERT_DOCTYPES = [
    "BOM",
    "Product Bundle",
    "Item",
]


# ---------- Public whitelisted methods ----------

@frappe.whitelist()
def request_signoff(target_doctype: str, target_docname: str):
    """
    Create a Pending signoff request for the given target.

    If a current signoff already exists for this target, it is superseded
    (is_current -> 0) and a new Pending record becomes current.

    Idempotent: if a current Pending record already exists at the target's
    current revision, return it without creating a duplicate.
    """
    _validate_target(target_doctype, target_docname)

    # Configuration Options can only have a signoff requested while Draft.
    # Released options are locked; Deprecated options are retired.
    if target_doctype == CONFIG_OPTION_DOCTYPE:
        status = frappe.db.get_value(CONFIG_OPTION_DOCTYPE, target_docname, "status")
        if status != CONFIG_OPTION_DRAFT_STATUS:
            frappe.throw(_(
                "Configuration Option '{0}' has status '{1}'. A signoff can only be "
                "requested while the option is Draft."
            ).format(target_docname, status or "not set"))

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

        # Stamp a superseded Pending record so it never masquerades as live.
        # Approved/Rejected records keep their status (history); only Pending
        # ones, which are now meaningless, are relabelled.
        supersede_updates = {"is_current": 0}
        if cur["status"] == "Pending":
            supersede_updates["status"] = "Superseded"
        frappe.db.set_value("Engineering Signoff", cur["name"], supersede_updates)

    # NOTE: this instantiation line was missing in the broken version, which is
    # why auto-re-requests crashed with NameError and left orphaned (is_current=0,
    # no replacement) signoffs. Do not remove it.
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
    Approve a Pending signoff. Restricted to Engineering User role.

    For InductOne Configuration Option, approval is also the release action:
    approval sets the target option status to Released (and locks it).
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
        cur = frappe.get_all(
            "Engineering Signoff",
            filters={
                "target_doctype": signoff.target_doctype,
                "target_docname": signoff.target_docname,
                "is_current": 1,
            },
            fields=["name"],
            limit=1,
        )
        msg = _(
            "Cannot approve: this signoff is no longer current. "
            "It has been superseded by a newer request."
        )
        if cur:
            msg += " " + _("The current request is {0}.").format(cur[0]["name"])
        frappe.throw(msg)

    # Edits do not invalidate signoffs in this model: a meaningful change is a
    # new record (new revision) with its own signoff, while minor edits to an
    # existing record are acceptable. Approval therefore accepts the current
    # state and records the revision actually approved. (The old revision-gate
    # here generated a dead Pending record on every approval whose target had
    # been touched since request — including a normal submit — so it is removed.)
    signoff.target_revision_id = _get_target_revision_id(
        signoff.target_doctype, signoff.target_docname
    )

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
    Reject a Pending signoff. Restricted to Engineering User role.
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
def supersede_config_option(option_name: str, new_option_code: str = None, notes: str = None):
    """
    Supersede a Released Configuration Option.

    Released options are immutable. To revise one, clone it into a new Draft
    option (carrying its mappings), mark the original Deprecated, and invalidate
    the original's current signoff. The new Draft goes through signoff fresh.

    Restricted to Engineering User role: superseding a released,
    build-driving option is an engineering action.
    """
    _require_signoff_role()

    original = frappe.get_doc(CONFIG_OPTION_DOCTYPE, option_name)

    if original.status != CONFIG_OPTION_RELEASED_STATUS:
        frappe.throw(_(
            "Only a Released Configuration Option can be superseded. "
            "'{0}' is currently '{1}'."
        ).format(option_name, original.status))

    base_code = original.get("option_code") or option_name
    if not new_option_code:
        new_option_code = _next_supersede_code(base_code)

    if frappe.db.exists(CONFIG_OPTION_DOCTYPE, {"option_code": new_option_code}):
        frappe.throw(_(
            "A Configuration Option with code '{0}' already exists. "
            "Provide a different code."
        ).format(new_option_code))

    # Clone (copy_doc carries the mappings child table) and reset to Draft.
    new_option = frappe.copy_doc(original)
    new_option.option_code = new_option_code
    new_option.status = CONFIG_OPTION_DRAFT_STATUS
    new_option.insert(ignore_permissions=True)

    # Deprecate the original. set_value bypasses the before_save lock by design;
    # the lock is meant to stop human UI edits, not controlled lifecycle moves.
    frappe.db.set_value(
        CONFIG_OPTION_DOCTYPE,
        option_name,
        "status",
        CONFIG_OPTION_DEPRECATED_STATUS,
        update_modified=True,
    )

    # Invalidate the original's current signoff — it's retired now.
    cur = frappe.get_all(
        "Engineering Signoff",
        filters={
            "target_doctype": CONFIG_OPTION_DOCTYPE,
            "target_docname": option_name,
            "is_current": 1,
        },
        fields=["name"],
        limit=1,
    )
    if cur:
        frappe.db.set_value("Engineering Signoff", cur[0]["name"], "is_current", 0)

    user = frappe.session.user
    now = frappe.utils.now_datetime()

    for docname, text in (
        (option_name, (
            f"<strong>Configuration Option SUPERSEDED</strong> by {user} at {now}<br>"
            f"Superseded by: {new_option.name} (code {new_option_code})<br>"
            f"{frappe.utils.escape_html(notes) if notes else '<em>(no notes)</em>'}"
        )),
        (new_option.name, (
            f"<strong>Configuration Option created by SUPERSEDE</strong> of {option_name} "
            f"by {user} at {now}. Edit as needed, then request Engineering Signoff."
        )),
    ):
        try:
            frappe.get_doc(CONFIG_OPTION_DOCTYPE, docname).add_comment("Comment", text=text)
        except Exception:
            pass

    frappe.db.commit()

    return {
        "ok": True,
        "original": option_name,
        "new_option": new_option.name,
        "new_option_code": new_option_code,
    }


@frappe.whitelist()
def get_current_signoff_status(target_doctype: str, target_docname: str):
    """
    Return the current signoff status for the given target.
    One of: Pending, Approved, Rejected, or None.
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
    before_save handler. Wired ONLY to InductOne Configuration Option.

    Two guards, both Configuration-Option-specific:
      1. Immutability: Released and Deprecated options cannot be edited.
         (Supersede creates a new Draft instead.)
      2. Manual release block: Draft cannot be flipped to Released by hand;
         only Engineering Signoff approval releases an option.

    There is intentionally NO signoff-invalidation here. Per process, edits do
    not trigger or invalidate signoffs — only new records get signoffs, and
    Released options are locked outright.
    """
    if doc.doctype != CONFIG_OPTION_DOCTYPE:
        return

    if doc.is_new():
        return

    try:
        previous = frappe.get_doc(doc.doctype, doc.name)
    except Exception:
        return

    old_status = getattr(previous, "status", None)
    new_status = getattr(doc, "status", None)
    release_in_progress = getattr(
        frappe.flags, "engineering_signoff_release_in_progress", False
    )

    # Guard 1 — immutability of Released / Deprecated options.
    if old_status in (CONFIG_OPTION_RELEASED_STATUS, CONFIG_OPTION_DEPRECATED_STATUS):
        if not release_in_progress:
            frappe.throw(_(
                "InductOne Configuration Option '{0}' is {1} and is locked. "
                "Released and Deprecated options are immutable. "
                "Use the Supersede action to create a new editable revision."
            ).format(doc.name, old_status))

    # Guard 2 — manual Draft -> Released is not allowed.
    if (
        new_status == CONFIG_OPTION_RELEASED_STATUS
        and old_status != CONFIG_OPTION_RELEASED_STATUS
        and not release_in_progress
    ):
        frappe.throw(_(
            "InductOne Configuration Option cannot be manually set to Released. "
            "Approve the current Engineering Signoff record to release this option."
        ))


def on_target_after_insert(doc, method=None):
    """
    after_insert handler. Auto-create a Pending signoff for newly inserted
    targets in AUTO_SIGNOFF_ON_INSERT_DOCTYPES (BOM, Item, Product Bundle).

    Configuration Options are excluded — their signoff is requested manually.
    Existing (grandfathered) records are never touched: this only fires on
    genuinely new inserts.
    """
    if doc.doctype not in AUTO_SIGNOFF_ON_INSERT_DOCTYPES:
        return

    try:
        request_signoff(doc.doctype, doc.name)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "engineering_signoff: auto-request on insert failed",
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


def _next_supersede_code(base_code):
    """
    Given an option code, return the next -R<n> revision code.
    'CBL-EXT'    -> 'CBL-EXT-R2'
    'CBL-EXT-R2' -> 'CBL-EXT-R3'
    """
    import re

    base_code = (base_code or "").strip()
    match = re.search(r"^(.*)-R(\d+)$", base_code)
    if match:
        stem, num = match.group(1), int(match.group(2))
        return f"{stem}-R{num + 1}"
    return f"{base_code}-R2"


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


def _apply_target_approval_side_effects(signoff):
    """
    Configuration Option approval is the release action: set status to Released.
    The release flag lets the (set_value) write past the before_save guards;
    set_value does not run before_save, but the flag is kept for defensiveness.
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


def _require_signoff_role():
    user_roles = frappe.get_roles(frappe.session.user)
    if not {"Engineering User", "InductOne Process Architect", "System Manager"} & set(user_roles):
        frappe.throw(
            _("This action requires the 'Engineering User' role."),
            frappe.PermissionError,
        )
