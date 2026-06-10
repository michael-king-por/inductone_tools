import frappe

def execute():
    BUILD = "SAL-ORD-2026-00047-BLD-0200"
    SNAP  = "SAL-ORD-2026-00047-BLD-0200-SNAP-0205"

    co_name  = frappe.db.get_value("InductOne Build", BUILD, "latest_config_order")
    pkg_list = frappe.get_all(
        "BOM Export Package",
        filters={"inductone_build": BUILD},
        fields=["name", "status", "output_zip", "configured_snapshot"],
        order_by="modified desc",
        limit=1
    )
    pkg_name = pkg_list[0]["name"] if pkg_list else None

    print(f"BUILD={BUILD}")
    print(f"SNAP={SNAP}")
    print(f"CO={co_name}")
    print(f"PKG={pkg_name}")

    from inductone_tools.bom_export import build_configured_rows, fetch_option_actions_server, explode_bom_tree_structured
    from inductone_tools.snapshot.hierarchy import (
        _build_stub_export_package,
        _assign_node_ids_and_parents,
        _enrich_with_item_metadata,
        populate_snapshot_hierarchy,
        generate_hierarchy_workbook,
        sync_hierarchy_workbook_to_configuration_order,
    )

    build = frappe.get_doc("InductOne Build", BUILD)
    snap  = frappe.get_doc("Configured BOM Snapshot", SNAP)

    selected = [r for r in (build.selections or [])
                if int(getattr(r, "selected", 0) or 0) == 1]

    print("\n" + "=" * 60)
    print("SELECTED OPTIONS")
    print("=" * 60)
    for s in selected:
        print(f"  {s.option_code:25} group={s.option_group}")

    should_present = {}  # item -> expected_qty
    should_absent  = set()

    print("\n" + "=" * 60)
    print("EXPECTED EFFECTS PER OPTION")
    print("=" * 60)

    for s in selected:
        mappings = fetch_option_actions_server(s.option)
        print(f"\n  [{s.option_code}]")
        for m in mappings:
            action  = m.get("action")
            target  = m.get("target_item")
            expand  = m.get("expand_mode")
            qty_fixed = float(m.get("qty_fixed") or 1.0)

            if action == "REMOVE":
                print(f"    REMOVE {target} ({expand}) -> ABSENT")
                should_absent.add(target)
                if expand in ("EXPLODE_DEFAULT_BOM", "USE_TARGET_BOM"):
                    bom = (m.get("target_bom") if expand == "USE_TARGET_BOM"
                           else frappe.db.get_value("BOM",
                               {"item": target, "is_default": 1, "is_active": 1, "docstatus": 1}, "name"))
                    if bom:
                        rows = explode_bom_tree_structured(bom, "Follow Explicit Child BOM Links", None, True)
                        for r in rows:
                            if r["is_leaf"]:
                                should_absent.add(r["item_code"])

            elif action == "ADD":
                if expand in ("EXPLODE_DEFAULT_BOM", "USE_TARGET_BOM"):
                    bom = (m.get("target_bom") if expand == "USE_TARGET_BOM"
                           else frappe.db.get_value("BOM",
                               {"item": target, "is_default": 1, "is_active": 1, "docstatus": 1}, "name"))
                    if bom:
                        # Assembly root
                        should_present[target] = {"qty": qty_fixed, "check_qty": True, "is_assembly": True}
                        print(f"    ADD {target} ({expand}) qty={qty_fixed} -> PRESENT as assembly")
                        rows = explode_bom_tree_structured(bom, "Follow Explicit Child BOM Links", None, True)
                        for r in rows:
                            expected_qty = r["qty"] * qty_fixed
                            should_present[r["item_code"]] = {
                                "qty": expected_qty,
                                "check_qty": not r.get("is_leaf") is False,
                                "level": r["bom_level"] + 1,  # +1 because injected at level 1
                            }
                            flag = "[LEAF]" if r["is_leaf"] else "[ASSM]"
                            print(f"      {flag} {r['item_code']} expected_qty={expected_qty} level={r['bom_level']+1}")
                else:
                    should_present[target] = {"qty": qty_fixed, "check_qty": False}
                    print(f"    ADD {target} ({expand}) qty={qty_fixed} -> PRESENT")

            elif action == "REPLACE":
                replace_with = m.get("replace_with_item")
                print(f"    REPLACE {target} WITH {replace_with} -> {target} ABSENT, {replace_with} PRESENT")
                should_absent.add(target)
                should_present[replace_with] = {"qty": qty_fixed, "check_qty": False}

            elif action == "QTY_OVERRIDE":
                print(f"    QTY_OVERRIDE {target} qty={qty_fixed} -> PRESENT qty={qty_fixed}")
                should_present[target] = {"qty": qty_fixed, "check_qty": True}

    def spot_check(collection, label):
        print(f"\n  Spot-check [{label}]:")
        print(f"  {'Item':<45} {'Exp':>6} {'Act':>6} {'Exp Qty':>10} {'Act Qty':>10}  RESULT")
        print(f"  {'-'*45} {'-'*6} {'-'*6} {'-'*10} {'-'*10}  {'-'*10}")
        failures = []
        all_items = set(should_present.keys()) | should_absent
        for item in sorted(all_items):
            hits = [r for r in collection if r.get("item_code") == item]
            actual_present = bool(hits)
            actual_qty = sum(float(r.get("qty") or 0) for r in hits) if hits else 0

            if item in should_absent and item in should_present:
                result = "CONFLICT"
            elif item in should_absent:
                exp_str = "ABSENT"
                act_str = "PRESENT" if actual_present else "ABSENT"
                exp_qty = "-"
                act_qty = str(actual_qty) if actual_present else "-"
                result = "PASS" if not actual_present else "*** FAIL ***"
                if result != "PASS":
                    failures.append(item)
                print(f"  {item:<45} {exp_str:>6} {act_str:>6} {exp_qty:>10} {act_qty:>10}  {result}")
                continue
            else:
                exp_info = should_present[item]
                exp_str = "PRESENT"
                act_str = "PRESENT" if actual_present else "ABSENT"
                exp_qty_val = exp_info.get("qty")
                exp_qty = str(exp_qty_val) if exp_qty_val is not None else "any"
                act_qty = str(actual_qty) if actual_present else "-"

                if not actual_present:
                    result = "*** FAIL ***"
                    failures.append(item)
                elif exp_info.get("check_qty") and exp_qty_val is not None:
                    # For items that appear multiple times (same item in multiple sub-assemblies),
                    # check that at least one occurrence has the right qty
                    qty_ok = any(abs(float(r.get("qty") or 0) - exp_qty_val) < 0.01 for r in hits)
                    result = "PASS" if qty_ok else f"QTY MISMATCH"
                    if not qty_ok:
                        failures.append(item)
                else:
                    result = "PASS"

            print(f"  {item:<45} {exp_str:>6} {act_str:>6} {exp_qty:>10} {act_qty:>10}  {result}")

        print(f"\n  Total: {len(all_items)} | Failures: {len(failures)}")
        return failures

    def orphan_check(nodes, label):
        id_list = [r["node_id"] for r in nodes]
        id_set = set(id_list)
        olist = [r for r in nodes if r["parent_node_id"] and r["parent_node_id"] not in id_set]
        print(f"  Orphans [{label}]: {len(olist)}")
        for o in olist:
            print(f"    ORPHAN item={o['item_code']} node={o['node_id']} parent={o['parent_node_id']}")
        if not olist:
            print(f"  OK - all parent references resolve [{label}]")
        return olist

    # Phase 3
    print("\n" + "=" * 60)
    print("PHASE 3 - Hierarchy dry-run + orphan check")
    print("=" * 60)
    stub = _build_stub_export_package(snap)
    rows = build_configured_rows(stub)
    hr   = _assign_node_ids_and_parents(rows)
    _enrich_with_item_metadata(hr)
    print(f"  Resolved rows: {len(rows)} | Hierarchy nodes: {len(hr)}")
    orphan_check(hr, "dry-run")

    # Show riser tree structure specifically
    riser_items = {"2000188","2000189","1000095","94453A349","96194A104"}
    print("\n  Riser tree in dry-run:")
    for r in hr:
        if r.get("item_code") in riser_items:
            indent = "  " * int(r["bom_level"])
            flag = "[ASSM]" if r["node_type"] == "Assembly" else "[LEAF]"
            print(f"    {indent}{flag} level={r['bom_level']} {r['item_code']} "
                  f"qty={r['qty']} parent={r['parent_node_id']} node={r['node_id']}")

    p3_failures = spot_check(hr, "dry-run hierarchy")

    # Phase 4
    print("\n" + "=" * 60)
    print("PHASE 4 - populate_snapshot_hierarchy")
    print("=" * 60)
    pop = populate_snapshot_hierarchy(SNAP)
    print(f"  {pop}")
    written = frappe.get_all(
        "Configured BOM Snapshot Hierarchy",
        filters={"parent": SNAP},
        fields=["node_id", "parent_node_id", "bom_level",
                "item_code", "qty", "node_type", "item_group"],
        order_by="idx asc"
    )
    print(f"  DB rows written: {len(written)}")
    orphan_check(written, "DB")

    print("\n  Riser tree in DB:")
    for r in written:
        if r.get("item_code") in riser_items:
            indent = "  " * int(r["bom_level"])
            flag = "[ASSM]" if r["node_type"] == "Assembly" else "[LEAF]"
            print(f"    {indent}{flag} level={r['bom_level']} {r['item_code']} "
                  f"qty={r['qty']} parent={r['parent_node_id']}")

    p4_failures = spot_check(written, "DB hierarchy")

    # Phase 5
    print("\n" + "=" * 60)
    print("PHASE 5 - generate_hierarchy_workbook")
    print("=" * 60)
    wb = generate_hierarchy_workbook(SNAP)
    print(f"  {wb}")
    attachments = frappe.get_all(
        "File",
        filters={"attached_to_doctype": "Configured BOM Snapshot", "attached_to_name": SNAP},
        fields=["file_name", "file_url", "creation"],
        order_by="creation desc"
    )
    hfiles = [f for f in attachments if "_configured_bom_hierarchy_" in (f["file_name"] or "").lower()]
    if hfiles:
        print(f"  OK - {hfiles[0]['file_name']}")
    else:
        print(f"  FAIL - no hierarchy workbook attached")

    # Phase 6
    print("\n" + "=" * 60)
    print("PHASE 6 - CO document index")
    print("=" * 60)
    co_name = (frappe.db.get_value("InductOne Configuration Order", {"snapshot": SNAP}, "name")
               or build.latest_config_order)
    if not co_name:
        print("  No CO - generate Configuration Order first")
    else:
        print(f"  CO: {co_name}")
        sync = sync_hierarchy_workbook_to_configuration_order(SNAP, co_name)
        print(f"  Sync ok: {sync.get('ok')} | {sync.get('message')}")
        co = frappe.get_doc("InductOne Configuration Order", co_name)
        doc_rows = list(co.documents or [])
        print(f"  Document index ({len(doc_rows)} rows):")
        for row in sorted(doc_rows, key=lambda r: int(getattr(r, "sort_order", 0) or 0)):
            title    = getattr(row, "doc_title", "") or ""
            file_url = getattr(row, "file_url", "") or ""
            sort_ord = getattr(row, "sort_order", "") or ""
            required = getattr(row, "required", "") or ""
            print(f"    [{sort_ord:>3}] {'FILE:Y' if file_url else 'FILE:N'} "
                  f"required={required} - {title}")

    # Phase 7
    print("\n" + "=" * 60)
    print("PHASE 7 - BOM Export Package")
    print("=" * 60)
    # Find package for this specific snapshot
    pkg_for_snap = frappe.db.get_value(
        "BOM Export Package",
        {"inductone_build": BUILD, "configured_snapshot": SNAP}, "name"
    ) or pkg_name
    if not pkg_for_snap:
        print("  No package - generate from build form first")
    else:
        pkg = frappe.get_doc("BOM Export Package", pkg_for_snap)
        print(f"  Package: {pkg_for_snap} | status={pkg.status} "
              f"| snap={pkg.configured_snapshot}")
        print(f"  ZIP: {pkg.output_zip or 'NOT GENERATED'}")
        if pkg.output_zip:
            field = pkg.meta.get_field("results")
            if field:
                results = frappe.get_all(
                    field.options,
                    filters={"parent": pkg_for_snap},
                    fields=["item_code", "bom_level", "qty", "has_pdf", "node_type"],
                    order_by="bom_level asc, item_code asc"
                )
                print(f"  Results rows: {len(results)}")

                print("\n  Riser rows in export package:")
                for r in results:
                    if r["item_code"] in riser_items:
                        print(f"    level={r['bom_level']} {r['item_code']} "
                              f"qty={r['qty']} pdf={r['has_pdf']} type={r['node_type']}")

                p7_failures = spot_check(results, "export package")
        else:
            print("  Not generated - run Generate from the package form first")
            p7_failures = []

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Phase 3 failures: {len(p3_failures)}")
    print(f"  Phase 4 failures: {len(p4_failures)}")
    print(f"  Structural effects: {len(getattr(snap, 'structural_effects', None) or [])}")
    for e in (getattr(snap, "structural_effects", None) or []):
        print(f"    {e.action:7} mode={e.effect_mode:25} target={e.target_item} src={e.source_option_code}")
