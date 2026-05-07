import frappe
from frappe import _


# Doctypes that can be signed off via this system.
# Add to this list as the governance pattern grows.
SIGNOFF_ENABLED_DOCTYPES = ["BOM", "Product Bundle"]


# ---------- Public whitelisted methods ----------

@frappe.whitelist()
def request_signoff(target_doctype: str, target_docname: str):
    """
    Create a Pending signoff request for the given target.
    
    If a current signoff already exists for this target, it is invalidated
    (is_current = 0) and a new Pending record becomes current.
    
    Idempotent: if a current Pending record already exists for this target's
    current revision, returns it without creating a duplicate.
    """
    _validate_target(target_doctype, target_docname)
    
    target_revision_id = _get_target_revision_id(target_doctype, target_docname)
    target_description = _get_target_description(target_doctype, target_docname)
    
    # Check for existing current record
    existing_current = frappe.get_all(
        "Engineering Signoff",
        filters={
            "target_doctype": target_doctype,
            "target_docname": target_docname,
            "is_current": 1
        },
        fields=["name", "status", "target_revision_id"],
        limit=1
    )
    
    if existing_current:
        cur = existing_current[0]
        # If the current record matches this revision and is Pending, return it (idempotent)
        if cur["status"] == "Pending" and cur["target_revision_id"] == target_revision_id:
            return {
                "ok": True,
                "signoff_name": cur["name"],
                "status": "Pending",
                "already_existed": True
            }
        # Otherwise invalidate the current record (revision changed, or status was Approved/Rejected and target changed)
        frappe.db.set_value("Engineering Signoff", cur["name"], "is_current", 0)
    
    # Create a new Pending record
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
        "already_existed": False
    }


@frappe.whitelist()
def approve_signoff(signoff_name: str, notes: str = None):
    """
    Approve a Pending signoff. Restricted to Engineering - Signoff role.
    """
    _require_signoff_role()
    
    signoff = frappe.get_doc("Engineering Signoff", signoff_name)
    
    if signoff.status != "Pending":
        frappe.throw(_(
            "Cannot approve: signoff is in status '{0}'. Only Pending signoffs can be approved."
        ).format(signoff.status))
    
    if not signoff.is_current:
        frappe.throw(_(
            "Cannot approve: this signoff is no longer current. The target has been modified since this request was created."
        ))
    
    # Verify revision still matches (defensive: someone might have modified between request and review)
    current_revision = _get_target_revision_id(signoff.target_doctype, signoff.target_docname)
    if signoff.target_revision_id != current_revision:
        # Auto-invalidate this record and refuse approval
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
    
    # Add a comment to the target for audit trail
    try:
        target = frappe.get_doc(signoff.target_doctype, signoff.target_docname)
        target.add_comment(
            "Comment",
            text=(
                f"<strong>Engineering Signoff — APPROVED</strong> by {user} at {now}<br>"
                f"Signoff record: {signoff.name}<br>"
                f"{frappe.utils.escape_html(notes) if notes else '<em>(no notes)</em>'}"
            )
        )
    except Exception:
        # Don't fail the approval if commenting fails (target might not support comments)
        pass
    
    frappe.db.commit()
    
    return {
        "ok": True,
        "signoff_name": signoff.name,
        "status": "Approved",
        "reviewed_by": user,
        "reviewed_at": now
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
            )
        )
    except Exception:
        pass
    
    frappe.db.commit()
    
    return {
        "ok": True,
        "signoff_name": signoff.name,
        "status": "Rejected",
        "reviewed_by": user,
        "reviewed_at": now
    }


@frappe.whitelist()
def get_current_signoff_status(target_doctype: str, target_docname: str):
    """
    Return the current signoff status for the given target.
    
    Returns one of: 'Pending', 'Approved', 'Rejected', or None if no current signoff exists.
    
    This is the canonical way for downstream consumers (InductOne release readiness,
    future workflows) to check whether a target is approved.
    """
    if not target_doctype or not target_docname:
        return None
    
    record = frappe.get_all(
        "Engineering Signoff",
        filters={
            "target_doctype": target_doctype,
            "target_docname": target_docname,
            "is_current": 1
        },
        fields=["name", "status", "target_revision_id"],
        limit=1
    )
    
    if not record:
        return None
    
    return record[0]["status"]


@frappe.whitelist()
def get_current_signoff_record(target_doctype: str, target_docname: str):
    """
    Return the full current signoff record for the given target, or None.
    Useful for showing context (who approved, when, notes, etc.) in UI.
    """
    if not target_doctype or not target_docname:
        return None
    
    records = frappe.get_all(
        "Engineering Signoff",
        filters={
            "target_doctype": target_doctype,
            "target_docname": target_docname,
            "is_current": 1
        },
        fields=[
            "name", "status", "target_revision_id", "target_description",
            "requested_at", "requested_by", "reviewed_at", "reviewed_by", "notes"
        ],
        limit=1
    )
    
    if not records:
        return None
    
    return records[0]


# ---------- Hook handlers ----------

def on_target_save(doc, method=None):
    """
    Hook handler called from BOM and Product Bundle before_save events.
    
    If the target has been modified in a way that affects signoff,
    invalidate the current Approved or Pending signoff and create a new
    Pending signoff request.
    
    Conservative invalidation rule: changes to the items table or 
    is_active invalidate; header-only changes do not.
    """
    if doc.doctype not in SIGNOFF_ENABLED_DOCTYPES:
        return
    
    # New documents: defer to after_insert hook
    if doc.is_new():
        return
    
    # Compare against previous saved state
    try:
        previous = frappe.get_doc(doc.doctype, doc.name)
    except Exception:
        return
    
    if not _signoff_invalidating_change(doc, previous):
        return
    
    # Find current signoff for this target
    current = frappe.get_all(
        "Engineering Signoff",
        filters={
            "target_doctype": doc.doctype,
            "target_docname": doc.name,
            "is_current": 1
        },
        fields=["name", "status"],
        limit=1
    )
    
    if not current:
        # No current record; one will be created via after_insert path or by manual request
        return
    
    cur = current[0]
    
    if cur["status"] == "Approved":
        # Invalidate the approved record. A new Pending one will be requested below.
        frappe.db.set_value("Engineering Signoff", cur["name"], "is_current", 0)
        try:
            doc.add_comment(
                "Comment",
                text=(
                    f"<strong>Engineering signoff invalidated</strong> due to modification by "
                    f"{frappe.session.user}. Re-signoff required before release."
                )
            )
        except Exception:
            pass
    elif cur["status"] == "Pending":
        # Pending record exists but target changed; invalidate and create fresh request
        frappe.db.set_value("Engineering Signoff", cur["name"], "is_current", 0)
    elif cur["status"] == "Rejected":
        # Previously rejected; if Ops has now fixed and saved, treat as a fresh request
        frappe.db.set_value("Engineering Signoff", cur["name"], "is_current", 0)


def on_target_after_insert(doc, method=None):
    """
    Hook handler called after BOM or Product Bundle is created.
    Auto-create a Pending signoff request.
    """
    if doc.doctype not in SIGNOFF_ENABLED_DOCTYPES:
        return
    
    # Optional escape hatch: respect signoff_required if the field exists
    signoff_required = int(getattr(doc, "signoff_required", 1) or 1)
    if not signoff_required:
        return
    
    try:
        request_signoff(doc.doctype, doc.name)
    except Exception:
        # Don't block the save if signoff request fails; log instead
        frappe.log_error(
            frappe.get_traceback(),
            "engineering_signoff: auto-request on insert failed"
        )


def on_target_after_save(doc, method=None):
    """
    Hook handler called after BOM or Product Bundle is saved (after on_target_save invalidation).
    
    If we just invalidated a current signoff in on_target_save, create a fresh Pending request.
    """
    if doc.doctype not in SIGNOFF_ENABLED_DOCTYPES:
        return
    
    if doc.is_new():
        return
    
    # Optional escape hatch
    signoff_required = int(getattr(doc, "signoff_required", 1) or 1)
    if not signoff_required:
        return
    
    # Check if there's currently no current signoff (because we just invalidated one)
    current = frappe.get_all(
        "Engineering Signoff",
        filters={
            "target_doctype": doc.doctype,
            "target_docname": doc.name,
            "is_current": 1
        },
        limit=1
    )
    
    if current:
        # Still has a current record; nothing to do
        return
    
    # No current record means we need to create a fresh Pending request
    try:
        request_signoff(doc.doctype, doc.name)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "engineering_signoff: auto-request on save failed"
        )


# ---------- Internal helpers ----------

def _validate_target(target_doctype, target_docname):
    """Validate that the target is signoff-eligible and exists."""
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
    """
    Return a stable identifier of the target's current state.
    Uses the modified timestamp, which changes on every save.
    """
    modified = frappe.db.get_value(target_doctype, target_docname, "modified")
    return str(modified) if modified else ""


def _get_target_description(target_doctype, target_docname):
    """
    Return a human-readable description of the target for display in the signoff record.
    """
    if target_doctype == "BOM":
        bom = frappe.db.get_value(
            "BOM",
            target_docname,
            ["item", "item_name", "is_active", "is_default"],
            as_dict=True
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
    
    elif target_doctype == "Product Bundle":
        bundle = frappe.db.get_value(
            "Product Bundle",
            target_docname,
            ["new_item_code", "description"],
            as_dict=True
        ) or {}
        parts = []
        if bundle.get("description"):
            parts.append(bundle["description"])
        if bundle.get("new_item_code"):
            parts.append(f"({bundle['new_item_code']})")
        return " ".join(parts) if parts else target_docname
    
    return target_docname


def _signoff_invalidating_change(new_doc, old_doc):
    """
    Detect whether the change from old_doc to new_doc invalidates signoff.
    
    Conservative rule: changes to items table or is_active invalidate;
    header-only changes (description, etc.) do not.
    """
    # Check is_active change
    if int(getattr(new_doc, "is_active", 0) or 0) != int(getattr(old_doc, "is_active", 0) or 0):
        return True
    
    # Check items table — both BOM and Product Bundle use 'items'
    new_items = _serialize_items_table(getattr(new_doc, "items", []) or [])
    old_items = _serialize_items_table(getattr(old_doc, "items", []) or [])
    
    if new_items != old_items:
        return True
    
    # For BOM, also check operations
    if new_doc.doctype == "BOM":
        new_ops = _serialize_items_table(getattr(new_doc, "operations", []) or [])
        old_ops = _serialize_items_table(getattr(old_doc, "operations", []) or [])
        if new_ops != old_ops:
            return True
    
    return False


def _serialize_items_table(items):
    """Convert a child table into a comparable tuple of key fields."""
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


def _require_signoff_role():
    """Raise PermissionError if current user lacks Engineering - Signoff role."""
    user_roles = frappe.get_roles(frappe.session.user)
    if "Engineering - Signoff" not in user_roles and "System Manager" not in user_roles:
        frappe.throw(
            _("This action requires the 'Engineering - Signoff' role."),
            frappe.PermissionError
        )