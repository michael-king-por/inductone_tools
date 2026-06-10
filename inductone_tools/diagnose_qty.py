import frappe

def execute():
    BUILD = "SAL-ORD-2026-00047-BLD-0200"

    # Auto-find latest snapshot for this build
    snap_name = frappe.db.get_value("InductOne Build", BUILD, "latest_snapshot")
    print(f"BUILD={BUILD}")
    print(f"SNAP={snap_name}")

    from inductone_tools.bom_export import (
        build_configured_rows,
        load_snapshot_structural_effect_sets,
    )
    from inductone_tools.snapshot.hierarchy import (
        _build_stub_export_package,
        _assign_node_ids_and_parents,
        _enrich_with_item_metadata,
        populate_snapshot_hierarchy,
        generate_hierarchy_workbook,
        sync_hierarchy_workbook_to_configuration_order,
    )

    snap = frappe.get_doc("Configured BOM Snapshot", snap_name)
    stub = _build_stub_export_package(snap)

    TARGET_ITEMS = {"1000095", "94453A349", "96194A104", "2000188"}

    # ── Step 1: Snapshot flat lines — must now show correct quantities ────────
    print("\n" + "=" * 60)
    print("STEP 1 — Snapshot flat lines (must be 4.0, 16.0, 16.0)")
    print("=" * 60)
    failures = []
    expected = {"1000095": 4.0, "94453A349": 16.0, "96194A104": 16.0}
    for ln in (snap.lines or []):
        if (ln.item_code or "") in TARGET_ITEMS:
            exp = expected.get(ln.item_code)
            actual = float(ln.qty or 0)
            result = "PASS" if exp is None or abs(actual - exp) < 0.01 else "FAIL"
            if result == "FAIL":
                failures.append(ln.item_code)
            print(f"  {result} item={ln.item_code} qty={actual} "
                  f"expected={exp} included={ln.included}")

    # ── Step 2: snapshot_qty_by_item after fix ────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 2 — snapshot_qty_by_item (must be 4.0, 16.0, 16.0)")
    print("=" * 60)
    snapshot_qty_by_item = {}
    for ln in (snap.lines or []):
        ic = getattr(ln, "item_code", None)
        if not ic:
            continue
        if int(getattr(ln, "included", 0) or 0) != 1:
            continue
        snapshot_qty_by_item[ic] = float(getattr(ln, "qty", 0) or 0)
    for item in sorted(TARGET_ITEMS):
        val = snapshot_qty_by_item.get(item)
        exp = expected.get(item)
        result = "N/A" if exp is None else ("PASS" if val and abs(val - exp) < 0.01 else "FAIL")
        if result == "FAIL":
            failures.append(item)
        print(f"  {result} {item}: snap_qty={val} expected={exp}")

    # ── Step 3: build_configured_rows final output ────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 3 — build_configured_rows final output")
    print("=" * 60)
    rows = build_configured_rows(stub)
    for r in rows:
        if r["item_code"] in TARGET_ITEMS:
            exp = expected.get(r["item_code"])
            actual = float(r["qty"] or 0)
            result = "N/A" if exp is None else ("PASS" if abs(actual - exp) < 0.01 else "FAIL")
            if result == "FAIL":
                failures.append(r["item_code"])
            print(f"  {result} item={r['item_code']} qty={actual} "
                  f"expected={exp} level={r['bom_level']} "
                  f"ancestor={r.get('ancestor_item_codes', [])}")

    # ── Step 4: leaf_occurrence_count — verify would_rewrite is now safe ──────
    print("\n" + "=" * 60)
    print("STEP 4 — apply_snapshot_quantities rewrite check")
    print("=" * 60)
    leaf_occurrence_count = {}
    for r in rows:
        if not r.get("is_leaf"):
            continue
        ic = r.get("item_code") or ""
        leaf_occurrence_count[ic] = leaf_occurrence_count.get(ic, 0) + 1
    for item in sorted(TARGET_ITEMS):
        count = leaf_occurrence_count.get(item, 0)
        snap_qty = snapshot_qty_by_item.get(item)
        exp = expected.get(item)
        would_rewrite = (count == 1 and item in snapshot_qty_by_item)
        # After fix: snap_qty should equal the BOM qty, so rewrite is harmless
        rewrite_safe = (snap_qty is not None and exp is not None
                        and abs(snap_qty - exp) < 0.01)
        result = "PASS" if (not would_rewrite or rewrite_safe) else "FAIL"
        if result == "FAIL":
            failures.append(item)
        print(f"  {result} {item}: occurrences={count} snap_qty={snap_qty} "
              f"bom_qty={exp} would_rewrite={would_rewrite} rewrite_safe={rewrite_safe}")

    # ── Step 5: hierarchy dry-run ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 5 — Hierarchy dry-run")
    print("=" * 60)
    hr = _assign_node_ids_and_parents(rows)
    _enrich_with_item_metadata(hr)

    id_list = [r["node_id"] for r in hr]
    id_set = set(id_list)
    orphans = [r for r in hr if r["parent_node_id"] and r["parent_node_id"] not in id_set]
    print(f"  Orphans: {len(orphans)}")
    if orphans:
        for o in orphans:
            print(f"    ORPHAN item={o['item_code']} node={o['node_id']} "
                  f"parent={o['parent_node_id']}")

    print("\n  Riser tree:")
    for r in hr:
        if r["item_code"] in TARGET_ITEMS:
            indent = "  " * int(r["bom_level"])
            flag = "[ASSM]" if r["node_type"] == "Assembly" else "[LEAF]"
            exp = expected.get(r["item_code"])
            actual = float(r["qty"] or 0)
            result = "N/A" if exp is None else ("PASS" if abs(actual - exp) < 0.01 else "FAIL")
            if result == "FAIL":
                failures.append(r["item_code"])
            print(f"  {indent}{flag} level={r['bom_level']} {r['item_code']} "
                  f"qty={actual} expected={exp} {result} "
                  f"parent={r['parent_node_id']}")

    # ── Step 6: populate + workbook + CO sync ─────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 6 — populate_snapshot_hierarchy")
    print("=" * 60)
    pop = populate_snapshot_hierarchy(snap_name)
    print(f"  {pop}")

    written = frappe.get_all(
        "Configured BOM Snapshot Hierarchy",
        filters={"parent": snap_name},
        fields=["node_id", "parent_node_id", "bom_level",
                "item_code", "qty", "node_type"],
        order_by="idx asc"
    )
    print(f"  DB rows: {len(written)}")
    print("\n  Riser tree in DB:")
    for r in written:
        if r["item_code"] in TARGET_ITEMS:
            indent = "  " * int(r["bom_level"])
            flag = "[ASSM]" if r["node_type"] == "Assembly" else "[LEAF]"
            exp = expected.get(r["item_code"])
            actual = float(r["qty"] or 0)
            result = "N/A" if exp is None else ("PASS" if abs(actual - exp) < 0.01 else "FAIL")
            if result == "FAIL":
                failures.append(r["item_code"])
            print(f"    {indent}{flag} level={r['bom_level']} {r['item_code']} "
                  f"qty={actual} expected={exp} {result} parent={r['parent_node_id']}")

    print("\n" + "=" * 60)
    print("STEP 7 — generate_hierarchy_workbook + CO sync")
    print("=" * 60)
    wb = generate_hierarchy_workbook(snap_name)
    print(f"  Workbook: {wb.get('file_url')}")

    co_name = frappe.db.get_value(
        "InductOne Configuration Order", {"snapshot": snap_name}, "name"
    )
    if co_name:
        sync = sync_hierarchy_workbook_to_configuration_order(snap_name, co_name)
        print(f"  CO sync ok: {sync.get('ok')}")
    else:
        print("  No CO linked to this snapshot")

    # ── Final summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    unique_failures = list(dict.fromkeys(failures))
    if unique_failures:
        print(f"  FAILURES ({len(unique_failures)}): {unique_failures}")
    else:
        print("  ALL CHECKS PASSED")
