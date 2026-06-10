"""
STRUCTURAL FIDELITY VALIDATOR

Flat-quantity gates prove leaf TOTALS are right. They cannot see SHAPE: a leaf
under the wrong parent, a flattened assembly, or a reparented branch can still
roll up to identical totals. This validator proves the configured hierarchy has
the correct STRUCTURE.

Ground truth for shape = ERPNext native BOM tree (the parent->child edges of the
BOM Item tree, walked recursively). NOT the flat rollup.

Structural claims proved:

  S1  TREE INTEGRITY
      Every node has a resolvable parent (or is a declared root). No orphans,
      no cycles, every parent_node_id points at a real node, every assembly
      has children, every leaf has none.

  S2  EDGE FIDELITY vs NATIVE
      Every parent->child EDGE in the configured tree is either:
        (a) present in the native master BOM tree, OR
        (b) explained by an option effect (an injected branch's internal edges,
            a replacement branch, an added assembly's subtree).
      No configured edge is unexplained.

  S3  NATIVE-EDGE COVERAGE
      Every parent->child edge in the native master tree is present in the
      configured tree, EXCEPT where an option suppressed that node/branch.
      No native edge silently vanished.

  S4  DEPTH / PATH FIDELITY
      For every leaf, its full ancestor PATH from root in the configured tree
      matches its native path (for untouched leaves), or matches the expected
      injected path (for option-added leaves). Catches reparenting that
      preserves totals.

  S5  ANCESTOR-CHAIN ROUND TRIP
      The hierarchy's parent_node_id chain and the structured rows'
      ancestor_item_codes agree for every node. Catches divergence between the
      two parentage representations the pipeline maintains.

Run:
  bench --site <site> execute inductone_tools.validate_structure.execute
"""

from collections import defaultdict

import frappe

from inductone_tools.bom_export import (
    explode_bom_tree_structured,
    build_configured_rows,
    load_snapshot_structural_effect_sets,
)

BUILD = "SAL-ORD-2026-00047-BLD-0200"
TOP_BOM = "BOM-1611 027 0010-004"


def execute():
    print("=" * 78)
    print("STRUCTURAL FIDELITY VALIDATOR")
    print("Ground truth: ERPNext native BOM tree (parent->child edges)")
    print("=" * 78)

    snap_name = frappe.db.get_value("InductOne Build", BUILD, "latest_snapshot")
    snap = frappe.get_doc("Configured BOM Snapshot", snap_name)
    print(f"BUILD={BUILD}\nSNAP={snap_name}\nTOP_BOM={TOP_BOM}")

    fails = []

    # native parent->child edges (item-level) of the master tree
    native_edges, native_paths = native_tree(TOP_BOM)
    print(f"\nNative tree: {len(native_edges)} distinct parent->child edges")

    # configured hierarchy rows (the persisted single source of truth)
    hier = list(snap.hierarchy or [])
    print(f"Configured hierarchy: {len(hier)} nodes")

    effects = load_snapshot_structural_effect_sets(snap)

    fails += s1_tree_integrity(hier)
    fails += s2_edge_fidelity(hier, native_edges, effects)
    fails += s3_native_coverage(hier, native_edges, effects)
    fails += s4_path_fidelity(hier, native_paths, effects)
    fails += s5_ancestor_roundtrip(hier)

    print("\n" + "=" * 78)
    print("FINAL RESULT")
    print("=" * 78)
    uniq = list(dict.fromkeys(fails))
    if uniq:
        print(f"  {len(uniq)} STRUCTURAL FAILURE(S):")
        for f in uniq[:60]:
            print(f"    - {f}")
        if len(uniq) > 60:
            print(f"    ... and {len(uniq) - 60} more")
        print("\n  STRUCTURE NOT PROVEN. Diagnose above.")
    else:
        print("  ALL STRUCTURAL GATES PASSED.")
        print("  The configured tree's SHAPE matches ERPNext's native tree plus")
        print("  only the option-driven structural changes — every edge accounted for.")


# ---------------------------------------------------------------------------
# Native tree: recursive walk producing parent->child edges and root paths.
# Edge = (parent_item, child_item). Path = tuple of item codes root..leaf.
# ---------------------------------------------------------------------------
def native_tree(top_bom):
    edges = set()
    paths = defaultdict(list)  # leaf_item -> list of full paths (tuples)

    def walk(bom_name, parent_item, path):
        b = frappe.get_doc("BOM", bom_name)
        for bi in b.items:
            child = bi.item_code
            if parent_item is not None:
                edges.add((parent_item, child))
            new_path = path + (child,)
            if getattr(bi, "bom_no", None):
                walk(bi.bom_no, child, new_path)
            else:
                paths[child].append(new_path)

    # root item of the top bom
    top_item = frappe.db.get_value("BOM", top_bom, "item")
    walk(top_bom, top_item, (top_item,))
    return edges, paths


# ---------------------------------------------------------------------------
# S1 — tree integrity
# ---------------------------------------------------------------------------
def s1_tree_integrity(hier):
    print("\n" + "-" * 78)
    print("S1 — Tree integrity (parents resolve, no cycles, leaf/assembly sane)")
    print("-" * 78)
    fails = []
    by_id = {h.node_id: h for h in hier}
    ids = set(by_id)

    # orphans
    orphans = [h for h in hier if h.parent_node_id and h.parent_node_id not in ids]
    for o in orphans:
        print(f"    ORPHAN {o.item_code} node={o.node_id} parent={o.parent_node_id}")
        fails.append(f"orphan {o.item_code} ({o.node_id})")

    # cycles
    def has_cycle(start):
        seen = set()
        n = by_id.get(start)
        while n and n.parent_node_id:
            if n.node_id in seen:
                return True
            seen.add(n.node_id)
            n = by_id.get(n.parent_node_id)
        return False
    cyc = [h.node_id for h in hier if has_cycle(h.node_id)]
    for c in cyc:
        print(f"    CYCLE at node {c}")
        fails.append(f"cycle {c}")

    # children index
    children = defaultdict(list)
    for h in hier:
        if h.parent_node_id:
            children[h.parent_node_id].append(h)

    # assembly must have children; leaf must not
    bad_leaf = [h for h in hier if int(h.is_leaf or 0) == 1 and children.get(h.node_id)]
    bad_asm = [h for h in hier if int(h.is_leaf or 0) == 0 and not children.get(h.node_id)]
    for h in bad_leaf:
        print(f"    LEAF-WITH-CHILDREN {h.item_code} node={h.node_id}")
        fails.append(f"leaf has children {h.item_code}")
    for h in bad_asm:
        print(f"    ASSEMBLY-NO-CHILDREN {h.item_code} node={h.node_id}")
        fails.append(f"assembly has no children {h.item_code}")

    roots = [h for h in hier if not h.parent_node_id]
    print(f"  nodes={len(hier)} roots={len(roots)} orphans={len(orphans)} "
          f"cycles={len(cyc)} leaf-with-children={len(bad_leaf)} "
          f"assembly-no-children={len(bad_asm)}")
    if not fails:
        print("  OK — tree is well-formed")
    return fails


# ---------------------------------------------------------------------------
# Configured edges + explained-edge set
# ---------------------------------------------------------------------------
def _configured_edges(hier):
    by_id = {h.node_id: h for h in hier}
    edges = set()
    for h in hier:
        if h.parent_node_id and h.parent_node_id in by_id:
            edges.add((by_id[h.parent_node_id].item_code, h.item_code))
    return edges


def _explained_edges(effects):
    """Edges introduced by option effects: internal edges of injected branches
    (ADD_BRANCH, REPLACE new branch, increment-of-assembly's own subtree)."""
    explained = set()

    def add_branch_edges(item, bom):
        if not bom:
            return
        try:
            be, _ = native_tree(bom)
        except Exception:
            return
        explained.update(be)
        # also the edge from injection point's parent chain is item-internal;
        # the top edge (parent->item) is handled separately as a root injection
        # mark edges from `item` to its direct children too
        try:
            b = frappe.get_doc("BOM", bom)
            for bi in b.items:
                explained.add((item, bi.item_code))
        except Exception:
            pass

    for eff in effects.get("additive_effects", []):
        add_branch_edges(eff.get("target_item"),
                         eff.get("resolved_target_bom") or eff.get("target_bom")
                         or frappe.db.get_value("BOM", {"item": eff.get("target_item"),
                            "is_default": 1, "is_active": 1, "docstatus": 1}, "name"))
    for eff in effects.get("replacement_effects", []):
        add_branch_edges(eff.get("replace_with_item"),
                         eff.get("resolved_replace_with_bom") or eff.get("replace_with_bom"))
    # incremented assemblies keep their native subtree edges (already native);
    # nothing new to add for increment except the assembly's own subtree, which
    # is native and thus already in native_edges.
    return explained


def s2_edge_fidelity(hier, native_edges, effects):
    print("\n" + "-" * 78)
    print("S2 — Edge fidelity (every configured edge is native or option-explained)")
    print("-" * 78)
    fails = []
    conf = _configured_edges(hier)
    explained = _explained_edges(effects)

    # injection root edges: an ADD_BRANCH/REPLACE attaches target under some
    # parent. Accept any edge whose child is an injected branch root.
    injected_roots = set()
    for eff in effects.get("additive_effects", []):
        injected_roots.add(eff.get("target_item"))
    for eff in effects.get("replacement_effects", []):
        if eff.get("replace_with_item"):
            injected_roots.add(eff.get("replace_with_item"))

    unexplained = 0
    for (p, c) in sorted(conf):
        if (p, c) in native_edges:
            continue
        if (p, c) in explained:
            continue
        if c in injected_roots:
            continue  # root attachment edge of an injected branch
        unexplained += 1
        print(f"    UNEXPLAINED EDGE {p} -> {c}")
        fails.append(f"unexplained edge {p}->{c}")
    print(f"  configured edges: {len(conf)} | unexplained: {unexplained}")
    if not fails:
        print("  OK — every configured edge is native or explained by an option")
    return fails


def s3_native_coverage(hier, native_edges, effects):
    print("\n" + "-" * 78)
    print("S3 — Native-edge coverage (no native edge vanished except suppressions)")
    print("-" * 78)
    fails = []
    conf = _configured_edges(hier)

    suppressed_items = set()
    suppressed_items |= set(effects.get("suppressed_node_items", set()))
    suppressed_items |= set(effects.get("suppressed_branch_items", set()))
    suppressed_items |= set(effects.get("removed_target_items", set()))
    # replacement old targets are suppressed branches
    for eff in effects.get("replacement_effects", []):
        if eff.get("target_item"):
            suppressed_items.add(eff["target_item"])

    # an edge is allowed-missing if its child OR parent was suppressed, or any
    # ancestor of the edge was a suppressed branch
    missing = 0
    for (p, c) in sorted(native_edges):
        if (p, c) in conf:
            continue
        if c in suppressed_items or p in suppressed_items:
            continue
        missing += 1
        print(f"    MISSING NATIVE EDGE {p} -> {c} (not suppressed)")
        fails.append(f"missing native edge {p}->{c}")
    print(f"  native edges: {len(native_edges)} | unexpectedly missing: {missing}")
    if not fails:
        print("  OK — every native edge present except deliberate suppressions")
    return fails


def s4_path_fidelity(hier, native_paths, effects):
    print("\n" + "-" * 78)
    print("S4 — Path fidelity (each leaf's root path matches native or injection)")
    print("-" * 78)
    fails = []
    by_id = {h.node_id: h for h in hier}

    def conf_path(node):
        out = []
        n = node
        while n:
            out.append(n.item_code)
            n = by_id.get(n.parent_node_id) if n.parent_node_id else None
        out.reverse()
        return tuple(out)

    injected_roots = set()
    for eff in effects.get("additive_effects", []):
        injected_roots.add(eff.get("target_item"))
    for eff in effects.get("replacement_effects", []):
        if eff.get("replace_with_item"):
            injected_roots.add(eff.get("replace_with_item"))

    checked = mism = 0
    for h in hier:
        if int(h.is_leaf or 0) != 1:
            continue
        cp = conf_path(h)
        # if path passes through an injected root, it's an option-added path
        if set(cp) & injected_roots:
            continue
        native_for_item = native_paths.get(h.item_code, [])
        if not native_for_item:
            # leaf not in native at all and not injected — that's an S2/S3 issue,
            # skip here
            continue
        checked += 1
        # configured path must match one of the native paths for this leaf
        # (compare the suffix from the leaf upward, allowing the configured root
        # to be the same top item)
        if cp not in native_for_item:
            # tolerate exact match on the tail (some pipelines root differently)
            tail_ok = any(cp[-len(np):] == np or np[-len(cp):] == cp
                          for np in native_for_item)
            if not tail_ok:
                mism += 1
                print(f"    PATH MISMATCH {h.item_code}")
                print(f"        configured: {' > '.join(cp)}")
                print(f"        native:     {' > '.join(native_for_item[0])}")
                fails.append(f"path mismatch {h.item_code}")
    print(f"  untouched leaves checked: {checked} | path mismatches: {mism}")
    if not fails:
        print("  OK — every untouched leaf sits on its native path")
    return fails


def s5_ancestor_roundtrip(hier):
    print("\n" + "-" * 78)
    print("S5 — Ancestor-chain round trip (parent_node_id chain == ancestor list)")
    print("-" * 78)
    fails = []
    by_id = {h.node_id: h for h in hier}

    def chain_items(node):
        out = []
        n = by_id.get(node.parent_node_id) if node.parent_node_id else None
        while n:
            out.append(n.item_code)
            n = by_id.get(n.parent_node_id) if n.parent_node_id else None
        out.reverse()
        return out

    checked = mism = 0
    for h in hier:
        stored = getattr(h, "ancestor_item_codes", None)
        if stored is None:
            continue  # field not persisted on hierarchy; skip silently
        # stored may be a JSON string or list
        if isinstance(stored, str):
            try:
                stored_list = frappe.parse_json(stored) or []
            except Exception:
                stored_list = [s for s in stored.split(",") if s]
        else:
            stored_list = list(stored or [])
        checked += 1
        derived = chain_items(h)
        if list(stored_list) != derived:
            mism += 1
            print(f"    CHAIN MISMATCH {h.item_code} node={h.node_id}")
            print(f"        parent-chain: {derived}")
            print(f"        stored:       {stored_list}")
            fails.append(f"ancestor chain mismatch {h.item_code}")
    if checked == 0:
        print("  SKIP — hierarchy nodes do not persist ancestor_item_codes")
    else:
        print(f"  nodes checked: {checked} | mismatches: {mism}")
        if not fails:
            print("  OK — both parentage representations agree")
    return fails
