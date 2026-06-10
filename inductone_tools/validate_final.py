import os
import csv
import subprocess
from decimal import Decimal

import frappe

# Deployed import paths (triple-nested package confirmed on bench).
from inductone_tools.inductone_tools.configured_bom.flat_bom import (
    build_flat_bom_rows_from_hierarchy,
    build_and_attach_flat_bom_for_config_order,
)
from inductone_tools.bom_export import (
    explode_bom_tree_structured,
    load_snapshot_structural_effect_sets,
)

BUILD = "SAL-ORD-2026-00047-BLD-0200"

# Hand-specified expected CONTEXTUAL node quantities (in-parent qty).
EXPECTED_NODE_QTY = {
    ("2000188", "assembly"): 1.0,        # riser branch (absent target)
    ("1000095", "leaf"): 4.0,
    ("94453A349", "leaf"): 16.0,
    ("96194A104", "leaf"): 16.0,
    ("1611 027 0279", "assembly"): 2.0,  # stacklight assembly incremented 1->2
    ("1417891/542/5.0", "leaf"): 2.0,    # cable incremented 1->2
    ("Hose, SAE1004R, 2in^1611 027 0915", "leaf"): 50.0,  # hose override
}

# Hand-specified expected FLAT (procurement) leaf totals.
# stacklight leaves double because assembly qty 2 multiplies them.
EXPECTED_FLAT_QTY = {
    "1000095": 4.0,
    "94453A349": 16.0,
    "96194A104": 16.0,
    "LR6-3ILWMNW-RYG": 2.0,   # 1 per assembly * assembly qty 2
    "LR6-BW": 2.0,
    "LR6-E-B": 2.0,
    "SZK-003W": 2.0,
    # 90128A244: stacklight contributes 4 * assembly qty 2 = 8, PLUS a separate
    # usage of 6 under 1611 027 0411 = 14 total. Verified against actual tree.
    "90128A244": 14.0,
    # 90576A104: stacklight contributes 4 * 2 = 8, plus 2 elsewhere = 10 total.
    "90576A104": 10.0,
    "1417891/542/5.0": 2.0,    # cable leaf incremented to 2
    "Hose, SAE1004R, 2in^1611 027 0915": 50.0,  # hose override
}

EXPECTED_ABSENT = ["1417891", "1407402", "1276573", "RSM RKM 30-5M/S101", "LR-10iA_10"]
# Procurement flat BOM is leaf-only. Assemblies (2000188, 1611 027 0279) are
# verified in P3 (hierarchy), NOT here.
EXPECTED_PRESENT = ["1000095", "94453A349", "96194A104", "LR-10iA_10-Pendant",
                    "1417891/542/5.0"]

APP_ROOT = os.path.expanduser("~/frappe-bench/apps/inductone_tools")


def execute():
    print("=" * 72)
    print("CONFIGURED BOM REFACTOR — FULL PIPELINE VALIDATION")
    print("=" * 72)

    snap_name = frappe.db.get_value("InductOne Build", BUILD, "latest_snapshot")
    print(f"BUILD={BUILD}")
    print(f"SNAP={snap_name}")
    snap = frappe.get_doc("Configured BOM Snapshot", snap_name)

    fails = []
    fails += p0_bom_sanity(snap)
    fails += p1_dead_code()
    fails += p2_resolver(snap)
    fails += p3_hierarchy_qty(snap)
    fails += p4_independent_flat(snap)
    p5_old_vs_new_diff(snap)  # review gate, never auto-fails
    fails += p6_conservation(snap)
    fails += p7_round_trip(snap, snap_name)

    print("\n" + "=" * 72)
    print("FINAL RESULT")
    print("=" * 72)
    uniq = list(dict.fromkeys(fails))
    if uniq:
        print(f"  {len(uniq)} FAILURE(S):")
        for f in uniq:
            print(f"    - {f}")
        print("\n  DO NOT PROMOTE. Diagnose failures above.")
    else:
        print("  ALL AUTOMATED GATES PASSED.")
        print("  Review the P5 OLD-vs-NEW diff and sign off each line before promoting.")


def p0_bom_sanity(snap):
    print("\n" + "-" * 72)
    print("P0 — BOM sanity (all make-qty == 1)")
    print("-" * 72)
    fails = []
    boms = sorted({getattr(h, "bom_used", None) for h in (snap.hierarchy or []) if getattr(h, "bom_used", None)})
    if snap.top_bom:
        boms = sorted(set(boms) | {snap.top_bom})
    bad = [(b, frappe.db.get_value("BOM", b, "quantity")) for b in boms
           if frappe.db.get_value("BOM", b, "quantity") not in (None, 1, 1.0)]
    print(f"  BOMs checked: {len(boms)} | non-unit: {len(bad)}")
    for b, q in bad:
        print(f"    FAIL {b} quantity={q}")
        fails.append(f"BOM {b} make-qty {q} != 1")
    if not bad:
        print("  OK — uniform make-qty 1")
    return fails


def p1_dead_code():
    print("\n" + "-" * 72)
    print("P1 — Deprecated path removed + no callers")
    print("-" * 72)
    fails = []
    res = subprocess.run(
        ["grep", "-rn", "--include=*.py", "--include=*.js", "generate_configured_export_now", APP_ROOT],
        capture_output=True, text=True, timeout=60,
    )
    hits = [ln for ln in (res.stdout or "").splitlines() if "validate_" not in ln]
    print(f"  references: {len(hits)}")
    for h in hits:
        print(f"    {h}")
    if hits:
        fails.append("deprecated generate_configured_export_now still referenced")
    else:
        print("  OK — fully removed, zero references")
    return fails


def p2_resolver(snap):
    print("\n" + "-" * 72)
    print("P2 — Resolver (baseline-aware ADD classification)")
    print("-" * 72)
    fails = []
    baseline = explode_bom_tree_structured(snap.top_bom, "Follow Explicit Child BOM Links", None, True)
    baseline_items = {r.get("item_code") for r in baseline if r.get("item_code")}
    sets = load_snapshot_structural_effect_sets(snap)

    # load_snapshot_structural_effect_sets returns the RAW pre-reclassification
    # buckets. build_configured_rows reclassifies ADD_BRANCH->INCREMENT for
    # targets already in the baseline. Replicate that here so we assert against
    # the RESOLVED classification, matching what actually drives the tree.
    raw_additive = list(sets.get("additive_effects", []))
    resolved_additive = []
    resolved_increment = list(sets.get("increment_effects", []))
    for eff in raw_additive:
        t = eff.get("target_item")
        if (eff.get("effect_mode") or "") == "ADD_BRANCH" and t in baseline_items:
            resolved_increment.append(dict(eff, effect_mode="INCREMENT_NODE_QTY"))
        else:
            resolved_additive.append(eff)

    for eff in resolved_additive:
        t = eff.get("target_item")
        if t in baseline_items:
            print(f"    FAIL {t} in baseline but classified branch (should INCREMENT)")
            fails.append(f"{t} misclassified as branch")
        else:
            print(f"    OK   {t} absent -> ADD_BRANCH")
    for eff in resolved_increment:
        t = eff.get("target_item")
        if t not in baseline_items:
            print(f"    FAIL {t} absent but INCREMENT (should BRANCH)")
            fails.append(f"{t} misclassified as increment")
        else:
            print(f"    OK   {t} present -> INCREMENT_NODE_QTY (+{eff.get('effect_qty')})")
    for eff in sets.get("override_effects", []):
        t = eff.get("target_item")
        print(f"    OK   {t} -> OVERRIDE_NODE_QTY (={eff.get('effect_qty')})")
    return fails


def p3_hierarchy_qty(snap):
    print("\n" + "-" * 72)
    print("P3 — Hierarchy node quantities + integrity")
    print("-" * 72)
    fails = []
    rows = list(snap.hierarchy or [])
    ids = {r.node_id for r in rows}
    orphans = [r for r in rows if r.parent_node_id and r.parent_node_id not in ids]
    print(f"  Nodes: {len(rows)} | Orphans: {len(orphans)}")
    for o in orphans:
        print(f"    FAIL ORPHAN {o.item_code} node={o.node_id} parent={o.parent_node_id}")
        fails.append(f"orphan {o.item_code}")

    for (item, kind), want in EXPECTED_NODE_QTY.items():
        want_leaf = (kind == "leaf")
        matches = [r for r in rows if r.item_code == item and bool(int(r.is_leaf or 0)) == want_leaf]
        if not matches:
            print(f"    FAIL {item} ({kind}) not found")
            fails.append(f"{item} ({kind}) missing")
            continue
        if len(matches) > 1:
            print(f"    FAIL {item} ({kind}) appears {len(matches)}x (expected single)")
            fails.append(f"{item} ({kind}) duplicated {len(matches)}x")
        for m in matches:
            got = float(m.qty or 0)
            ok = abs(got - want) < 1e-6
            print(f"    {'OK  ' if ok else 'FAIL'} {item} ({kind}) qty={got} expected={want}")
            if not ok:
                fails.append(f"{item} ({kind}) qty {got} != {want}")
    return fails


def _independent_rollup(snap):
    rows = list(snap.hierarchy or [])
    by_id = {r.node_id: r for r in rows}

    def mult(nid, seen=None):
        seen = seen or set()
        if nid in seen:
            raise RuntimeError(f"cycle at {nid}")
        seen.add(nid)
        n = by_id[nid]
        q = Decimal(str(n.qty or 0))
        pid = n.parent_node_id or ""
        return q if not pid else mult(pid, seen) * q

    totals = {}
    for r in rows:
        if int(r.is_leaf or 0) != 1:
            continue
        totals[r.item_code] = totals.get(r.item_code, Decimal("0")) + mult(r.node_id)
    return totals


def p4_independent_flat(snap):
    print("\n" + "-" * 72)
    print("P4 — Independent rollup vs production flat BOM")
    print("-" * 72)
    fails = []
    independent = _independent_rollup(snap)
    production = {r["item_code"]: Decimal(str(r["qty"]))
                 for r in build_flat_bom_rows_from_hierarchy(snap)}

    mism = 0
    for item in sorted(set(independent) | set(production)):
        a = independent.get(item, Decimal("0"))
        b = production.get(item, Decimal("0"))
        if a != b:
            mism += 1
            print(f"    FAIL {item}: independent={a} production={b}")
            fails.append(f"flat mismatch {item}")
    print(f"  Items: {len(set(independent) | set(production))} | mismatches: {mism}")
    if mism == 0:
        print("  OK — production flat BOM == independent rollup")

    for item, want in EXPECTED_FLAT_QTY.items():
        got = float(production.get(item, Decimal("0")))
        ok = abs(got - want) < 1e-6
        print(f"    {'OK  ' if ok else 'FAIL'} flat[{item}]={got} expected={want}")
        if not ok:
            fails.append(f"flat {item} {got} != {want}")

    for item in EXPECTED_PRESENT:
        if item not in production:
            print(f"    FAIL expected-present {item} missing")
            fails.append(f"{item} missing from flat")
    for item in EXPECTED_ABSENT:
        if item in production:
            print(f"    FAIL expected-absent {item} present qty={production[item]}")
            fails.append(f"{item} should be absent")
    return fails


def _old_rollup(snap):
    totals = {}
    for ln in (snap.lines or []):
        if int(getattr(ln, "included", 0) or 0) != 1:
            continue
        ic = getattr(ln, "item_code", None)
        if ic:
            totals[ic] = totals.get(ic, Decimal("0")) + Decimal(str(getattr(ln, "qty", 0) or 0))
    return totals


def p5_old_vs_new_diff(snap):
    print("\n" + "-" * 72)
    print("P5 — OLD (snapshot.lines) vs NEW (hierarchy) — REVIEW GATE")
    print("-" * 72)
    old = _old_rollup(snap)
    new = {r["item_code"]: Decimal(str(r["qty"])) for r in build_flat_bom_rows_from_hierarchy(snap)}
    items = sorted(set(old) | set(new))
    diffs = [(i, old.get(i, Decimal("0")), new.get(i, Decimal("0"))) for i in items
             if old.get(i, Decimal("0")) != new.get(i, Decimal("0"))]
    print(f"  old items: {len(old)} | new items: {len(new)} | differences: {len(diffs)}")
    if diffs:
        print(f"  {'Item':<42} {'OLD':>8} {'NEW':>8}  CAUSE")
        for i, a, b in diffs:
            if a == 0:
                cause = "NEW (hierarchy-only / branch)"
            elif b == 0:
                cause = "DROPPED (suppressed)"
            elif b > a:
                cause = "INCREASED (increment/multiply)"
            else:
                cause = "DECREASED — investigate"
            print(f"  {i:<42} {str(a):>8} {str(b):>8}  {cause}")
        print("\n  >>> Confirm every line is an intended correction before promoting.")
    else:
        print("  No differences.")


def p6_conservation(snap):
    print("\n" + "-" * 72)
    print("P6 — Conservation (untouched leaves unchanged old vs new)")
    print("-" * 72)
    fails = []
    sets = load_snapshot_structural_effect_sets(snap)
    touched = set()
    for k in ("additive_effects", "increment_effects", "replacement_effects", "override_effects"):
        for eff in sets.get(k, []):
            if eff.get("target_item"):
                touched.add(eff["target_item"])
            # REPLACE introduces a new replacement item — it is legitimately
            # new, not "untouched". Mark it touched so conservation does not
            # flag it.
            if eff.get("replace_with_item"):
                touched.add(eff["replace_with_item"])
    touched |= set(sets.get("suppressed_node_items", set()))
    touched |= set(sets.get("suppressed_branch_items", set()))
    touched |= set(sets.get("removed_target_items", set()))

    by_id = {h.node_id: h for h in (snap.hierarchy or [])}

    def ancestors(node):
        out, pid = [], (node.parent_node_id or "")
        while pid:
            p = by_id.get(pid)
            if not p:
                break
            out.append(p.item_code)
            pid = p.parent_node_id or ""
        return out

    affected = set(touched)
    for h in (snap.hierarchy or []):
        if int(h.is_leaf or 0) != 1:
            continue
        if h.item_code in touched or (set(ancestors(h)) & touched):
            affected.add(h.item_code)

    old = _old_rollup(snap)
    new = {r["item_code"]: Decimal(str(r["qty"])) for r in build_flat_bom_rows_from_hierarchy(snap)}

    checked = moved = 0
    for item in sorted(set(old) | set(new)):
        if item in affected:
            continue
        checked += 1
        if old.get(item, Decimal("0")) != new.get(item, Decimal("0")):
            moved += 1
            print(f"    FAIL untouched {item} old={old.get(item)} new={new.get(item)}")
            fails.append(f"conservation broken {item}")
    print(f"  Untouched checked: {checked} | moved: {moved}")
    if moved == 0:
        print("  OK — nothing unintended moved")
    return fails


def p7_round_trip(snap, snap_name):
    print("\n" + "-" * 72)
    print("P7 — Round-trip exported flat CSV vs truth")
    print("-" * 72)
    fails = []
    truth = {r["item_code"]: r["qty"] for r in build_flat_bom_rows_from_hierarchy(snap)}

    co_name = frappe.db.get_value("InductOne Configuration Order", {"snapshot": snap_name}, "name")
    if not co_name:
        print("  SKIP — no CO linked")
        return fails

    build_and_attach_flat_bom_for_config_order(co_name)

    files = frappe.get_all("File",
        filters={"attached_to_doctype": "InductOne Configuration Order", "attached_to_name": co_name},
        fields=["file_name", "file_url", "creation"], order_by="creation desc")
    csvf = next((f for f in files if (f["file_name"] or "").lower().endswith(".csv")
                 and "flat_bom" in (f["file_name"] or "").lower()), None)
    if not csvf:
        print("  FAIL — no flat CSV attached")
        return fails + ["flat CSV not produced"]

    path = _resolve(csvf["file_url"])
    if not path or not os.path.exists(path):
        print(f"  FAIL — CSV not on disk: {csvf['file_url']}")
        return fails + ["flat CSV missing on disk"]

    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    start = next((i + 1 for i, r in enumerate(rows) if r and r[0] == "Item Code"), None)
    parsed = {}
    if start is not None:
        for r in rows[start:]:
            if r and r[0]:
                parsed[r[0]] = r[4]

    mism = 0
    for item, q in truth.items():
        pq = parsed.get(item)
        if pq is None:
            mism += 1
            print(f"    FAIL {item} in truth absent from CSV")
            fails.append(f"{item} absent from CSV")
        elif Decimal(str(pq)) != Decimal(str(q)):
            mism += 1
            print(f"    FAIL {item} CSV={pq} truth={q}")
            fails.append(f"CSV {item} {pq} != {q}")
    for item in parsed:
        if item not in truth:
            mism += 1
            print(f"    FAIL {item} in CSV absent from truth")
            fails.append(f"{item} extra in CSV")
    print(f"  CSV rows: {len(parsed)} | truth: {len(truth)} | mismatches: {mism}")
    if mism == 0:
        print("  OK — exported CSV exactly matches hierarchy-derived truth")
    return fails


def _resolve(url):
    if not url:
        return None
    if url.startswith("/private/files/"):
        return frappe.get_site_path("private", "files", url.replace("/private/files/", ""))
    if url.startswith("/files/"):
        return frappe.get_site_path("public", "files", url.replace("/files/", ""))
    return None
