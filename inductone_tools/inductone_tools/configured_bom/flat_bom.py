"""
flat_bom.py — RE-BASED on snapshot.hierarchy (single source of truth).

CHANGE SUMMARY
==============
OLD behavior: _build_flat_bom_rows_from_snapshot read snapshot.lines (the flat
final_map), filtered included==1, rolled up by (item_code, uom). It had no tree
and therefore could not reflect per-node contextual quantities or correct
parent-chain multiplication for option-driven node-quantity changes.

NEW behavior: the flat / procurement BOM is derived by walking
snapshot.hierarchy, which is the single source of truth. We:
  - include LEAF nodes only (procurement BOM — no assemblies)
  - multiply each leaf's contextual qty by the product of every ancestor
    node's contextual qty (top-down rollup)
  - roll up identical leaf item_codes into a single total line

This makes the flat BOM a pure function of the frozen hierarchy, so it can never
disagree with the hierarchy workbook again. The hierarchy node quantities already
reflect option-driven increments (INCREMENT_NODE_QTY) and injected branches
(ADD_BRANCH), so those flow into the rollup automatically.

snapshot.lines is no longer consulted for quantities here. It retains only its
membership role elsewhere (included flag in build_configured_rows).
"""

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
      - Builds rolled-up flat PROCUREMENT BOM (leaf items only) by walking the
        snapshot hierarchy and multiplying quantities down each ancestor chain
      - Saves CSV as File attachment
      - Writes link + document-index row back onto the config order
    """
    co = frappe.get_doc("InductOne Configuration Order", config_order_name)
    _set_status(co.name, "Running", error="")

    try:
        if not co.snapshot:
            raise frappe.ValidationError(
                "Configuration Order has no Snapshot linked. Cannot build flat BOM CSV."
            )

        snap = frappe.get_doc("Configured BOM Snapshot", co.snapshot)

        # SINGLE SOURCE OF TRUTH: roll up from the materialized hierarchy.
        rows = build_flat_bom_rows_from_hierarchy(snap)

        csv_bytes = _render_csv_bytes(config_order=co, snapshot=snap, rows=rows)

        fname = f"{co.name}_Flat_BOM.csv"
        saved = save_file(
            fname=fname,
            content=csv_bytes,
            dt="InductOne Configuration Order",
            dn=co.name,
            is_private=1,
        )

        co = frappe.get_doc("InductOne Configuration Order", co.name)

        doc_title = f"{co.name} Flat BOM CSV"
        existing_row = None
        for row in (co.documents or []):
            if (row.doc_title or "") == doc_title or (row.file_url or "") == (saved.file_url or ""):
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
            existing_row.small_text_vtsj = "Auto-generated rolled-up flat procurement BOM (leaf items, hierarchy-derived)."
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
                "small_text_vtsj": "Auto-generated rolled-up flat procurement BOM (leaf items, hierarchy-derived).",
            })

        co.flat_bom_status = "Complete"
        co.flat_bom_error = ""
        co.save(ignore_permissions=True)
        frappe.db.commit()

    except Exception:
        tb = frappe.get_traceback()
        frappe.db.set_value("InductOne Configuration Order", co.name, {
            "flat_bom_status": "Failed",
            "flat_bom_error": tb,
        })
        frappe.db.commit()
        raise


# -----------------------------
# Core rollup — hierarchy walk
# -----------------------------

def build_flat_bom_rows_from_hierarchy(snapshot_doc):
    """
    Roll up the frozen snapshot hierarchy into a flat PROCUREMENT BOM.

    Rules (per spec):
      - LEAF nodes only. Assemblies are structural; they do not appear in the
        procurement BOM. Their quantity multiplies their descendants.
      - Each leaf's effective quantity = leaf contextual qty
          × product of every ancestor node's contextual qty (root → leaf).
      - Roll up identical item_codes (one UOM per item, guaranteed) by summing
        effective quantities.

    Implementation detail:
      The hierarchy child rows carry node_id / parent_node_id and a contextual
      qty per node. We build a node map, compute each node's cumulative
      multiplier as parent_multiplier × node_qty, then emit leaves.

    Returns a list of dict rows: item_code, item_name, description, source, uom, qty(str).
    """
    hierarchy = list(snapshot_doc.hierarchy or [])
    if not hierarchy:
        # Defensible: an empty hierarchy yields an empty BOM rather than silently
        # falling back to a different (now-retired) source of truth.
        return []

    # Index nodes by node_id.
    nodes_by_id = {}
    for h in hierarchy:
        node_id = getattr(h, "node_id", None)
        if not node_id:
            # Hierarchy rows must have node_ids (populator guarantees this).
            # If one is missing, fail loudly rather than produce a wrong BOM.
            raise frappe.ValidationError(
                f"Hierarchy row for item {getattr(h, 'item_code', '?')} on snapshot "
                f"{snapshot_doc.name} has no node_id; cannot roll up safely."
            )
        nodes_by_id[node_id] = h

    # Compute cumulative multiplier per node via memoized walk to root.
    multiplier_cache = {}

    def _cumulative_multiplier(node_id):
        if node_id in multiplier_cache:
            return multiplier_cache[node_id]

        node = nodes_by_id.get(node_id)
        if node is None:
            # Parent referenced but not present — should never happen given the
            # populator's orphan checks, but guard anyway.
            raise frappe.ValidationError(
                f"Hierarchy node {node_id} on snapshot {snapshot_doc.name} references "
                f"a missing node; cannot compute rollup multiplier."
            )

        node_qty = _to_decimal(getattr(node, "qty", 0))
        parent_id = getattr(node, "parent_node_id", "") or ""

        if not parent_id:
            result = node_qty
        else:
            result = _cumulative_multiplier(parent_id) * node_qty

        multiplier_cache[node_id] = result
        return result

    # Pre-fetch item metadata in bulk for clean output.
    leaf_item_codes = sorted({
        getattr(h, "item_code", None)
        for h in hierarchy
        if int(getattr(h, "is_leaf", 0) or 0) == 1 and getattr(h, "item_code", None)
    })

    item_meta = {}
    if leaf_item_codes:
        meta_rows = frappe.get_all(
            "Item",
            filters={"name": ["in", leaf_item_codes]},
            fields=["name", "item_name", "description", "stock_uom", "custom_source"],
        )
        for r in meta_rows:
            item_meta[r["name"]] = r

    # Roll up leaves.
    rollup = {}
    for h in hierarchy:
        if int(getattr(h, "is_leaf", 0) or 0) != 1:
            continue  # leaves only

        item_code = getattr(h, "item_code", None)
        if not item_code:
            continue

        node_id = getattr(h, "node_id")
        effective_qty = _cumulative_multiplier(node_id)

        uom = (getattr(h, "uom", None)
               or item_meta.get(item_code, {}).get("stock_uom")
               or "")

        key = (item_code, uom)  # one UOM per item guaranteed; compound key is a safety net
        if key not in rollup:
            meta = item_meta.get(item_code, {})
            rollup[key] = {
                "item_code": item_code,
                "item_name": (getattr(h, "item_name", None) or meta.get("item_name") or ""),
                "description": (getattr(h, "description", None) or meta.get("description") or ""),
                "source": meta.get("custom_source") or "",
                "uom": uom,
                "qty": Decimal("0"),
            }
        rollup[key]["qty"] += effective_qty

    out = list(rollup.values())
    out.sort(key=lambda r: (r["item_code"], r["uom"]))
    for r in out:
        r["qty"] = _decimal_to_str(r["qty"])
    return out


# -----------------------------
# CSV rendering
# -----------------------------

def _render_csv_bytes(config_order, snapshot, rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["CONFIG_ORDER", config_order.name])
    w.writerow(["SNAPSHOT", snapshot.name])
    w.writerow(["SALES_ORDER", getattr(config_order, "sales_order", "")])
    w.writerow(["INDUCTONE_BUILD", getattr(config_order, "inductone_build", "")])
    w.writerow(["ORIENTATION", getattr(config_order, "orientation", "")])
    w.writerow(["GENERATED_AT", str(now_datetime())])
    w.writerow(["SOURCE_OF_TRUTH", "snapshot.hierarchy (leaf rollup, parent-chain multiplied)"])
    w.writerow([])
    w.writerow(["Item Code", "Item Name", "Description", "Source", "Total Qty", "UOM"])
    for r in rows:
        w.writerow([
            r.get("item_code", ""),
            r.get("item_name", ""),
            r.get("description", ""),
            r.get("source", ""),
            r.get("qty", ""),
            r.get("uom", ""),
        ])
    return out.getvalue().encode("utf-8")


# -----------------------------
# helpers
# -----------------------------

def _set_status(config_order_name: str, status: str, error: str = ""):
    frappe.db.set_value("InductOne Configuration Order", config_order_name, {
        "flat_bom_status": status,
        "flat_bom_error": error or "",
    })


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
