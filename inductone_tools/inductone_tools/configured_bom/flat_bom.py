import csv
import io
from decimal import Decimal, InvalidOperation

import frappe
from frappe.utils import now_datetime
from frappe.utils.file_manager import save_file


# -----------------------------
# Public job entrypoint
# -----------------------------

def build_and_attach_flat_bom_for_config_order(config_order_name: str):
    """
    Background job:
      - Reads InductOne Configuration Order
      - Reads linked Configured BOM Snapshot
      - Builds rolled-up flat BOM from included=1 snapshot lines
      - Saves CSV as File attachment
      - Writes link back onto config order
    """

    # Load config order
    co = frappe.get_doc("InductOne Configuration Order", config_order_name)

    # Mark running
    _set_status(co.name, "Running", error="")

    try:
        if not co.snapshot:
            raise frappe.ValidationError("Configuration Order has no Snapshot linked. Cannot build flat BOM CSV.")

        snap = frappe.get_doc("Configured BOM Snapshot", co.snapshot)

        # Build rolled-up rows
        rows = _build_flat_bom_rows_from_snapshot(snap)

        # Render CSV bytes
        csv_bytes = _render_csv_bytes(
            config_order=co,
            snapshot=snap,
            rows=rows
        )

        # Attach CSV to configuration order
        fname = f"{co.name}_Flat_BOM.csv"
        saved = save_file(
            fname=fname,
            content=csv_bytes,
            dt="InductOne Configuration Order",
            dn=co.name,
            is_private=1
        )

        # Reload full doc so we can safely update child tables
        co = frappe.get_doc("InductOne Configuration Order", co.name)

        doc_title = f"{co.name} Flat BOM CSV"
        existing_row = None

        for row in (co.documents or []):
            if (
                (row.doc_title or "") == doc_title
                or (row.file_url or "") == (saved.file_url or "")
            ):
                existing_row = row
                break

        if existing_row:
            existing_row.source_type = "MANUAL"
            existing_row.source_name = co.name
            existing_row.doc_type = "OTHER"
            existing_row.doc_title = doc_title
            existing_row.file = saved.file_url
            existing_row.file_url = saved.file_url
            existing_row.required = "YES"
            existing_row.sort_order = 900
            existing_row.small_text_vtsj = "Auto-generated rolled-up flat BOM CSV."
        else:
            co.append("documents", {
                "source_type": "MANUAL",
                "source_name": co.name,
                "doc_type": "OTHER",
                "doc_title": doc_title,
                "file": saved.file_url,
                "file_url": saved.file_url,
                "required": "YES",
                "sort_order": 900,
                "small_text_vtsj": "Auto-generated rolled-up flat BOM CSV."
            })

        co.flat_bom_status = "Complete"
        co.flat_bom_error = ""

        co.save(ignore_permissions=True)
        frappe.db.commit()

    except Exception:
        tb = frappe.get_traceback()
        frappe.db.set_value("InductOne Configuration Order", co.name, {
            "flat_bom_status": "Failed",
            "flat_bom_error": tb
        })
        frappe.db.commit()
        raise


# -----------------------------
# Helpers
# -----------------------------

def _set_status(config_order_name: str, status: str, error: str = ""):
    frappe.db.set_value("InductOne Configuration Order", config_order_name, {
        "flat_bom_status": status,
        "flat_bom_error": error or ""
    })


def _build_flat_bom_rows_from_snapshot(snapshot_doc):
    """
    Takes snapshot.lines (Configured BOM Snapshot Item child table)
    filters to included=1
    rolls up by (item_code, uom)
    returns list of dict rows
    """

    included_lines = [ln for ln in (snapshot_doc.lines or []) if int(getattr(ln, "included", 0) or 0) == 1]

    # Keyed rollup: (item_code, uom)
    rollup = {}

    # Optional: pre-fetch item metadata in bulk for clean output (source, name, description)
    item_codes = sorted({ln.item_code for ln in included_lines if getattr(ln, "item_code", None)})

    item_meta = {}
    if item_codes:
        meta_rows = frappe.get_all(
            "Item",
            filters={"name": ["in", item_codes]},
            fields=["name", "item_name", "description", "stock_uom", "custom_source"]
        )
        for r in meta_rows:
            item_meta[r["name"]] = r

    for ln in included_lines:
        item_code = getattr(ln, "item_code", None)
        if not item_code:
            continue

        uom = getattr(ln, "uom", None) or (item_meta.get(item_code, {}).get("stock_uom")) or ""

        # parse qty as Decimal for stable math
        qty = _to_decimal(getattr(ln, "qty", 0))

        key = (item_code, uom)
        if key not in rollup:
            meta = item_meta.get(item_code, {})
            rollup[key] = {
                "item_code": item_code,
                "item_name": (getattr(ln, "item_name", None) or meta.get("item_name") or ""),
                "description": (getattr(ln, "description", None) or meta.get("description") or ""),
                "source": meta.get("custom_source") or "",
                "uom": uom,
                "qty": Decimal("0")
            }

        rollup[key]["qty"] += qty

    # Convert to sorted list
    out = list(rollup.values())

    # Deterministic ordering
    out.sort(key=lambda r: (r["item_code"], r["uom"]))

    # Convert qty to string/float for CSV
    for r in out:
        r["qty"] = _decimal_to_str(r["qty"])

    return out


def _render_csv_bytes(config_order, snapshot, rows):
    """
    Produces CSV bytes.
    """

    out = io.StringIO()
    w = csv.writer(out)

    # Header metadata (top of file) - builder-friendly and defensible
    w.writerow(["CONFIG_ORDER", config_order.name])
    w.writerow(["SNAPSHOT", snapshot.name])
    w.writerow(["SALES_ORDER", getattr(config_order, "sales_order", "")])
    w.writerow(["INDUCTONE_BUILD", getattr(config_order, "inductone_build", "")])
    w.writerow(["ORIENTATION", getattr(config_order, "orientation", "")])
    w.writerow(["GENERATED_AT", str(now_datetime())])
    w.writerow([])

    # Column headers (flat BOM)
    w.writerow(["Item Code", "Item Name", "Description", "Source", "Total Qty", "UOM"])

    for r in rows:
        w.writerow([
            r.get("item_code", ""),
            r.get("item_name", ""),
            r.get("description", ""),
            r.get("source", ""),
            r.get("qty", ""),
            r.get("uom", "")
        ])

    return out.getvalue().encode("utf-8")


def _to_decimal(x) -> Decimal:
    try:
        if x is None or x == "":
            return Decimal("0")
        return Decimal(str(x))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _decimal_to_str(d: Decimal) -> str:
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s