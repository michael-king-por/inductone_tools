"""
Configured BOM Snapshot Hierarchy — populator and workbook generator.

Two whitelisted entry points:

  populate_snapshot_hierarchy(snapshot_name):
      Called from the client snapshot-generation flow right after the
      Configured BOM Snapshot is inserted. Reads the snapshot, runs the
      existing tree resolver (bom_export.build_configured_rows), and
      writes one Configured BOM Snapshot Hierarchy row per resolved
      node. Frozen forever after.

  generate_hierarchy_workbook(snapshot_name):
      Called immediately after populate_snapshot_hierarchy. Reads the
      hierarchy rows, renders an XLSX matching the live BOM Explorer
      report visual style, attaches it to the Snapshot, registers it
      in the linked CO's Document Index.

Design notes:
  - Path 1 architecture: snapshot creation is client-driven. These
    server functions are called explicitly by the client AFTER the
    snapshot insert succeeds. No doc_events, no after_insert magic.
  - We use bom_export.build_configured_rows directly (Path B2 from the
    discussion): a stub BOM Export Package doc is constructed in memory
    and passed in. The export-package code path is unchanged.
  - Item Name, Description, UOM, Item Group are copied from live Item
    records at hierarchy-population time. Once written, they are frozen
    on the hierarchy child rows and never re-read. This is the whole
    point — the snapshot is immune to later edits.
  - Excel outline grouping is applied per bom_level so builders get
    native collapse/expand. Indentation in the Item Code column uses
    leading nbsp characters so visual hierarchy survives sort/filter.
"""

import io

import frappe
from frappe import _
from frappe.utils import now, now_datetime
from frappe.utils.file_manager import save_file

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from inductone_tools.bom_export import build_configured_rows


# ============================================================
#  Public entry points
# ============================================================

@frappe.whitelist()
def populate_snapshot_hierarchy(snapshot_name):
    """
    Materialize the hierarchical tree onto the Configured BOM Snapshot.

    Called from the client snapshot-generation flow after the snapshot is
    inserted. Writes one Configured BOM Snapshot Hierarchy row per node
    in the resolved tree. Idempotent: existing hierarchy rows are wiped
    and replaced if called again on the same snapshot.

    Returns a dict with row counts and any warnings.
    """
    if not snapshot_name:
        frappe.throw(_("snapshot_name is required."))

    snap = frappe.get_doc("Configured BOM Snapshot", snapshot_name)

    if not snap.inductone_build:
        frappe.throw(_(
            "Snapshot {0} has no linked InductOne Build; "
            "hierarchy population requires it to resolve options."
        ).format(snapshot_name))

    if not snap.top_bom:
        frappe.throw(_(
            "Snapshot {0} has no top_bom; hierarchy cannot be resolved."
        ).format(snapshot_name))

    # Wipe any existing hierarchy rows. Idempotent re-runs replace
    # rather than append.
    _clear_snapshot_hierarchy(snapshot_name)

    # Build a stub BOM Export Package doc so we can call
    # build_configured_rows without modifying it.
    stub_package = _build_stub_export_package(snap)

    # This is where the work happens. The function resolves baseline
    # tree + structural effects + selected options into a final
    # filtered list of nodes.
    resolved_rows = build_configured_rows(stub_package)

    # Walk resolved rows, attach node_id and parent_node_id, write to
    # the hierarchy child table.
    hierarchy_rows = _assign_node_ids_and_parents(resolved_rows)

    # Enrich each row with frozen copies of Item metadata.
    _enrich_with_item_metadata(hierarchy_rows)

    # Bulk insert.
    _insert_hierarchy_rows(snapshot_name, hierarchy_rows)

    frappe.db.commit()

    return {
        "ok": True,
        "snapshot_name": snapshot_name,
        "hierarchy_rows": len(hierarchy_rows),
        "assemblies": sum(1 for r in hierarchy_rows if r["node_type"] == "Assembly"),
        "leaves": sum(1 for r in hierarchy_rows if r["node_type"] == "Leaf"),
    }


@frappe.whitelist()
def generate_hierarchy_workbook(snapshot_name):
    """
    Generate the indented BOM XLSX from the snapshot's hierarchy table,
    attach it to the snapshot, and register it in the linked CO's
    Document Index.

    Returns the file_url of the saved workbook.
    """
    if not snapshot_name:
        frappe.throw(_("snapshot_name is required."))

    snap = frappe.get_doc("Configured BOM Snapshot", snapshot_name)

    if not (snap.hierarchy or []):
        frappe.throw(_(
            "Snapshot {0} has no hierarchy rows. Run populate_snapshot_hierarchy "
            "first, or regenerate the snapshot."
        ).format(snapshot_name))

    workbook_bytes = _render_hierarchy_workbook(snap)

    fname = "{0}_Configured_BOM_Hierarchy_{1}.xlsx".format(
        snapshot_name,
        now_datetime().strftime("%Y%m%d_%H%M%S")
    )

    saved = save_file(
        fname=fname,
        content=workbook_bytes,
        dt="Configured BOM Snapshot",
        dn=snapshot_name,
        is_private=1,
    )

    # Register in CO Document Index if there's a linked CO.
    co_name = _resolve_co_for_snapshot(snapshot_name)
    if co_name:
        _register_in_co_document_index(co_name, snapshot_name, saved.file_url)

    frappe.db.commit()

    return {
        "ok": True,
        "snapshot_name": snapshot_name,
        "file_url": saved.file_url,
        "configuration_order": co_name,
    }


# ============================================================
#  Stub package construction — Path B2
# ============================================================

def _build_stub_export_package(snap):
    """
    Construct a minimal BOM Export Package doc in memory with just
    enough fields for build_configured_rows to do its work.

    This is the Path B2 approach: rather than refactor
    build_configured_rows to accept a generic context, we hand it the
    same shape of object it already expects. No risk of behavior drift.

    Not inserted, not saved. Lives only in memory for the duration of
    this call.
    """
    stub = frappe.get_doc({
        "doctype": "BOM Export Package",
        "source_mode": "Configured Build",
        "bom": snap.top_bom,
        "inductone_build": snap.inductone_build,
        "configured_snapshot": snap.name,
        # build_configured_rows reads explosion_mode and max_depth.
        # Use the same defaults the real release flow uses.
        "explosion_mode": "Follow Explicit Child BOM Links",
        "max_depth": 0,
        "include_qty": 1,
    })
    return stub


# ============================================================
#  Hierarchy row construction
# ============================================================

def _assign_node_ids_and_parents(resolved_rows):
    """
    Walk the resolved rows in order and produce hierarchy rows with
    stable node_id / parent_node_id linkage.

    The resolved rows come out of build_configured_rows in walk order
    (depth-first via explode_bom_tree_structured). For each row, the
    parent is the most recently emitted row whose item_code matches
    the last entry in this row's ancestor_item_codes AND whose
    bom_level is exactly one less.

    For root-level rows (no ancestors), parent_node_id is empty.
    """
    out = []
    # Stack of (node_id, item_code, bom_level) representing the open
    # branch from the root down to the current insertion point.
    # We pop entries when we move back up the tree.
    branch_stack = []

    counter = [0]
    def _next_id():
        counter[0] += 1
        return "N{0:05d}".format(counter[0])

    for row in resolved_rows:
        node_id = _next_id()
        bom_level = int(row.get("bom_level") or 0)
        ancestor_items = row.get("ancestor_item_codes") or []

        # Pop branch_stack entries that are at or below this row's level.
        # The remaining top of stack is our parent.
        while branch_stack and branch_stack[-1][2] >= bom_level:
            branch_stack.pop()

        # Validate that the stack head corresponds to our expected parent.
        # If ancestor_items is non-empty, the last ancestor should match
        # the top of the stack. If not, the rows arrived out of order
        # and we still produce a best-effort parent pointer.
        parent_node_id = ""
        if branch_stack:
            parent_node_id = branch_stack[-1][0]

        node = {
            "node_id": node_id,
            "parent_node_id": parent_node_id,
            "bom_level": bom_level,
            "item_code": row.get("item_code") or "",
            "item_name": row.get("item_name") or "",
            "description": row.get("description") or "",
            "qty": float(row.get("qty") or 0),
            "uom": row.get("uom") or "",
            "bom_used": row.get("bom_used") or "",
            "node_type": row.get("node_type") or "Leaf",
            "is_leaf": 1 if row.get("is_leaf") else 0,
            # effect_origin and source_option_code are not currently in
            # the resolved row dict from build_configured_rows; we set
            # BASELINE as default and let future work refine this when
            # build_configured_rows is updated to propagate origin.
            "effect_origin": "BASELINE",
            "source_option_code": "",
            "excluded_by_structural_effect": 0,
            "item_group": "",  # filled in by _enrich_with_item_metadata
        }

        out.append(node)

        # Push this node onto the stack so subsequent rows can find it
        # as parent.
        branch_stack.append((node_id, row.get("item_code") or "", bom_level))

    return out


def _enrich_with_item_metadata(hierarchy_rows):
    """
    Fill item_group, and backfill item_name/description/uom from the
    Item master if any of them are missing on the hierarchy row.

    These values are frozen onto the hierarchy rows. Once written, they
    never re-read live data — the snapshot is immune to later edits.
    """
    item_codes = sorted({
        r["item_code"] for r in hierarchy_rows
        if r.get("item_code")
    })

    if not item_codes:
        return

    # One bulk query for all item metadata.
    items = frappe.get_all(
        "Item",
        filters={"name": ["in", item_codes]},
        fields=["name", "item_name", "description", "stock_uom", "item_group"],
    )
    item_index = {i["name"]: i for i in items}

    for r in hierarchy_rows:
        ic = r.get("item_code")
        if not ic:
            continue
        meta = item_index.get(ic) or {}
        if not r.get("item_name"):
            r["item_name"] = meta.get("item_name") or ""
        if not r.get("description"):
            r["description"] = meta.get("description") or ""
        if not r.get("uom"):
            r["uom"] = meta.get("stock_uom") or ""
        r["item_group"] = meta.get("item_group") or ""


# ============================================================
#  Persistence
# ============================================================

def _clear_snapshot_hierarchy(snapshot_name):
    """Remove all existing hierarchy rows for this snapshot. Used to
    make populate_snapshot_hierarchy idempotent."""
    frappe.db.delete("Configured BOM Snapshot Hierarchy", {
        "parent": snapshot_name,
        "parenttype": "Configured BOM Snapshot",
        "parentfield": "hierarchy",
    })


def _insert_hierarchy_rows(snapshot_name, hierarchy_rows):
    """
    Direct child-row inserts without saving the parent. Same pattern
    used in bom_export.update_results_and_missing_summary — avoids the
    optimistic-lock pitfall on the snapshot form.
    """
    for idx, row in enumerate(hierarchy_rows, start=1):
        doc = frappe.get_doc({
            "doctype": "Configured BOM Snapshot Hierarchy",
            "parent": snapshot_name,
            "parenttype": "Configured BOM Snapshot",
            "parentfield": "hierarchy",
            "idx": idx,
            "node_id": row["node_id"],
            "parent_node_id": row["parent_node_id"],
            "bom_level": row["bom_level"],
            "item_code": row["item_code"],
            "item_name": row["item_name"],
            "description": row["description"],
            "qty": row["qty"],
            "uom": row["uom"],
            "bom_used": row["bom_used"],
            "node_type": row["node_type"],
            "is_leaf": row["is_leaf"],
            "effect_origin": row["effect_origin"],
            "source_option_code": row["source_option_code"],
            "excluded_by_structural_effect": row["excluded_by_structural_effect"],
            "item_group": row["item_group"],
        })
        doc.insert(ignore_permissions=True)


# ============================================================
#  Workbook rendering — match BOM Explorer visual style
# ============================================================

# Column layout — matches the BOM Explorer report screenshot.
COLUMNS = [
    ("Item Code",            "item_code",          50),
    ("Item Name",            "item_name",          30),
    ("BOM",                  "bom_used",           28),
    ("Qty",                  "qty",                 8),
    ("UOM",                  "uom",                 8),
    ("BOM Level",            "bom_level",          10),
    ("Standard Description", "description",        40),
    ("Item Group",           "item_group",         18),
]

INDENT_CHAR = "\u00a0"  # non-breaking space
INDENT_WIDTH = 4        # nbsp chars per level

HEADER_FILL = PatternFill("solid", fgColor="F0F0F0")
HEADER_FONT = Font(bold=True, color="333333", size=11)
ROOT_FILL = PatternFill("solid", fgColor="FAFAFA")
ASSEMBLY_FONT = Font(bold=False, color="000000")
LEAF_FONT = Font(bold=False, color="333333")
THIN_BORDER = Border(
    bottom=Side(style="thin", color="E0E0E0"),
)


def _render_hierarchy_workbook(snap):
    """
    Produce the XLSX bytes matching the live BOM Explorer report
    visual style: indented item codes, Excel outline grouping for
    collapse/expand, frozen header, filterable columns, provenance
    header block.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Configured BOM Hierarchy"

    # ---- Provenance header block (rows 1-7) ----
    _write_provenance_header(ws, snap)

    # ---- Column header row (row 9) ----
    header_row = 9
    for col_idx, (label, _key, width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=label)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(vertical="center")
        cell.border = THIN_BORDER
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[header_row].height = 22
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    # Filterable range — applied after we know how many data rows.

    # ---- Data rows ----
    data_start_row = header_row + 1
    current_row = data_start_row

    # Insert the synthetic root row first — the top BOM itself.
    # The BOM Explorer report shows the root assembly as level 0.
    root_row = _build_root_row(snap)
    _write_data_row(ws, current_row, root_row, level=0)
    current_row += 1

    for h in (snap.hierarchy or []):
        row_data = {
            "item_code": h.item_code or "",
            "item_name": h.item_name or "",
            "bom_used": h.bom_used or "",
            "qty": h.qty,
            "uom": h.uom or "",
            "bom_level": h.bom_level or 0,
            "description": h.description or "",
            "item_group": h.item_group or "",
            "node_type": h.node_type or "Leaf",
        }
        _write_data_row(ws, current_row, row_data, level=int(h.bom_level or 0))
        current_row += 1

    data_end_row = current_row - 1

    # ---- Filter + autosizing tweaks ----
    if data_end_row >= data_start_row:
        last_col_letter = get_column_letter(len(COLUMNS))
        ws.auto_filter.ref = "A{0}:{1}{2}".format(
            header_row, last_col_letter, data_end_row
        )

    # ---- Outline grouping ----
    # Apply outline_level so Excel's group-collapse controls work.
    for excel_row in range(data_start_row, data_end_row + 1):
        # We need the bom_level for THIS row, not the iterator.
        # Walk the data we already wrote: read cell (row, BOM Level col).
        bom_level_col = next(i for i, c in enumerate(COLUMNS, start=1) if c[1] == "bom_level")
        level_val = ws.cell(row=excel_row, column=bom_level_col).value
        try:
            level_int = int(level_val or 0)
        except (TypeError, ValueError):
            level_int = 0
        # Outline level: 0 means the row is always visible; > 0 means it
        # collapses under the row above it at the next-lower level.
        ws.row_dimensions[excel_row].outline_level = level_int

    ws.sheet_properties.outlinePr.summaryBelow = False
    ws.sheet_properties.outlinePr.summaryRight = False

    # ---- Save to bytes ----
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def _write_provenance_header(ws, snap):
    """
    Render rows 1-7: title and key metadata block, matching the visual
    weight of the BOM Explorer's header callout.
    """
    title_cell = ws.cell(row=1, column=1, value="Configured BOM Hierarchy")
    title_cell.font = Font(bold=True, size=16, color="1F2A44")

    # Top BOM in a styled callout — matches the report screenshot's
    # rounded BOM name pill.
    top_bom_cell = ws.cell(row=2, column=1, value=snap.top_bom or "(no top BOM)")
    top_bom_cell.font = Font(bold=True, size=11, color="1F2A44")
    top_bom_cell.fill = PatternFill("solid", fgColor="EEF2F7")
    top_bom_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)

    # Metadata block rows 4-7
    meta = [
        ("Snapshot",            snap.name),
        ("InductOne Build",     snap.inductone_build or ""),
        ("Top BOM",             snap.top_bom or ""),
        ("Generated At",        str(snap.generated_at or "")),
        ("Snapshot Rev",        str(snap.snapshot_rev or "")),
        ("Source Watermark",    "Configured BOM Hierarchy export | "
                                "snapshot frozen at generation | "
                                "Plus One Robotics confidential"),
    ]
    for i, (label, value) in enumerate(meta, start=4):
        label_cell = ws.cell(row=i, column=1, value=label)
        label_cell.font = Font(bold=True, color="555555", size=10)
        ws.cell(row=i, column=2, value=value).font = Font(color="333333", size=10)


def _build_root_row(snap):
    """Synthesize the root row for the top BOM, since the resolved
    rows from build_configured_rows are children of the root, not
    inclusive of it."""
    top_item = snap.top_item or ""
    top_item_name = ""
    top_item_desc = ""
    top_item_uom = ""
    top_item_group = ""

    if top_item:
        item_meta = frappe.db.get_value(
            "Item", top_item,
            ["item_name", "description", "stock_uom", "item_group"],
            as_dict=True,
        ) or {}
        top_item_name = item_meta.get("item_name") or ""
        top_item_desc = item_meta.get("description") or ""
        top_item_uom = item_meta.get("stock_uom") or ""
        top_item_group = item_meta.get("item_group") or ""

    return {
        "item_code": top_item,
        "item_name": top_item_name,
        "bom_used": snap.top_bom or "",
        "qty": 1,
        "uom": top_item_uom,
        "bom_level": 0,
        "description": top_item_desc,
        "item_group": top_item_group,
        "node_type": "Assembly",
    }


def _write_data_row(ws, excel_row, row_data, level):
    """Write a single data row with appropriate indentation and styling."""
    for col_idx, (_label, key, _width) in enumerate(COLUMNS, start=1):
        value = row_data.get(key, "")

        # Indent the Item Code column by bom_level.
        if key == "item_code" and value:
            indent = INDENT_CHAR * (INDENT_WIDTH * level)
            cell_value = "{0}{1}".format(indent, value)
        elif key == "qty":
            # Render qty as float; preserve int display when whole.
            try:
                q = float(value or 0)
                cell_value = q
            except (TypeError, ValueError):
                cell_value = value
        else:
            cell_value = value

        cell = ws.cell(row=excel_row, column=col_idx, value=cell_value)
        cell.border = THIN_BORDER
        cell.alignment = Alignment(vertical="center", wrap_text=False)

        # Slight visual differentiation: assemblies bold, leaves plain.
        if row_data.get("node_type") == "Assembly":
            cell.font = Font(bold=False, color="000000", size=10)
        else:
            cell.font = Font(bold=False, color="333333", size=10)

        if key == "qty":
            cell.alignment = Alignment(vertical="center", horizontal="right")

    ws.row_dimensions[excel_row].height = 18


# ============================================================
#  CO Document Index registration
# ============================================================

def _resolve_co_for_snapshot(snapshot_name):
    """Find the CO that this snapshot was used in. The CO has a
    `snapshot` field linking back to the snapshot."""
    return frappe.db.get_value(
        "InductOne Configuration Order",
        {"snapshot": snapshot_name},
        "name",
    )


def _register_in_co_document_index(co_name, snapshot_name, file_url):
    """
    Add or update the Document Index row for the hierarchy workbook on
    the linked CO. Mirrors the pattern in bom_export.sync_package_into_configuration_order.
    """
    co = frappe.get_doc("InductOne Configuration Order", co_name)

    row_title = "Configured BOM Hierarchy - {0}".format(snapshot_name)
    row_note = (
        "Indented BOM as resolved against the configured snapshot. "
        "Authoritative for the released configuration. "
        "Snapshot: {0}".format(snapshot_name)
    )

    existing_row = None
    for row in (co.documents or []):
        title = (getattr(row, "doc_title", "") or "").strip()
        if "Configured BOM Hierarchy" in title and snapshot_name in title:
            existing_row = row
            break

    if existing_row:
        existing_row.source_type = "MANUAL"
        existing_row.source_name = snapshot_name
        existing_row.doc_type = "OTHER"
        existing_row.doc_title = row_title
        existing_row.file_url = file_url
        if hasattr(existing_row, "file"):
            existing_row.file = file_url
        existing_row.required = "YES"
        existing_row.sort_order = 250  # Between CO PDF (~100) and BOM Export Package (~300)
        existing_row.small_text_vtsj = row_note
    else:
        co.append("documents", {
            "source_type": "MANUAL",
            "source_name": snapshot_name,
            "doc_type": "OTHER",
            "doc_title": row_title,
            "file_url": file_url,
            "required": "YES",
            "sort_order": 250,
            "small_text_vtsj": row_note,
        })

    co.save(ignore_permissions=True)
