import csv
import io
import os
import re
import zipfile
from urllib.parse import urlparse

import frappe
from frappe.utils import now, now_datetime
from frappe.utils.file_manager import save_file


@frappe.whitelist()
def generate_configured_export_now(config_order_name: str):
    """
    Build a configuration-specific export ZIP from:
      - InductOne Configuration Order
      - linked Configured BOM Snapshot
      - Configuration Order document index rows
      - attached Flat BOM CSV (if present)

    Output ZIP is attached back to the Configuration Order.
    """

    if not config_order_name:
        frappe.throw("config_order_name is required.")

    co = frappe.get_doc("InductOne Configuration Order", config_order_name)

    _set_status(co.name, "Running", error="")
    frappe.db.set_value("InductOne Configuration Order", co.name, {
        "configured_export_zip": None,
        "configured_export_generated_at": None,
    })
    frappe.db.commit()

    try:
        if not co.snapshot:
            raise frappe.ValidationError("Configuration Order has no linked snapshot.")

        snap = frappe.get_doc("Configured BOM Snapshot", co.snapshot)
        included_items = _get_included_snapshot_items(snap)
        indexed_docs, missing_docs = _collect_config_order_documents(co)
        flat_bom_file = _find_flat_bom_attachment(co)

        zip_name, zip_bytes = _build_configured_export_zip(
            co=co,
            snap=snap,
            included_items=included_items,
            indexed_docs=indexed_docs,
            missing_docs=missing_docs,
            flat_bom_file=flat_bom_file,
        )

        saved = save_file(
            fname=zip_name,
            content=zip_bytes,
            dt="InductOne Configuration Order",
            dn=co.name,
            is_private=1,
        )

        frappe.db.set_value("InductOne Configuration Order", co.name, {
            "configured_export_status": "Complete",
            "configured_export_zip": saved.file_url,
            "configured_export_generated_at": now_datetime(),
            "configured_export_error": "",
        })

        # Optional but useful: append export ZIP itself into the document index
        _append_generated_zip_to_document_index_if_missing(co.name, saved.file_url, zip_name)

        frappe.db.commit()
        return {
            "ok": True,
            "config_order": co.name,
            "file_url": saved.file_url,
            "zip_name": zip_name,
            "included_item_count": len(included_items),
            "document_count": len(indexed_docs),
            "missing_document_count": len(missing_docs),
        }

    except Exception:
        tb = frappe.get_traceback()
        frappe.db.set_value("InductOne Configuration Order", co.name, {
            "configured_export_status": "Failed",
            "configured_export_error": tb,
        })
        frappe.db.commit()
        raise


def _set_status(config_order_name: str, status: str, error: str = ""):
    frappe.db.set_value("InductOne Configuration Order", config_order_name, {
        "configured_export_status": status,
        "configured_export_error": error or "",
    })


def _get_included_snapshot_items(snapshot_doc):
    """
    Returns normalized rows for included snapshot items only.
    Expects snapshot_doc.lines child table with included flag.
    """
    out = []

    for ln in (snapshot_doc.lines or []):
        included = int(getattr(ln, "included", 0) or 0)
        if included != 1:
            continue

        out.append({
            "item_code": getattr(ln, "item_code", "") or "",
            "item_name": getattr(ln, "item_name", "") or "",
            "description": getattr(ln, "description", "") or "",
            "uom": getattr(ln, "uom", "") or "",
            "qty": getattr(ln, "qty", 0) or 0,
        })

    out.sort(key=lambda r: (r["item_code"], str(r["uom"])))
    return out


def _collect_config_order_documents(co):
    """
    Reads co.documents child table and normalizes file-backed rows.
    Returns:
      indexed_docs: usable docs with resolvable file paths
      missing_docs: rows missing file/file_url or missing file on disk
    """
    indexed_docs = []
    missing_docs = []

    for row in (co.documents or []):
        file_url = (getattr(row, "file", None) or getattr(row, "file_url", None) or "").strip()

        doc = {
            "sort_order": int(getattr(row, "sort_order", 100) or 100),
            "source_type": getattr(row, "source_type", "") or "",
            "source_name": getattr(row, "source_name", "") or "",
            "doc_type": getattr(row, "doc_type", "") or "",
            "doc_title": getattr(row, "doc_title", "") or "Untitled Document",
            "required": getattr(row, "required", "") or "",
            "notes": getattr(row, "small_text_vtsj", "") or "",
            "file_url": file_url,
            "abs_path": None,
            "file_name": None,
        }

        if not file_url:
            missing_docs.append({
                **doc,
                "reason": "No file or file_url on document index row",
            })
            continue

        abs_path = _resolve_file_path(file_url)
        if not abs_path or not os.path.exists(abs_path):
            missing_docs.append({
                **doc,
                "reason": f"File not found on disk for {file_url}",
            })
            continue

        doc["abs_path"] = abs_path
        doc["file_name"] = os.path.basename(abs_path)
        indexed_docs.append(doc)

    indexed_docs.sort(key=lambda d: (d["sort_order"], d["doc_type"], d["doc_title"]))
    missing_docs.sort(key=lambda d: (d["sort_order"], d["doc_type"], d["doc_title"]))
    return indexed_docs, missing_docs


def _find_flat_bom_attachment(co):
    """
    Find attached File row for the generated flat BOM CSV.
    Does NOT rely on a flat_bom_csv field existing on the doctype.
    """
    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "InductOne Configuration Order",
            "attached_to_name": co.name,
            "is_folder": 0,
        },
        fields=["name", "file_name", "file_url", "is_private", "modified", "creation"],
        order_by="modified desc",
    )

    for f in files:
        fname = (f.get("file_name") or "").lower()
        furl = (f.get("file_url") or "").lower()

        if fname.endswith(".csv") and "flat_bom" in fname:
            abs_path = _resolve_file_path(f.get("file_url"))
            if abs_path and os.path.exists(abs_path):
                f["abs_path"] = abs_path
                return f

        if furl.endswith(".csv") and "flat_bom" in furl:
            abs_path = _resolve_file_path(f.get("file_url"))
            if abs_path and os.path.exists(abs_path):
                f["abs_path"] = abs_path
                return f

    return None


def _build_configured_export_zip(co, snap, included_items, indexed_docs, missing_docs, flat_bom_file):
    """
    Build the configuration-specific ZIP bytes.
    """
    buf = io.BytesIO()
    zip_name = f"{_safe_name(co.name)}_Configured_Export_{now_datetime().strftime('%Y%m%d_%H%M%S')}.zip"

    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Core metadata files
        zf.writestr("manifest.txt", _manifest_text(co, snap, included_items, indexed_docs, missing_docs, flat_bom_file))
        zf.writestr("included_items.csv", _included_items_csv_bytes(included_items))
        zf.writestr("document_index.csv", _document_index_csv_bytes(indexed_docs))
        zf.writestr("missing_files.csv", _missing_files_csv_bytes(missing_docs))

        # Flat BOM
        if flat_bom_file:
            zf.write(
                flat_bom_file["abs_path"],
                f"Flat_BOM/{os.path.basename(flat_bom_file['abs_path'])}"
            )

        # Indexed docs
        for doc in indexed_docs:
            ext = os.path.splitext(doc["file_name"])[1] or ""
            safe_title = _safe_name(doc["doc_title"])
            safe_type = _safe_name(doc["doc_type"] or "OTHER")
            zip_file_name = f"{doc['sort_order']:04d}_{safe_type}_{safe_title}{ext}"
            zip_path = f"Documents/{zip_file_name}"
            zf.write(doc["abs_path"], zip_path)

    buf.seek(0)
    return zip_name, buf.read()


def _append_generated_zip_to_document_index_if_missing(config_order_name: str, file_url: str, zip_name: str):
    """
    Append generated ZIP to the document index if not already present.
    """
    co = frappe.get_doc("InductOne Configuration Order", config_order_name)

    for row in (co.documents or []):
        existing = (getattr(row, "file", None) or getattr(row, "file_url", None) or "").strip()
        if existing == file_url:
            return

    max_sort = 0
    for row in (co.documents or []):
        try:
            max_sort = max(max_sort, int(getattr(row, "sort_order", 0) or 0))
        except Exception:
            pass

    co.append("documents", {
        "source_type": "MANUAL",
        "source_name": co.name,
        "doc_type": "OTHER",
        "doc_title": "Configured Export Package",
        "file": file_url,
        "file_url": file_url,
        "required": "NO",
        "sort_order": max_sort + 100 if max_sort else 9999,
        "small_text_vtsj": f"Auto-generated ZIP package: {zip_name}",
    })

    co.save(ignore_permissions=True)


def _resolve_file_path(file_url: str):
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


def _included_items_csv_bytes(rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["item_code", "item_name", "description", "qty", "uom"])
    for r in rows:
        w.writerow([
            r.get("item_code", ""),
            r.get("item_name", ""),
            r.get("description", ""),
            r.get("qty", ""),
            r.get("uom", ""),
        ])
    return out.getvalue().encode("utf-8")


def _document_index_csv_bytes(rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([
        "sort_order",
        "source_type",
        "source_name",
        "doc_type",
        "doc_title",
        "required",
        "file_url",
        "notes",
    ])
    for r in rows:
        w.writerow([
            r.get("sort_order", ""),
            r.get("source_type", ""),
            r.get("source_name", ""),
            r.get("doc_type", ""),
            r.get("doc_title", ""),
            r.get("required", ""),
            r.get("file_url", ""),
            r.get("notes", ""),
        ])
    return out.getvalue().encode("utf-8")


def _missing_files_csv_bytes(rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([
        "sort_order",
        "source_type",
        "source_name",
        "doc_type",
        "doc_title",
        "required",
        "file_url",
        "reason",
    ])
    for r in rows:
        w.writerow([
            r.get("sort_order", ""),
            r.get("source_type", ""),
            r.get("source_name", ""),
            r.get("doc_type", ""),
            r.get("doc_title", ""),
            r.get("required", ""),
            r.get("file_url", ""),
            r.get("reason", ""),
        ])
    return out.getvalue().encode("utf-8")


def _manifest_text(co, snap, included_items, indexed_docs, missing_docs, flat_bom_file):
    lines = [
        f"Configuration Order: {co.name}",
        f"Snapshot: {snap.name}",
        f"InductOne Build: {getattr(co, 'inductone_build', '')}",
        f"Sales Order: {getattr(co, 'sales_order', '')}",
        f"Builder Supplier: {getattr(co, 'builder_supplier', '')}",
        f"Orientation: {getattr(co, 'orientation', '')}",
        f"Generated At: {now()}",
        f"Included Snapshot Items: {len(included_items)}",
        f"Indexed Documents Included: {len(indexed_docs)}",
        f"Indexed Documents Missing: {len(missing_docs)}",
        f"Flat BOM CSV Included: {'YES' if flat_bom_file else 'NO'}",
    ]
    return "\n".join(lines)


def _safe_name(value: str):
    value = value or ""
    value = re.sub(r"[^\w\-. ]+", "_", value)
    value = value.strip().replace(" ", "_")
    return value[:180] if value else "unnamed"