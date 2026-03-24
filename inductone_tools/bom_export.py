import os
import csv
import io
import zipfile
from urllib.parse import urlparse

import frappe
from frappe.utils import now
from frappe.utils.file_manager import save_file

# Watermark deps (soft import; if missing, we fall back to original PDF + log warning)
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
    from pypdf import PdfReader, PdfWriter
except Exception:
    canvas = None
    inch = None
    PdfReader = None
    PdfWriter = None


# -----------------------------
# Public Entry Point (Button)
# -----------------------------

@frappe.whitelist()
def generate_now(package_name: str):
    """
    Synchronous export entrypoint (no queue).
    IMPORTANT: Avoid doc.save() to prevent optimistic-lock conflicts on the open form.
    """
    _set_status(package_name, "Running")
    _append_log(package_name, f"[{now()}] Starting synchronous export.")

    doc = frappe.get_doc("BOM Export Package", package_name)
    _validate_package(doc)

    # Reset outputs for rerun (db-level)
    frappe.db.set_value("BOM Export Package", package_name, "output_zip", None)
    frappe.db.set_value("BOM Export Package", package_name, "missing_files_summary", None)

    # Clear results child table without saving parent
    _clear_results_table(doc)

    try:
        # 1) Resolve rows
        if (doc.source_mode or "BOM") == "Configured Build":
            rows = build_configured_rows(doc)
        else:
            rows = explode_bom_tree(
                root_bom=doc.bom,
                explosion_mode=doc.explosion_mode or "Follow Explicit Child BOM Links",
                max_depth=doc.max_depth,
                include_qty=bool(getattr(doc, "include_qty", 1)),
            )

        # 2) Collect attachments
        exts = _requested_exts(doc)
        attachment_index = collect_attachments_for_rows(
            rows=rows,
            include_item_attachments=bool(getattr(doc, "include_item_attachments", 1)),
            include_bom_attachments=bool(getattr(doc, "include_bom_attachments", 0)),
            exts=exts,
        )

        # 3) Write child results (no parent save) + build missing summary text (db-level)
        missing_rows = update_results_and_missing_summary(package_name, doc, rows, attachment_index, exts)

        # 4) Build ZIP and attach
        zip_file_name, zip_bytes = build_zip_bytes(
            package_name=package_name,
            package_doc=doc,
            rows=rows,
            attachment_index=attachment_index,
            exts=exts,
            missing_rows=missing_rows,
        )

        saved = save_file(
            fname=zip_file_name,
            content=zip_bytes,
            dt="BOM Export Package",
            dn=package_name,
            is_private=1
        )

        frappe.db.set_value("BOM Export Package", package_name, "output_zip", saved.file_url)
        _append_log(package_name, f"[{now()}] Complete. ZIP attached: {saved.file_url}")
        _set_status(package_name, "Complete")

        sync_package_into_configuration_order(package_name)

        frappe.db.commit()
        return {"ok": True, "file_url": saved.file_url}

    except Exception:
        tb = frappe.get_traceback()
        _append_log(package_name, f"[{now()}] FAILED:\n{tb}")
        _set_status(package_name, "Failed")
        frappe.db.commit()
        raise


# -----------------------------
# Logging + Status (DB-level)
# -----------------------------

def _set_status(package_name: str, status: str):
    frappe.db.set_value("BOM Export Package", package_name, "status", status)

def _append_log(package_name: str, line: str):
    current = frappe.db.get_value("BOM Export Package", package_name, "run_log") or ""
    frappe.db.set_value("BOM Export Package", package_name, "run_log", current + "\n" + line)


# -----------------------------
# Configuration Order Sync
# -----------------------------

def sync_package_into_configuration_order(package_name: str):
    """
    Ensure the linked InductOne Configuration Order points to this package,
    and ensure a matching Document Index row exists / is updated with the ZIP URL.
    """
    pkg = frappe.get_doc("BOM Export Package", package_name)

    config_order_name = getattr(pkg, "configuration_order", None)
    if not config_order_name:
        return

    co = frappe.get_doc("InductOne Configuration Order", config_order_name)

    if hasattr(co, "bom_export_package"):
        co.bom_export_package = pkg.name

    existing_row = None
    for row in (co.documents or []):
        title = (getattr(row, "doc_title", "") or "").strip()
        notes = (getattr(row, "small_text_vtsj", "") or "").strip()
        if pkg.name in title or pkg.name in notes:
            existing_row = row
            break

    row_title = f"Configured BOM Export Package - {pkg.name}"
    row_note = f"BOM Export Package: {pkg.name} | Status: {pkg.status or 'Draft'}"

    if existing_row:
        existing_row.source_type = "BOM"
        existing_row.source_name = pkg.bom or getattr(co, "top_bom", "") or ""
        existing_row.doc_type = "OTHER"
        existing_row.doc_title = row_title
        existing_row.file_url = pkg.output_zip or ""
        existing_row.required = "YES"
        existing_row.sort_order = 300
        existing_row.small_text_vtsj = row_note
    else:
        co.append("documents", {
            "source_type": "BOM",
            "source_name": pkg.bom or getattr(co, "top_bom", "") or "",
            "doc_type": "OTHER",
            "doc_title": row_title,
            "file_url": pkg.output_zip or "",
            "required": "YES",
            "sort_order": 300,
            "small_text_vtsj": row_note
        })

    co.save(ignore_permissions=True)


# -----------------------------
# Validation
# -----------------------------

def _validate_package(doc):
    if not (doc.include_pdf or doc.include_stl or doc.include_dxf or getattr(doc, "include_step", 0)):
        frappe.throw("Select at least one file type (PDF/STL/DXF/STEP).")

    source_mode = doc.source_mode or "BOM"

    if source_mode == "Configured Build":
        if not doc.inductone_build:
            frappe.throw("Configured Build mode requires InductOne Build.")
        if not doc.configuration_order:
            frappe.throw("Configured Build mode requires Configuration Order.")
        if not doc.configured_snapshot:
            frappe.throw("Configured Build mode requires Configured Snapshot.")
        if not doc.bom:
            frappe.throw("Configured Build mode requires BOM/top BOM.")
    else:
        if not doc.bom:
            frappe.throw("BOM is required.")


def _requested_exts(doc):
    exts = []
    if doc.include_pdf:
        exts.append(".pdf")
    if doc.include_stl:
        exts.append(".stl")
    if doc.include_dxf:
        exts.append(".dxf")
    if getattr(doc, "include_step", 0):
        exts.extend([".step", ".stp"])
    return exts


# -----------------------------
# BOM Explosion
# -----------------------------

def explode_bom_tree(root_bom: str, explosion_mode: str, max_depth=None, include_qty=True):
    visited_boms = set()
    out = []

    # Normalize max_depth: 0/blank = unlimited
    if max_depth in (None, "", 0, "0"):
        max_depth = None
    else:
        max_depth = int(max_depth)

    def _walk(bom_name: str, level: int):
        # level=0 is root, level=1 is first children, etc.
        if max_depth is not None and level >= max_depth:
            return

        if bom_name in visited_boms:
            return
        visited_boms.add(bom_name)

        bom = frappe.get_doc("BOM", bom_name)

        for bi in bom.items:
            child_bom = None
            if getattr(bi, "bom_no", None):
                child_bom = bi.bom_no

            if not child_bom and explosion_mode == "Fallback to Default Active BOM":
                child_bom = frappe.db.get_value(
                    "BOM",
                    {"item": bi.item_code, "is_default": 1, "is_active": 1, "docstatus": 1},
                    "name"
                )

            out.append({
                "bom_level": level + 1,
                "item_code": bi.item_code,
                "item_name": bi.item_name,
                "qty": float(bi.qty) if include_qty else 1.0,
                "uom": bi.uom,
                "description": bi.description,
                "bom_used": child_bom,
            })

            if child_bom:
                _walk(child_bom, level + 1)

    _walk(root_bom, level=0)
    return out

def build_configured_rows(package_doc):
    """
    Build structured export rows for a configured InductOne build.

    Strategy:
      1) Start from the top BOM tree (preserves assemblies/subassemblies)
      2) Use configured snapshot included leaf lines as final truth for included leaves
      3) Keep baseline assembly rows only if they still lead to included leaves
      4) Inject additive subtrees from selected option mappings that are not present in baseline
    """
    if not package_doc.inductone_build:
        frappe.throw("Configured Build mode requires InductOne Build.")
    if not package_doc.configured_snapshot:
        frappe.throw("Configured Build mode requires Configured Snapshot.")

    build = frappe.get_doc("InductOne Build", package_doc.inductone_build)
    snap = frappe.get_doc("Configured BOM Snapshot", package_doc.configured_snapshot)

    top_bom = package_doc.bom or build.top_bom
    if not top_bom:
        frappe.throw("Configured Build mode requires BOM / top BOM.")

    baseline_rows = explode_bom_tree_structured(
        root_bom=top_bom,
        explosion_mode=package_doc.explosion_mode or "Follow Explicit Child BOM Links",
        max_depth=package_doc.max_depth,
        include_qty=bool(getattr(package_doc, "include_qty", 1)),
    )

    included_leaf_codes = {
        ln.item_code
        for ln in (snap.lines or [])
        if int(getattr(ln, "included", 0) or 0) == 1 and getattr(ln, "item_code", None)
    }

    # Keep baseline leafs that are truly included
    # Keep baseline assemblies if they have at least one included leaf descendant
    filtered = []
    for row in baseline_rows:
        if row.get("is_leaf"):
            if row["item_code"] in included_leaf_codes:
                filtered.append(row)
        else:
            descendant_leafs = set(row.get("descendant_leaf_item_codes") or [])
            if descendant_leafs.intersection(included_leaf_codes):
                filtered.append(row)

    # Additive subtrees from selected options
    selected = [r for r in (build.selections or []) if int(getattr(r, "selected", 0) or 0) == 1]
    addition_rows = build_added_structure_rows_from_selected_options(
        selected_rows=selected,
        baseline_rows=baseline_rows,
        explosion_mode=package_doc.explosion_mode or "Follow Explicit Child BOM Links",
        max_depth=package_doc.max_depth,
        include_qty=bool(getattr(package_doc, "include_qty", 1)),
    )

    # Combine + dedupe
    seen = set()
    out = []

    for row in filtered + addition_rows:
        key = (
            row.get("item_code") or "",
            row.get("bom_used") or "",
            row.get("node_type") or "",
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)

    # Stable ordering
    out.sort(key=lambda r: (
        int(r.get("bom_level") or 0),
        r.get("item_code") or "",
        r.get("bom_used") or "",
        r.get("node_type") or "",
    ))
    return out


def explode_bom_tree_structured(root_bom: str, explosion_mode: str, max_depth=None, include_qty=True):
    """
    Structured tree explosion.
    Keeps assemblies and leafs.
    Adds metadata needed for configured filtering.
    """
    visited = set()
    out = []

    if max_depth in (None, "", 0, "0"):
        max_depth = None
    else:
        max_depth = int(max_depth)

    def _walk(bom_name: str, level: int, ancestor_items=None, ancestor_boms=None):
        ancestor_items = list(ancestor_items or [])
        ancestor_boms = list(ancestor_boms or [])

        if max_depth is not None and level >= max_depth:
            return []

        visit_key = (bom_name, tuple(ancestor_items), tuple(ancestor_boms), level)
        if visit_key in visited:
            return []
        visited.add(visit_key)

        bom = frappe.get_doc("BOM", bom_name)
        subtree_leafs = []

        for bi in bom.items:
            child_bom = getattr(bi, "bom_no", None)

            if not child_bom and explosion_mode == "Fallback to Default Active BOM":
                child_bom = frappe.db.get_value(
                    "BOM",
                    {"item": bi.item_code, "is_default": 1, "is_active": 1, "docstatus": 1},
                    "name"
                )

            row = {
                "bom_level": level + 1,
                "item_code": bi.item_code,
                "item_name": bi.item_name,
                "qty": float(bi.qty) if include_qty else 1.0,
                "uom": bi.uom,
                "description": bi.description,
                "bom_used": child_bom,
                "node_type": "Assembly" if child_bom else "Leaf",
                "is_leaf": 0 if child_bom else 1,
                "ancestor_item_codes": list(ancestor_items),
                "ancestor_boms": list(ancestor_boms),
                "descendant_leaf_item_codes": [],
            }

            if child_bom:
                child_leafs = _walk(
                    child_bom,
                    level + 1,
                    ancestor_items=ancestor_items + [bi.item_code],
                    ancestor_boms=ancestor_boms + [child_bom],
                )
                row["descendant_leaf_item_codes"] = sorted(set(child_leafs))
                subtree_leafs.extend(child_leafs)
            else:
                row["descendant_leaf_item_codes"] = [bi.item_code]
                subtree_leafs.append(bi.item_code)

            out.append(row)

        return subtree_leafs

    _walk(root_bom, level=0)
    return out


def build_added_structure_rows_from_selected_options(selected_rows, baseline_rows, explosion_mode, max_depth, include_qty):
    """
    Build extra structure rows for ADD / REPLACE / QTY_OVERRIDE mappings
    that are not already present in baseline structure.
    """
    baseline_item_codes = {r.get("item_code") for r in baseline_rows if r.get("item_code")}
    out = []

    for sel in selected_rows:
        option_name = sel.option
        mappings = fetch_option_actions_server(option_name)

        for mr in mappings:
            action = (mr.get("action") or "ADD").strip()

            if action not in ("ADD", "REPLACE", "QTY_OVERRIDE"):
                continue

            target_item = mr.get("target_item")
            expand_mode = (mr.get("expand_mode") or "AS_ITEM_ONLY").strip()
            target_bom = mr.get("target_bom")

            if not target_item:
                continue

            # If already present in baseline, don't inject duplicate structure
            if target_item in baseline_item_codes:
                continue

            if expand_mode == "AS_ITEM_ONLY":
                meta = frappe.db.get_value(
                    "Item",
                    target_item,
                    ["item_name", "description", "stock_uom"],
                    as_dict=True,
                ) or {}

                out.append({
                    "bom_level": 1,
                    "item_code": target_item,
                    "item_name": meta.get("item_name") or "",
                    "qty": 1.0 if include_qty else 1.0,
                    "uom": meta.get("stock_uom") or "",
                    "description": meta.get("description") or "",
                    "bom_used": None,
                    "node_type": "Leaf",
                    "is_leaf": 1,
                    "ancestor_item_codes": [],
                    "ancestor_boms": [],
                    "descendant_leaf_item_codes": [target_item],
                })

            elif expand_mode == "EXPLODE_DEFAULT_BOM":
                default_bom = frappe.db.get_value(
                    "BOM",
                    {"item": target_item, "is_default": 1, "is_active": 1, "docstatus": 1},
                    "name"
                )
                if not default_bom:
                    continue

                meta = frappe.db.get_value(
                    "Item",
                    target_item,
                    ["item_name", "description", "stock_uom"],
                    as_dict=True,
                ) or {}

                out.append({
                    "bom_level": 1,
                    "item_code": target_item,
                    "item_name": meta.get("item_name") or "",
                    "qty": 1.0 if include_qty else 1.0,
                    "uom": meta.get("stock_uom") or "",
                    "description": meta.get("description") or "",
                    "bom_used": default_bom,
                    "node_type": "Assembly",
                    "is_leaf": 0,
                    "ancestor_item_codes": [],
                    "ancestor_boms": [],
                    "descendant_leaf_item_codes": [],
                })

                subtree = explode_bom_tree_structured(
                    root_bom=default_bom,
                    explosion_mode=explosion_mode,
                    max_depth=max_depth,
                    include_qty=include_qty,
                )
                out.extend(subtree)

            elif expand_mode == "USE_TARGET_BOM" and target_bom:
                meta = frappe.db.get_value(
                    "Item",
                    target_item,
                    ["item_name", "description", "stock_uom"],
                    as_dict=True,
                ) or {}

                out.append({
                    "bom_level": 1,
                    "item_code": target_item,
                    "item_name": meta.get("item_name") or "",
                    "qty": 1.0 if include_qty else 1.0,
                    "uom": meta.get("stock_uom") or "",
                    "description": meta.get("description") or "",
                    "bom_used": target_bom,
                    "node_type": "Assembly",
                    "is_leaf": 0,
                    "ancestor_item_codes": [],
                    "ancestor_boms": [],
                    "descendant_leaf_item_codes": [],
                })

                subtree = explode_bom_tree_structured(
                    root_bom=target_bom,
                    explosion_mode=explosion_mode,
                    max_depth=max_depth,
                    include_qty=include_qty,
                )
                out.extend(subtree)

    return out


def fetch_option_actions_server(option_name):
    doc = frappe.get_doc("InductOne Configuration Option", option_name)
    out = []
    for row in (doc.mappings_table or []):
        out.append({
            "action": getattr(row, "action", None),
            "target_item": getattr(row, "target_item", None),
            "target_bom": getattr(row, "target_bom", None),
            "expand_mode": getattr(row, "expand_mode", None),
            "qty_source": getattr(row, "qty_source", None),
            "qty_fixed": getattr(row, "qty_fixed", None),
        })
    return out


# -----------------------------
# Attachment Collection
# -----------------------------

def collect_attachments_for_rows(rows, include_item_attachments: bool, include_bom_attachments: bool, exts):
    """
    Index:
      key: ("Item", item_code) or ("BOM", bom_name)
      value: dict { ".pdf": FileRow, ".stl": FileRow, ".dxf": FileRow } (latest per ext)
    """
    idx = {}

    def _pick_latest(files):
        files_sorted = sorted(
            files,
            key=lambda f: (f.get("modified") or "", f.get("creation") or ""),
            reverse=True
        )
        return files_sorted[0] if files_sorted else None

    if include_item_attachments:
        item_codes = sorted(set(r["item_code"] for r in rows if r.get("item_code")))
        for ext in exts:
            like = f"%{ext}"
            files = frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": "Item",
                    "attached_to_name": ["in", item_codes],
                    "is_folder": 0,
                    "file_url": ["like", like],
                },
                fields=["name", "attached_to_name", "file_name", "file_url", "is_private", "modified", "creation"]
            )
            grouped = {}
            for f in files:
                grouped.setdefault(f["attached_to_name"], []).append(f)
            for item_code, flist in grouped.items():
                latest = _pick_latest(flist)
                if latest:
                    idx.setdefault(("Item", item_code), {})[ext] = latest

    if include_bom_attachments:
        bom_names = sorted(set(r["bom_used"] for r in rows if r.get("bom_used")))
        for ext in exts:
            like = f"%{ext}"
            files = frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": "BOM",
                    "attached_to_name": ["in", bom_names],
                    "is_folder": 0,
                    "file_url": ["like", like],
                },
                fields=["name", "attached_to_name", "file_name", "file_url", "is_private", "modified", "creation"]
            )
            grouped = {}
            for f in files:
                grouped.setdefault(f["attached_to_name"], []).append(f)
            for bom_name, flist in grouped.items():
                latest = _pick_latest(flist)
                if latest:
                    idx.setdefault(("BOM", bom_name), {})[ext] = latest

    return idx


def resolve_file_path(file_url: str):
    if not file_url:
        return None

    if "://" in file_url:
        parsed = urlparse(file_url)
        file_url = parsed.path

    if file_url.startswith("/private/files/"):
        rel = file_url.replace("/private/files/", "")
        return frappe.get_site_path("private", "files", rel)

    if file_url.startswith("/files/"):
        rel = file_url.replace("/files/", "")
        return frappe.get_site_path("public", "files", rel)

    if file_url.startswith("private/files/"):
        rel = file_url.replace("private/files/", "")
        return frappe.get_site_path("private", "files", rel)

    if file_url.startswith("files/"):
        rel = file_url.replace("files/", "")
        return frappe.get_site_path("public", "files", rel)

    return None


# -----------------------------
# Results + Missing Summary (NO parent save)
# -----------------------------

def _clear_results_table(package_doc):
    """
    Clear child table rows without saving parent doc.
    """
    field = package_doc.meta.get_field("results")
    if not field:
        return
    child_doctype = field.options
    if not child_doctype:
        return

    frappe.db.delete(child_doctype, {
        "parent": package_doc.name,
        "parenttype": package_doc.doctype,
        "parentfield": "results",
    })

def update_results_and_missing_summary(package_name, package_doc, rows, attachment_index, exts):
    """
    Inserts child rows directly (no parent save) and sets missing summary via db.set_value.
    Returns missing_rows for ZIP CSV.
    """
    missing_rows = []

    field = package_doc.meta.get_field("results")
    child_doctype = field.options if field and field.options else None

    idx_counter = 1

    for r in rows:
        item_key = ("Item", r["item_code"])
        bom_key = ("BOM", r["bom_used"]) if r.get("bom_used") else None

        per_item = attachment_index.get(item_key, {})
        per_bom = attachment_index.get(bom_key, {}) if bom_key else {}

        availability = {}
        for ext in exts:
            availability[ext] = bool(per_item.get(ext) or per_bom.get(ext))

        for ext in exts:
            if not availability[ext]:
                missing_rows.append({
                    "item_code": r["item_code"],
                    "item_name": r.get("item_name"),
                    "bom_used": r.get("bom_used"),
                    "bom_level": r.get("bom_level"),
                    "node_type": r.get("node_type"),
                    "ext": ext
                })

        if child_doctype:
            child = frappe.get_doc({
                "doctype": child_doctype,
                "parent": package_doc.name,
                "parenttype": package_doc.doctype,
                "parentfield": "results",
                "idx": idx_counter,
                "item_code": r["item_code"],
                "item_name": r.get("item_name"),
                "bom_used": r.get("bom_used"),
                "bom_level": r.get("bom_level"),
                "qty": r.get("qty"),
                "has_pdf": 1 if availability.get(".pdf") else 0,
                "has_stl": 1 if availability.get(".stl") else 0,
                "has_dxf": 1 if availability.get(".dxf") else 0,
                "has_step": 1 if (availability.get(".step") or availability.get(".stp")) else 0,
            })
            child.insert(ignore_permissions=True)
            idx_counter += 1

    # Build missing summary text
    if missing_rows:
        lines = [f"Missing files: {len(missing_rows)}"]
        for m in missing_rows[:50]:
            lines.append(f"- {m['item_code']} ({m['ext']}) level={m['bom_level']} bom={m.get('bom_used') or ''}")
        if len(missing_rows) > 50:
            lines.append(f"... and {len(missing_rows) - 50} more")
        summary = "\n".join(lines)
    else:
        summary = "No missing files detected for selected extensions."

    frappe.db.set_value("BOM Export Package", package_name, "missing_files_summary", summary)
    return missing_rows


# -----------------------------
# ZIP Build (NO doc mutation)
# -----------------------------

def build_zip_bytes(package_name, package_doc, rows, attachment_index, exts, missing_rows):
    bom_safe = (package_doc.bom or "BOM").replace("/", "_")
    zip_name = f"{bom_safe}_export_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.zip"

    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for r in rows:
            item_code = r["item_code"]
            item_key = ("Item", item_code)
            bom_key = ("BOM", r["bom_used"]) if r.get("bom_used") else None

            per_item = attachment_index.get(item_key, {})
            per_bom = attachment_index.get(bom_key, {}) if bom_key else {}

            for ext in exts:
                f = per_item.get(ext) or per_bom.get(ext)
                if not f:
                    continue

                file_url = f.get("file_url")
                abs_path = resolve_file_path(file_url)

                if not abs_path or not os.path.exists(abs_path):
                    _append_log(package_name, f"[{now()}] WARN: file not found on disk: {file_url}")
                    continue

                original_name = f.get("file_name") or os.path.basename(abs_path)
                folder = "STEP" if ext.lower() in (".step", ".stp") else ext.lstrip('.').upper()
                zip_path = f"{folder}/{item_code}/{original_name}"

                # Watermark PDFs in-memory before zipping (do not modify source files)
                if ext.lower() == ".pdf":
                    try:
                        pdf_bytes = _read_file_bytes(abs_path)
                        wm_text = _watermark_text(package_doc)
                        wm_bytes = watermark_pdf_bytes(pdf_bytes, wm_text)
                        zf.writestr(zip_path, wm_bytes)
                    except Exception:
                        _append_log(package_name, f"[{now()}] WARN: watermark failed for {file_url}; added original. {frappe.get_traceback()}")
                        zf.write(abs_path, zip_path)
                else:
                    zf.write(abs_path, zip_path)

        zf.writestr("missing_files.csv", _missing_csv_bytes(missing_rows))
        zf.writestr("results.csv", _results_csv_bytes(
            rows=rows,
            attachment_index=attachment_index,
            exts=exts
        ))
        zf.writestr("manifest.txt", _manifest_text(package_doc, rows, exts, missing_rows))

    buf.seek(0)
    return zip_name, buf.read()


# -----------------------------
# PDF Watermark Helpers (in-memory)
# -----------------------------

def _read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def _watermark_text(package_doc) -> str:
    ts = frappe.utils.now()
    return f"SNAPSHOT EXPORT • {ts} • {package_doc.name} • Source: ERPNext"

def watermark_pdf_bytes(input_pdf_bytes: bytes, watermark_text: str) -> bytes:
    """
    Returns a new PDF (bytes) that has watermark_text stamped on every page.
    Does NOT modify the original file on disk.
    """
    if not (canvas and inch and PdfReader and PdfWriter):
        raise RuntimeError("PDF watermark dependencies not available (reportlab/pypdf).")

    reader = PdfReader(io.BytesIO(input_pdf_bytes))
    writer = PdfWriter()

    for page in reader.pages:
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)

        wm_pdf_bytes = _make_watermark_page_pdf(w, h, watermark_text)
        wm_reader = PdfReader(io.BytesIO(wm_pdf_bytes))
        wm_page = wm_reader.pages[0]

        page.merge_page(wm_page)
        writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()

def _make_watermark_page_pdf(page_width: float, page_height: float, text: str) -> bytes:
    """
    Creates a single-page PDF containing the watermark text, sized to the target page.
    This page is merged over each target page.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))

    # Bottom-right footer stamp (readable, low obstruction)
    c.setFont("Helvetica", 9)
    x = page_width - 0.5 * inch
    y = 0.35 * inch
    c.drawRightString(x, y, text)

    c.save()
    return buf.getvalue()


def _results_csv_bytes(rows, attachment_index, exts):
    out = io.StringIO()
    w = csv.writer(out)

    headers = ["bom_level", "node_type", "item_code", "item_name", "qty", "uom", "bom_used"]
    headers += [f"has_{ext.lstrip('.')}" for ext in exts]
    w.writerow(headers)

    for r in rows:
        item_key = ("Item", r["item_code"])
        bom_key = ("BOM", r["bom_used"]) if r.get("bom_used") else None

        per_item = attachment_index.get(item_key, {})
        per_bom = attachment_index.get(bom_key, {}) if bom_key else {}

        avail = []
        for ext in exts:
            avail.append(1 if (per_item.get(ext) or per_bom.get(ext)) else 0)

        w.writerow([
            r.get("bom_level"),
            r.get("node_type"),
            r.get("item_code"),
            r.get("item_name"),
            r.get("qty"),
            r.get("uom"),
            r.get("bom_used"),
            *avail
        ])

    return out.getvalue().encode("utf-8")


def _missing_csv_bytes(missing_rows):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["item_code", "item_name", "bom_used", "bom_level", "missing_ext"])
    for m in missing_rows:
        writer.writerow([
            m["item_code"],
            m.get("item_name") or "",
            m.get("bom_used") or "",
            m.get("bom_level") or "",
            m.get("ext") or ""
        ])
    return out.getvalue().encode("utf-8")


def _manifest_text(doc, rows, exts, missing_rows):
    lines = [
        f"BOM Export Package: {doc.name}",
        f"Root BOM: {doc.bom}",
        f"Extensions: {', '.join(exts)}",
        f"Total exploded rows: {len(rows)}",
        f"Missing entries: {len(missing_rows)}",
        f"Generated: {frappe.utils.now()}",
    ]
    return "\n".join(lines)