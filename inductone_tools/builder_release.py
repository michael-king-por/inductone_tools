import os
import csv
import io
import zipfile

import frappe
from frappe.utils import now
from frappe.utils.file_manager import save_file

from .bom_export import build_configured_rows, resolve_file_path


@frappe.whitelist()
def generate_builder_release_bundle(build_name: str, package_name: str = None):
    """
    Build one builder-facing ZIP bundle from the current InductOne Build context.

    This is intentionally light on gatekeeping for now. It assumes the user has
    manually prepared / approved the release basis and wants a releasable package.
    """
    build = frappe.get_doc("InductOne Build", build_name)

    co_name = _resolve_configuration_order_name(build)
    snapshot_name = _resolve_snapshot_name(build)
    top_bom = getattr(build, "top_bom", None) or getattr(build, "bom", None)

    if not co_name:
        frappe.throw("InductOne Build must have a linked Configuration Order to generate a builder release bundle.")

    if not snapshot_name:
        frappe.throw("InductOne Build must have a selected/latest snapshot to generate a builder release bundle.")

    if not top_bom:
        frappe.throw("InductOne Build must have Top BOM to generate a builder release bundle.")

    co = frappe.get_doc("InductOne Configuration Order", co_name)

    package_doc = None
    if package_name:
        package_doc = frappe.get_doc("BOM Export Package", package_name)
    else:
        resolved_package_name = _resolve_bom_export_package_name(build, co)
        if resolved_package_name:
            package_doc = frappe.get_doc("BOM Export Package", resolved_package_name)

    flat_bom_file_url = _resolve_flat_bom_file_url(build, co)

    bundle_name, bundle_bytes, manifest = _build_builder_release_bundle_bytes(
        build=build,
        configuration_order=co,
        package_doc=package_doc,
        flat_bom_file_url=flat_bom_file_url,
        snapshot_name=snapshot_name,
        top_bom=top_bom,
    )

    saved = save_file(
        fname=bundle_name,
        content=bundle_bytes,
        dt="InductOne Build",
        dn=build.name,
        is_private=1,
    )

    _set_if_present(build, ["builder_release_bundle", "builder_package", "released_builder_package"], saved.file_url)
    _set_if_present(build, ["builder_release_manifest_json"], frappe.as_json(manifest))
    _set_if_present(build, ["builder_release_generated_at", "builder_package_generated_at"], now())
    _set_if_present(build, ["builder_release_status"], "Prepared")
    build.save(ignore_permissions=True)

    _sync_builder_release_document_index(
        configuration_order_name=co.name,
        build_name=build.name,
        bundle_url=saved.file_url,
        package_name=package_doc.name if package_doc else None,
        flat_bom_file_url=flat_bom_file_url,
    )

    return {
        "ok": True,
        "build": build.name,
        "configuration_order": co.name,
        "bundle_file_url": saved.file_url,
        "package_name": package_doc.name if package_doc else None,
        "flat_bom_file_url": flat_bom_file_url,
        "manifest": manifest,
    }


@frappe.whitelist()
def release_to_builder_now(build_name: str, package_name: str = None, note: str = None):
    """
    Minimal operational release action.
    - Generates the unified builder bundle
    - Generates/refreshes required serial capture template
    - Stamps the user's actual release fields
    - Updates Configuration Order document index with the builder release bundle

    This does NOT add hard gatekeeping yet.
    """
    result = generate_builder_release_bundle(build_name=build_name, package_name=package_name)

    # Keep serial template generation in place so the release bundle remains useful later.
    try:
        serial_result = generate_required_serial_capture_artifact(build_name)
    except Exception:
        serial_result = {"template_file_url": None}

    build = frappe.get_doc("InductOne Build", build_name)

    # Stamp the actual fields used by the current build doctype/client flow.
    _set_if_present(build, ["build_status"], "RELEASED_TO_BUILDER")
    _set_if_present(build, ["released_at"], frappe.utils.now_datetime())
    _set_if_present(build, ["released_by"], frappe.session.user)

    # Optional helper fields if they exist
    _set_if_present(build, ["builder_release_status"], "Released")
    _set_if_present(build, ["builder_released_on", "released_to_builder_at"], frappe.utils.now_datetime())
    _set_if_present(build, ["builder_released_by", "released_to_builder_by"], frappe.session.user)
    _set_if_present(build, ["builder_release_note", "builder_release_notes"], note or "")
    _set_if_present(build, ["as_built_status"], "Pending Builder Submission")

    build.save(ignore_permissions=True)

    return {
        "ok": True,
        "build": build.name,
        "bundle_file_url": result.get("bundle_file_url"),
        "serial_template_file_url": serial_result.get("template_file_url"),
        "released_at": getattr(build, "released_at", None),
        "released_by": getattr(build, "released_by", None),
    }


@frappe.whitelist()
def generate_required_serial_capture_artifact(build_name: str):
    """
    Generate a CSV template listing the configured rows that likely require serial capture.
    This is retained for later completion workflow, but it is not required to expose a button now.
    """
    build = frappe.get_doc("InductOne Build", build_name)
    rows = _get_configured_rows_for_build(build)
    required_rows = _derive_required_serial_capture_rows(rows)

    _sync_required_serial_capture_table(build, required_rows)

    csv_bytes = _required_serial_capture_csv_bytes(required_rows)
    fname = f"{build.name}_required_serial_capture_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.csv"
    saved = save_file(
        fname=fname,
        content=csv_bytes,
        dt="InductOne Build",
        dn=build.name,
        is_private=1,
    )

    _set_if_present(build, ["required_serial_capture_file", "builder_serial_template", "serial_capture_template_file"], saved.file_url)
    _set_if_present(build, ["required_serial_capture_generated_at", "serial_capture_template_generated_at"], now())
    build.save(ignore_permissions=True)

    co_name = _resolve_configuration_order_name(build)
    if co_name:
        _append_or_update_document_index_row(
            parent_doctype="InductOne Configuration Order",
            parent_name=co_name,
            title=f"Builder Serial Capture Template - {build.name}",
            file_url=saved.file_url,
            source_type="BUILD",
            source_name=build.name,
            sort_order=320,
            note=f"Required serial capture template for build {build.name}",
        )

    return {
        "ok": True,
        "build": build.name,
        "required_serial_rows": len(required_rows),
        "template_file_url": saved.file_url,
    }


@frappe.whitelist()
def submit_as_built_now(build_name: str, serials_json: str = None, note: str = None):
    """
    Minimal as-built submission endpoint.
    Kept in place for later closeout work.
    """
    build = frappe.get_doc("InductOne Build", build_name)
    rows = []
    if serials_json:
        rows = frappe.parse_json(serials_json) or []

    _sync_as_built_serial_capture_table(build, rows)

    if rows:
        csv_bytes = _as_built_serial_capture_csv_bytes(rows)
        fname = f"{build.name}_as_built_serial_capture_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.csv"
        saved = save_file(
            fname=fname,
            content=csv_bytes,
            dt="InductOne Build",
            dn=build.name,
            is_private=1,
        )
        _set_if_present(build, ["as_built_serial_capture_file", "as_built_serials_file"], saved.file_url)

    _set_if_present(build, ["as_built_status"], "Submitted")
    _set_if_present(build, ["builder_completion_note", "as_built_note", "as_built_notes"], note or "")
    _set_if_present(build, ["builder_completed_on", "as_built_submitted_on"], now())
    _set_if_present(build, ["builder_completed_by", "as_built_submitted_by"], frappe.session.user)
    build.save(ignore_permissions=True)

    return {"ok": True, "build": build.name, "submitted_rows": len(rows)}


@frappe.whitelist()
def close_build_from_as_built(build_name: str, note: str = None):
    """
    Minimal close action after manual review.
    Kept in place for later closeout work.
    """
    build = frappe.get_doc("InductOne Build", build_name)

    _set_if_present(build, ["as_built_status"], "Accepted")
    _set_if_present(build, ["build_closed_on", "closed_on", "completed_on"], now())
    _set_if_present(build, ["build_closed_by", "closed_by", "completed_by"], frappe.session.user)
    _set_if_present(build, ["closure_note", "close_note", "completion_note"], note or "")

    build.save(ignore_permissions=True)
    return {"ok": True, "build": build.name}


def _build_builder_release_bundle_bytes(build, configuration_order, package_doc, flat_bom_file_url, snapshot_name, top_bom):
    bundle_name = f"{build.name}_builder_release_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.zip"
    manifest = {
        "build": build.name,
        "configuration_order": configuration_order.name,
        "configured_snapshot": snapshot_name,
        "top_bom": top_bom,
        "bom_export_package": package_doc.name if package_doc else None,
        "flat_bom_file_url": flat_bom_file_url,
        "generated": now(),
        "contents": [],
        "missing": [],
    }

    serial_rows = _derive_required_serial_capture_rows(_get_configured_rows_for_build(build))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        cover_text = _builder_release_cover_text(
            build,
            configuration_order,
            package_doc,
            flat_bom_file_url,
            snapshot_name,
            top_bom,
            serial_rows,
        )
        zf.writestr("builder_release_cover.txt", cover_text)
        manifest["contents"].append({"path": "builder_release_cover.txt", "kind": "cover"})

        # Configuration Order PDF
        try:
            co_pdf = frappe.get_print("InductOne Configuration Order", configuration_order.name, as_pdf=True)
            zf.writestr(f"configuration_order/{configuration_order.name}.pdf", co_pdf)
            manifest["contents"].append({
                "path": f"configuration_order/{configuration_order.name}.pdf",
                "kind": "configuration_order_pdf"
            })
        except Exception:
            manifest["missing"].append({
                "kind": "configuration_order_pdf",
                "reason": "print_failed",
                "detail": frappe.get_traceback()
            })

        # Flat BOM CSV
        if flat_bom_file_url:
            _add_file_url_to_zip(
                zf,
                flat_bom_file_url,
                f"builder_bom/{os.path.basename(resolve_file_path(flat_bom_file_url) or flat_bom_file_url)}",
                manifest,
                "flat_bom"
            )
        else:
            manifest["missing"].append({"kind": "flat_bom", "reason": "not_found"})

        # BOM Export Package ZIP
        if package_doc and getattr(package_doc, "output_zip", None):
            zip_dest = f"bom_export/{os.path.basename(resolve_file_path(package_doc.output_zip) or package_doc.output_zip)}"
            _add_file_url_to_zip(zf, package_doc.output_zip, zip_dest, manifest, "bom_export_package")
        else:
            manifest["missing"].append({"kind": "bom_export_package", "reason": "not_found"})

        # Current Configuration Order linked documents
        for docrow in (getattr(configuration_order, "documents", None) or []):
            f_url = getattr(docrow, "file_url", None) or getattr(docrow, "file", None)
            if not f_url:
                continue
            title = (getattr(docrow, "doc_title", None) or "document").strip()
            safe_title = frappe.scrub(title).replace("-", "_") or "document"
            dest = f"configuration_order_documents/{safe_title}/{os.path.basename(resolve_file_path(f_url) or f_url)}"
            _add_file_url_to_zip(zf, f_url, dest, manifest, "configuration_order_document", allow_missing=True)

        # Serial capture template
        zf.writestr("serial_capture/required_serial_capture.csv", _required_serial_capture_csv_bytes(serial_rows))
        manifest["contents"].append({
            "path": "serial_capture/required_serial_capture.csv",
            "kind": "required_serial_capture"
        })

        # Final manifest
        zf.writestr("builder_release_manifest.json", frappe.as_json(manifest, indent=2))

    buf.seek(0)
    return bundle_name, buf.read(), manifest


def _builder_release_cover_text(build, configuration_order, package_doc, flat_bom_file_url, snapshot_name, top_bom, serial_rows):
    lines = [
        "INDUCTONE BUILDER RELEASE PACKAGE",
        "",
        f"Build: {build.name}",
        f"Configuration Order: {configuration_order.name}",
        f"Configured Snapshot: {snapshot_name or ''}",
        f"Top BOM: {top_bom or ''}",
        f"BOM Export Package: {package_doc.name if package_doc else ''}",
        f"BOM Export ZIP: {getattr(package_doc, 'output_zip', '') if package_doc else ''}",
        f"Flat BOM CSV: {flat_bom_file_url or ''}",
        f"Generated: {now()}",
        "",
        "Included package intent:",
        "- Configuration Order PDF (best effort)",
        "- Current Configuration Order linked documents",
        "- Configured BOM export package ZIP",
        "- Flat configured BOM CSV",
        "- Required serial capture CSV template",
        "",
        "Builder completion expectations:",
        "- Build to the released package basis unless a deviation is explicitly approved.",
        "- Return installed serials / vendor serials / POR serials as applicable.",
        "- Return completion evidence and note any deviations or substitutions.",
        "",
        f"Serial capture rows in template: {len(serial_rows)}",
    ]
    return "\n".join(lines)


def _add_file_url_to_zip(zf, file_url, zip_path, manifest, kind, allow_missing=False):
    abs_path = resolve_file_path(file_url)
    if not abs_path or not os.path.exists(abs_path):
        manifest["missing"].append({
            "kind": kind,
            "file_url": file_url,
            "zip_path": zip_path,
            "reason": "not_found_on_disk"
        })
        return

    zf.write(abs_path, zip_path)
    manifest["contents"].append({
        "path": zip_path,
        "kind": kind,
        "file_url": file_url
    })


def _resolve_configuration_order_name(build_doc):
    return (
        getattr(build_doc, "latest_config_order", None)
        or getattr(build_doc, "configuration_order", None)
        or getattr(build_doc, "inductone_configuration_order", None)
    )


def _resolve_snapshot_name(build_doc):
    return (
        getattr(build_doc, "selected_snapshot", None)
        or getattr(build_doc, "latest_snapshot", None)
        or getattr(build_doc, "configured_snapshot", None)
        or getattr(build_doc, "configured_bom_snapshot", None)
    )


def _resolve_bom_export_package_name(build, configuration_order):
    candidates = [
        getattr(build, "latest_bom_export_package", None),
        getattr(build, "bom_export_package", None),
        getattr(build, "export_package", None),
        getattr(configuration_order, "bom_export_package", None),
    ]

    for c in candidates:
        if c:
            return c

    for row in (getattr(configuration_order, "documents", None) or []):
        title = (getattr(row, "doc_title", "") or "")
        note = (getattr(row, "small_text_vtsj", "") or "")
        for text in (title, note):
            marker = "BOM Export Package:"
            if marker in text:
                return text.split(marker, 1)[1].split("|")[0].strip()

    return None


def _resolve_flat_bom_file_url(build, configuration_order):
    direct = (
        getattr(build, "flat_bom_file", None)
        or getattr(configuration_order, "flat_bom_file", None)
        or getattr(configuration_order, "configured_flat_bom_file", None)
    )
    if direct:
        return direct

    for row in (getattr(configuration_order, "documents", None) or []):
        title = (getattr(row, "doc_title", "") or "").lower()
        if "flat bom" in title or "configured bom csv" in title:
            return getattr(row, "file_url", None) or getattr(row, "file", None)

    return None


def _get_configured_rows_for_build(build_doc):
    top_bom = getattr(build_doc, "top_bom", None) or getattr(build_doc, "bom", None)
    snapshot_name = _resolve_snapshot_name(build_doc)
    co_name = _resolve_configuration_order_name(build_doc)

    if not top_bom:
        frappe.throw("Top BOM is required to derive configured rows for builder release.")
    if not snapshot_name:
        frappe.throw("Selected/Latest Snapshot is required to derive configured rows for builder release.")
    if not co_name:
        frappe.throw("Latest Configuration Order is required to derive configured rows for builder release.")

    temp = frappe._dict({
        "inductone_build": build_doc.name,
        "configured_snapshot": snapshot_name,
        "bom": top_bom,
        "explosion_mode": getattr(build_doc, "explosion_mode", None) or "Follow Explicit Child BOM Links",
        "max_depth": getattr(build_doc, "max_depth", None),
        "include_qty": getattr(build_doc, "include_qty", 1),
        "configuration_order": co_name,
    })
    return build_configured_rows(temp)


def _derive_required_serial_capture_rows(configured_rows):
    item_meta = {}
    out = []

    for row in configured_rows:
        item_code = row.get("item_code")
        if not item_code:
            continue

        if item_code not in item_meta:
            item_meta[item_code] = frappe.db.get_value(
                "Item",
                item_code,
                ["item_name", "has_serial_no", "serial_no_series", "description"],
                as_dict=True,
            ) or {}

        meta = item_meta[item_code]
        if int(meta.get("has_serial_no") or 0) != 1:
            continue

        out.append({
            "item_code": item_code,
            "item_name": row.get("item_name") or meta.get("item_name") or "",
            "bom_level": row.get("bom_level"),
            "node_type": row.get("node_type"),
            "expected_qty": row.get("qty") or 1,
            "bom_used": row.get("bom_used") or "",
            "parent_item_code": (row.get("ancestor_item_codes") or [""])[-1] if (row.get("ancestor_item_codes") or []) else "",
            "serial_no_series": meta.get("serial_no_series") or "",
            "description": row.get("description") or meta.get("description") or "",
            "vendor_serial_no": "",
            "por_serial_no": "",
            "installed_serial_no": "",
            "installed": 1,
            "notes": "",
        })

    return out


def _required_serial_capture_csv_bytes(rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([
        "item_code", "item_name", "bom_level", "node_type", "expected_qty", "bom_used",
        "parent_item_code", "serial_no_series", "description", "vendor_serial_no",
        "por_serial_no", "installed_serial_no", "installed", "notes"
    ])
    for r in rows:
        w.writerow([
            r.get("item_code") or "",
            r.get("item_name") or "",
            r.get("bom_level") or "",
            r.get("node_type") or "",
            r.get("expected_qty") or "",
            r.get("bom_used") or "",
            r.get("parent_item_code") or "",
            r.get("serial_no_series") or "",
            r.get("description") or "",
            r.get("vendor_serial_no") or "",
            r.get("por_serial_no") or "",
            r.get("installed_serial_no") or "",
            r.get("installed") or "",
            r.get("notes") or "",
        ])
    return out.getvalue().encode("utf-8")


def _as_built_serial_capture_csv_bytes(rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([
        "item_code", "item_name", "bom_level", "expected_qty", "serial_no", "vendor_serial_no",
        "por_serial_no", "parent_item_code", "installed", "notes"
    ])
    for r in rows:
        w.writerow([
            r.get("item_code") or "",
            r.get("item_name") or "",
            r.get("bom_level") or "",
            r.get("expected_qty") or "",
            r.get("serial_no") or r.get("installed_serial_no") or "",
            r.get("vendor_serial_no") or "",
            r.get("por_serial_no") or "",
            r.get("parent_item_code") or "",
            r.get("installed") if r.get("installed") is not None else 1,
            r.get("notes") or "",
        ])
    return out.getvalue().encode("utf-8")


def _sync_required_serial_capture_table(build_doc, rows):
    fieldname = _find_first_child_table_field(build_doc, [
        "required_serial_capture",
        "required_serials",
        "builder_required_serial_capture",
        "serial_capture_requirements",
    ])
    if not fieldname:
        return

    build_doc.set(fieldname, [])
    for r in rows:
        build_doc.append(fieldname, {
            "item_code": r.get("item_code"),
            "item_name": r.get("item_name"),
            "bom_level": r.get("bom_level"),
            "node_type": r.get("node_type"),
            "expected_qty": r.get("expected_qty"),
            "qty_required": r.get("expected_qty"),
            "bom_used": r.get("bom_used"),
            "parent_item_code": r.get("parent_item_code"),
            "serial_no_series": r.get("serial_no_series"),
            "description": r.get("description"),
            "installed": 1,
            "status": "Pending",
        })
    build_doc.save(ignore_permissions=True)


def _sync_as_built_serial_capture_table(build_doc, rows):
    fieldname = _find_first_child_table_field(build_doc, [
        "as_built_serial_capture",
        "as_built_serials",
        "actual_serial_capture",
        "builder_serial_submission",
    ])
    if not fieldname:
        return

    build_doc.set(fieldname, [])
    for r in rows:
        build_doc.append(fieldname, {
            "item_code": r.get("item_code"),
            "item_name": r.get("item_name"),
            "bom_level": r.get("bom_level"),
            "expected_qty": r.get("expected_qty"),
            "serial_no": r.get("serial_no") or r.get("installed_serial_no"),
            "vendor_serial_no": r.get("vendor_serial_no"),
            "por_serial_no": r.get("por_serial_no"),
            "parent_item_code": r.get("parent_item_code"),
            "installed": r.get("installed") if r.get("installed") is not None else 1,
            "notes": r.get("notes"),
            "status": "Submitted",
        })
    build_doc.save(ignore_permissions=True)


def _sync_builder_release_document_index(configuration_order_name, build_name, bundle_url, package_name=None, flat_bom_file_url=None):
    note = f"Builder release bundle for build {build_name}"
    if package_name:
        note += f" | BOM Export Package: {package_name}"
    if flat_bom_file_url:
        note += f" | Flat BOM: {flat_bom_file_url}"

    _append_or_update_document_index_row(
        parent_doctype="InductOne Configuration Order",
        parent_name=configuration_order_name,
        title=f"Builder Release Bundle - {build_name}",
        file_url=bundle_url,
        source_type="BUILD",
        source_name=build_name,
        sort_order=310,
        note=note,
    )


def _append_or_update_document_index_row(parent_doctype, parent_name, title, file_url, source_type="OTHER", source_name="", sort_order=300, note=""):
    doc = frappe.get_doc(parent_doctype, parent_name)
    existing = None

    for row in (getattr(doc, "documents", None) or []):
        if (getattr(row, "doc_title", "") or "").strip() == title:
            existing = row
            break

    payload = {
        "source_type": source_type,
        "source_name": source_name,
        "doc_type": "OTHER",
        "doc_title": title,
        "file": file_url or "",
        "file_url": file_url or "",
        "required": "YES",
        "sort_order": sort_order,
        "small_text_vtsj": note,
    }

    if existing:
        for k, v in payload.items():
            if hasattr(existing, k):
                setattr(existing, k, v)
    else:
        doc.append("documents", payload)

    doc.save(ignore_permissions=True)


def _find_first_child_table_field(doc, candidates):
    meta = getattr(doc, "meta", None)
    if not meta:
        return None

    for name in candidates:
        try:
            field = meta.get_field(name)
        except Exception:
            field = None
        if field and field.fieldtype == "Table":
            return name

    return None


def _set_if_present(doc, fieldnames, value):
    for fname in fieldnames:
        try:
            if hasattr(doc, fname):
                setattr(doc, fname, value)
                return True
            field = doc.meta.get_field(fname)
            if field:
                doc.set(fname, value)
                return True
        except Exception:
            continue
    return False