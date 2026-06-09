import frappe

def execute():
    # Auto-discover the latest build/snap/pkg rather than hardcoding
    # Find the most recently modified InductOne Build
    builds = frappe.get_all(
        "InductOne Build",
        fields=["name", "build_status", "latest_snapshot",
                "latest_config_order", "latest_bom_export_package",
                "top_item", "top_bom"],
        order_by="modified desc",
        limit=5
    )
    print("=" * 60)
    print("RECENT BUILDS")
    print("=" * 60)
    for b in builds:
        print(f"  {b['name']} status={b['build_status']} snap={b['latest_snapshot']}")

    # Use the build from the screenshot
    BUILD = "SAL-ORD-2026-00047-BLD-0200"
    snap_name = frappe.db.get_value("InductOne Build", BUILD, "latest_snapshot")
    co_name   = frappe.db.get_value("InductOne Build", BUILD, "latest_config_order")
    pkg_name  = frappe.db.get_value("InductOne Build", BUILD, "latest_bom_export_package")

    # Also check CO for snapshot link in case build field is stale
    if not snap_name and co_name:
        snap_name = frappe.db.get_value(
            "InductOne Configuration Order", co_name, "snapshot"
        )

    # And find package by build if not on build record
    if not pkg_name:
        pkg_list = frappe.get_all(
            "BOM Export Package",
            filters={"inductone_build": BUILD},
            fields=["name", "status", "output_zip", "configured_snapshot"],
            order_by="modified desc",
            limit=1
        )
        if pkg_list:
            pkg_name = pkg_list[0]["name"]

    print(f"\n  Using BUILD={BUILD}")
    print(f"  SNAP={snap_name}")
    print(f"  CO={co_name}")
    print(f"  PKG={pkg_name}")

    if not snap_name:
        print("\n  FAIL: No snapshot found for this build. Generate a snapshot first.")
        return

    SNAP = snap_name

    from inductone_tools.bom_export import build_configured_rows
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

    # Discover selected options dynamically
    selected = [r for r in (build.selections or [])
                if int(getattr(r, "selected", 0) or 0) == 1]

    print("\n" + "=" * 60)
    print("SELECTED OPTIONS")
    print("=" * 60)
    for s in selected:
        print(f"  {s.option_code:25} group={s.option_group}")

    # Build SPOT_CHECK dynamically from selected option mappings
    from inductone_tools.bom_export import fetch_option_actions_server
    from inductone_tools.bom_export import explode_bom_tree_structured

    should_present = set()
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
            qty     = m.get("qty_fixed")

            if action == "REMOVE":
                print(f"    REMOVE {target} ({expand}) -> should be ABSENT")
                should_absent.add(target)
                if expand in ("EXPLODE_DEFAULT_BOM", "USE_TARGET_BOM"):
                    bom = (m.get("target_bom") if expand == "USE_TARGET_BOM"
                           else frappe.db.get_value("BOM",
                               {"item": target, "is_default": 1,
                                "is_active": 1, "docstatus": 1}, "name"))
                    if bom:
                        rows = explode_bom_tree_structured(
                            bom, "Follow Explicit Child BOM Links", None, True)
                        for r in rows:
                            if r["is_leaf"]:
                                should_absent.add(r["item_code"])

            elif action == "ADD":
                print(f"    ADD {target} ({expand}) qty={qty} -> should be PRESENT")
                should_present.add(target)
                if expand in ("EXPLODE_DEFAULT_BOM", "USE_TARGET_BOM"):
                    bom = (m.get("target_bom") if expand == "USE_TARGET_BOM"
                           else frappe.db.get_value("BOM",
                               {"item": target, "is_default": 1,
                                "is_active": 1, "docstatus": 1}, "name"))
                    if bom:
                        rows = explode_bom_tree_structured(
                            bom, "Follow Explicit Child BOM Links", None, True)
                        for r in rows:
                            should_present.add(r["item_code"])

            elif action == "REPLACE":
                replace_with = m.get("replace_with_item")
                print(f"    REPLACE {target} WITH {replace_with} ({expand}) "
                      f"-> {target} ABSENT, {replace_with} PRESENT")
                should_absent.add(target)
                should_present.add(replace_with)

            elif action == "QTY_OVERRIDE":
                print(f"    QTY_OVERRIDE {target} qty={qty} -> should be PRESENT "
                      f"at qty={qty}")
                should_present.add(target)

    # Remove conflicts (items that appear in both — e.g. shared fasteners
    # that are added by one option and removed by another)
    conflicts = should_present & should_absent
    if conflicts:
        print(f"\n  NOTE: {len(conflicts)} item(s) in both PRESENT and ABSENT sets "
              f"(option ordering determines final state): {conflicts}")

    def spot_check(collection, label):
        print(f"\n  Spot-check [{label}]:")
        print(f"  {'Item':<45} {'Expected':<10} {'Actual':<10} {'PASS/FAIL'}")
        print(f"  {'-'*45} {'-'*10} {'-'*10} {'-'*9}")
        failures = []
        for item in sorted(should_present | should_absent):
            hits = [r for r in collection if r.get("item_code") == item]
            actual = "PRESENT" if hits else "ABSENT"
            if item in conflicts:
                expected = "CONFLICT"
                result = "SKIP"
            elif item in should_present:
                expected = "PRESENT"
                result = "PASS" if hits else "FAIL"
            else:
                expected = "ABSENT"
                result = "PASS" if not hits else "FAIL"
            if result == "FAIL":
                failures.append((item, expected, actual))
            marker = "*** FAIL ***" if result == "FAIL" else result
            print(f"  {item:<45} {expected:<10} {actual:<10} {marker}")
        print(f"\n  Total checks: {len(should_present | should_absent)} | "
              f"Failures: {len(failures)}")
        return failures

    def orphan_check(nodes, label):
        id_list = []
        for r in nodes:
            id_list.append(r["node_id"])
        id_set = set(id_list)
        olist = []
        for r in nodes:
            pid = r["parent_node_id"]
            if pid and pid not in id_set:
                olist.append(r)
        print(f"  Orphans [{label}]: {len(olist)}")
        for o in olist:
            print(f"    ORPHAN item={o['item_code']} node={o['node_id']} "
                  f"parent={o['parent_node_id']}")
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
    p4_failures = spot_check(written, "DB hierarchy")

    # Phase 5
    print("\n" + "=" * 60)
    print("PHASE 5 - generate_hierarchy_workbook")
    print("=" * 60)
    wb = generate_hierarchy_workbook(SNAP)
    print(f"  {wb}")
    attachments = frappe.get_all(
        "File",
        filters={"attached_to_doctype": "Configured BOM Snapshot",
                 "attached_to_name": SNAP},
        fields=["file_name", "file_url", "creation"],
        order_by="creation desc"
    )
    hfiles = [f for f in attachments
              if "_configured_bom_hierarchy_" in (f["file_name"] or "").lower()]
    if hfiles:
        print(f"  OK - {hfiles[0]['file_name']}")
    else:
        print(f"  FAIL - no hierarchy workbook attached")
        print(f"  Attachments: {[f['file_name'] for f in attachments]}")

    # Phase 6
    print("\n" + "=" * 60)
    print("PHASE 6 - CO document index")
    print("=" * 60)
    co_name = (frappe.db.get_value(
        "InductOne Configuration Order", {"snapshot": SNAP}, "name")
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
        for row in sorted(doc_rows,
                          key=lambda r: int(getattr(r, "sort_order", 0) or 0)):
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
    if not pkg_name:
        print("  No package - generate from build form first")
    else:
        pkg = frappe.get_doc("BOM Export Package", pkg_name)
        print(f"  Package: {pkg_name} | status={pkg.status} "
              f"| zip={pkg.output_zip or 'NOT GENERATED'}")
        if pkg.output_zip:
            field = pkg.meta.get_field("results")
            if field:
                results = frappe.get_all(
                    field.options,
                    filters={"parent": pkg_name},
                    fields=["item_code", "bom_level", "qty",
                            "has_pdf", "node_type"],
                    order_by="bom_level asc, item_code asc"
                )
                print(f"  Results rows: {len(results)}")
                p7_failures = spot_check(results, "export package")
                print(f"\n  Phase 7 failures: {len(p7_failures)}")
        else:
            print("  Not generated - run Generate from the package form first")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Phase 3 (dry-run hierarchy) failures: {len(p3_failures)}")
    print(f"  Phase 4 (DB hierarchy) failures:      {len(p4_failures)}")
    print(f"  Structural effects on snapshot: "
          f"{len(getattr(snap, 'structural_effects', None) or [])}")
    print(f"  Delta lines on snapshot: "
          f"{len(getattr(snap, 'delta_lines', None) or [])}")
    for e in (getattr(snap, "structural_effects", None) or []):
        print(f"    effect: action={e.action} mode={e.effect_mode} "
              f"target={e.target_item} src={e.source_option_code}")
