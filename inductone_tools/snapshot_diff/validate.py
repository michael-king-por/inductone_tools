# ============================================================================
#  SNAPSHOT DIFF -- COMPREHENSIVE BENCH VALIDATION
# ============================================================================
#
#  Run this in the bench console on the site:
#
#      bench --site plusonerobotics.v.frappe.cloud console
#
#  Then paste this whole file in, OR run it as:
#
#      bench --site plusonerobotics.v.frappe.cloud execute \
#          inductone_tools.snapshot_diff.validate.run
#
#  (if you save it as inductone_tools/snapshot_diff/validate.py)
#
#  It walks every layer bottom-up and prints PASS/FAIL at each step so you can
#  see exactly where the chain breaks. Replace the two SNAP names below with
#  your real snapshots if these are stale.
# ============================================================================

import frappe
import json
import traceback

SNAP_A = "SAL-ORD-2026-00047-BLD-0179-SNAP-0185"
SNAP_B = "SAL-ORD-2026-00047-BLD-0200-SNAP-0204"


def line(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def run():
    print("\n\n##### SNAPSHOT DIFF VALIDATION START #####")

    # ---- 0. Confirm the app module is importable at all ----
    line("0. MODULE IMPORTS")
    try:
        from inductone_tools.snapshot_diff import schema, engine, tree, loader
        print("PASS: all four modules import")
        print("     schema version:", schema.SNAPSHOT_SCHEMA_VERSION)
        print("     loader has get_report_data:", hasattr(loader, "get_report_data"))
        print("     loader has download_diff_workbook:", hasattr(loader, "download_diff_workbook"))
        print("     loader has get_diff:", hasattr(loader, "get_diff"))
    except Exception:
        print("FAIL: import error")
        traceback.print_exc()
        print("\n>>> The app code is not deployed correctly. Stop here and "
              "re-push / re-update the app before anything else.")
        return

    # ---- 1. Confirm the snapshots exist ----
    line("1. SNAPSHOTS EXIST")
    for s in (SNAP_A, SNAP_B):
        exists = frappe.db.exists("Configured BOM Snapshot", s)
        print(("PASS" if exists else "FAIL"), s, "exists =", bool(exists))
    if not (frappe.db.exists("Configured BOM Snapshot", SNAP_A)
            and frappe.db.exists("Configured BOM Snapshot", SNAP_B)):
        print("\n>>> One or both snapshot names are wrong. Fix SNAP_A / SNAP_B "
              "at the top of this script.")
        # list a few real ones to help
        recent = frappe.get_all("Configured BOM Snapshot",
                                 fields=["name"], order_by="creation desc",
                                 limit_page_length=10)
        print("     Recent snapshots:")
        for r in recent:
            print("       ", r["name"])
        return

    # ---- 2. Confirm the hierarchy child table has rows ----
    line("2. HIERARCHY ROW COUNTS")
    for s in (SNAP_A, SNAP_B):
        cnt = frappe.db.count("Configured BOM Snapshot Hierarchy",
                              {"parent": s, "parenttype": "Configured BOM Snapshot"})
        print(("PASS" if cnt else "FAIL"), s, "hierarchy rows =", cnt)
        if not cnt:
            print("     >>> This snapshot has NO hierarchy rows. The diff has "
                  "nothing to compare. Was populate_snapshot_hierarchy run for it?")

    # ---- 3. Loader: load_snapshot_nodes ----
    line("3. LOADER -- load_snapshot_nodes")
    try:
        from inductone_tools.snapshot_diff.loader import load_snapshot_nodes
        nodes_a = load_snapshot_nodes(SNAP_A)
        nodes_b = load_snapshot_nodes(SNAP_B)
        print("PASS: loaded", len(nodes_a), "nodes from A,", len(nodes_b), "from B")
        if nodes_a:
            n = nodes_a[0]
            print("     sample A node: code=%r qty=%r bom_used=%r parent=%r excluded=%r"
                  % (n.item_code, n.qty, n.bom_used, n.parent_node_id, n.excluded))
        # how many are excluded?
        ex_a = sum(1 for n in nodes_a if n.excluded)
        ex_b = sum(1 for n in nodes_b if n.excluded)
        print("     excluded rows: A=%d  B=%d  (these are dropped from the diff)" % (ex_a, ex_b))
        nonblank_a = sum(1 for n in nodes_a if n.item_code and not n.excluded)
        nonblank_b = sum(1 for n in nodes_b if n.item_code and not n.excluded)
        print("     diffable rows: A=%d  B=%d" % (nonblank_a, nonblank_b))
        if nonblank_a == 0 and nonblank_b == 0:
            print("     >>> Every row is excluded or blank. That is why the diff "
                  "is empty. Check excluded_by_structural_effect on the hierarchy.")
    except Exception:
        print("FAIL: load_snapshot_nodes raised")
        traceback.print_exc()
        return

    # ---- 4. Flat engine ----
    line("4. FLAT DIFF ENGINE")
    try:
        from inductone_tools.snapshot_diff.engine import diff_snapshots
        res = diff_snapshots(nodes_a, nodes_b, SNAP_A, SNAP_B, include_unchanged=False)
        print("PASS: flat diff ran")
        print("     added=%d removed=%d qty=%d rev=%d moved=%d  total=%d  lines=%d"
              % (res.added, res.removed, res.qty_changed, res.revision_changed,
                 res.moved, res.total_changes, len(res.lines)))
    except Exception:
        print("FAIL: flat engine raised")
        traceback.print_exc()
        return

    # ---- 5. Tree engine ----
    line("5. HIERARCHICAL DIFF ENGINE")
    try:
        from inductone_tools.snapshot_diff.tree import diff_snapshots_tree, flatten_tree
        tres = diff_snapshots_tree(nodes_a, nodes_b, SNAP_A, SNAP_B, changes_only=True)
        flat = flatten_tree(tres)
        print("PASS: tree diff ran")
        print("     added=%d removed=%d changed=%d unchanged=%d  roots=%d  flat_rows=%d"
              % (tres.added, tres.removed, tres.changed, tres.unchanged,
                 len(tres.roots), len(flat)))
        if len(flat) == 0:
            print("     >>> Tree produced zero rows. If the flat engine found "
                  "changes but the tree did not, the parent_node_id linkage in "
                  "the hierarchy is the suspect.")
        # show first few
        for n in flat[:8]:
            print("       [%s] L%d %s" % (n.status, n.bom_level, n.item_code))
    except Exception:
        print("FAIL: tree engine raised")
        traceback.print_exc()
        return

    # ---- 6. get_report_data (what the UI report calls) ----
    line("6. get_report_data  (THE METHOD THE REPORT CALLS)")
    try:
        from inductone_tools.snapshot_diff.loader import get_report_data
        for vm in ("Hierarchical", "Flat Procurement"):
            payload = get_report_data(SNAP_A, SNAP_B, view_mode=vm,
                                      context_mode="Changes only")
            cols = payload.get("columns") or []
            data = payload.get("data") or []
            print("PASS: get_report_data(%s) -> columns=%d rows=%d"
                  % (vm, len(cols), len(data)))
            if data:
                print("       sample row keys:", sorted(data[0].keys()))
    except Exception:
        print("FAIL: get_report_data raised")
        traceback.print_exc()
        return

    # ---- 7. Simulate the sandbox shell return contract ----
    line("7. SANDBOX SHELL RETURN CONTRACT")
    try:
        # This mimics exactly what the report script does.
        filters = {"snapshot_a": SNAP_A, "snapshot_b": SNAP_B,
                   "view_mode": "Hierarchical", "context_mode": "Changes only"}
        data_result = frappe.call(
            "inductone_tools.snapshot_diff.loader.get_report_data",
            snapshot_a=filters.get("snapshot_a"),
            snapshot_b=filters.get("snapshot_b"),
            view_mode=filters.get("view_mode") or "Hierarchical",
            context_mode=filters.get("context_mode") or "Changes only",
        )
        columns = data_result.get("columns")
        result = data_result.get("data")
        print("PASS via frappe.call: columns=%s rows=%s"
              % (len(columns) if columns else None,
                 len(result) if result else None))
        if not result:
            print("     >>> frappe.call returned no data rows. If step 6 had rows "
                  "but this does not, frappe.call is unwrapping the dict "
                  "differently -- check the shell's .get() usage.")
    except Exception:
        print("FAIL: frappe.call to get_report_data raised")
        traceback.print_exc()
        return

    line("VALIDATION COMPLETE")
    print("If every step PASSED but the on-screen report is still empty, the "
          "problem is in the REPORT RECORD itself (the pasted script not "
          "assigning `result`/`columns`, or Is Standard misconfigured), not in "
          "the app code. See notes below.")
    print("\n##### SNAPSHOT DIFF VALIDATION END #####\n")


# Allow `bench execute inductone_tools.snapshot_diff.validate.run`
if __name__ == "__main__":
    run()