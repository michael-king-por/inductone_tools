"""
================================================================================
 HIERARCHICAL (TREE) DIFF MODE
================================================================================

The engine.py module produces the FLAT procurement diff -- every part rolled
up to one identity-keyed line. This module produces the HIERARCHICAL diff -- a
unified merged tree that walks the complete BOM structure and tags each node in
its structural position as added / removed / changed / unchanged, like a
unified git diff with context.

TWO AUDIENCES, TWO VIEWS, ONE COMPARISON
----------------------------------------
  Flat procurement diff (engine.py):
      audience = procurement / builder buying parts
      "you need 3 more of X, you no longer need Y, Z is a new revision"
      hierarchy irrelevant; quantities rolled up.

  Hierarchical diff (this module):
      audience = engineering following assembly structure
      "under this sub-assembly, at this node, this changed"
      structure preserved; reads like a unified diff down the tree.

ALIGNMENT MODEL (unified merged tree)
-------------------------------------
We build a single merged tree keyed by structural PATH (the chain of item codes
from root to node), not by identity alone. Each merged node carries an A-side
and a B-side occurrence if present, and a per-node status:

  ADDED       node path exists only in B
  REMOVED     node path exists only in A
  CHANGED     node path in both, but qty and/or revision differs
  UNCHANGED   node path in both, identical qty and revision

A node is rendered once, at its structural position, with its status. Children
are walked recursively. "Changes only" mode prunes any subtree that contains no
change (but always keeps ancestors of a change so the path to it is visible --
exactly like git showing the enclosing function/section of a hunk).
================================================================================
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import OrderedDict

from .schema import SnapshotNode, node_revision
from .engine import ADDED, REMOVED, QTY_CHANGED, REVISION_CHANGED, MOVED, USER_NOTES_CHANGED, UNCHANGED

CHANGED = "CHANGED"  # composite status for a node that differs in place


@dataclass
class TreeDiffNode:
    """One node in the unified merged tree."""
    path: Tuple[str, ...]              # structural path of item codes, root..self
    item_code: str
    item_name: str
    item_group: str
    bom_level: int
    status: str                        # ADDED | REMOVED | CHANGED | UNCHANGED
    categories: List[str] = field(default_factory=list)  # finer-grained tags

    a_qty: Optional[float] = None
    b_qty: Optional[float] = None
    a_revision: Optional[str] = None
    b_revision: Optional[str] = None
    a_bom: Optional[str] = None
    b_bom: Optional[str] = None
    a_user_notes: Optional[str] = None
    b_user_notes: Optional[str] = None
    uom: str = ""
    note: str = ""

    children: List["TreeDiffNode"] = field(default_factory=list)

    @property
    def subtree_has_change(self) -> bool:
        if self.status != UNCHANGED:
            return True
        return any(c.subtree_has_change for c in self.children)


@dataclass
class TreeDiffResult:
    snapshot_a: str
    snapshot_b: str
    schema_version: str
    roots: List[TreeDiffNode] = field(default_factory=list)
    added: int = 0
    removed: int = 0
    changed: int = 0
    unchanged: int = 0

    @property
    def total_changes(self) -> int:
        return self.added + self.removed + self.changed


def _build_path_map(nodes: List[SnapshotNode]) -> "OrderedDict[Tuple[str,...], dict]":
    """
    Build an ordered map of structural-path -> aggregated node info.

    The path is the chain of item codes from root to the node, derived by
    walking parent_node_id links. Excluded rows are skipped (suppressed by a
    structural effect -- not part of the delivered config).

    Duplicate identical paths (same part under same parent, multiple
    occurrences) are aggregated: quantities summed, first occurrence's
    metadata kept.
    """
    by_node_id = {n.node_id: n for n in nodes}

    def path_for(n: SnapshotNode) -> Tuple[str, ...]:
        chain = []
        seen = set()
        cur = n
        while cur is not None:
            if cur.node_id in seen:  # cycle guard
                break
            seen.add(cur.node_id)
            chain.append(cur.item_code)
            if not cur.parent_node_id:
                break
            cur = by_node_id.get(cur.parent_node_id)
        return tuple(reversed(chain))

    path_map: "OrderedDict[Tuple[str,...], dict]" = OrderedDict()
    for n in nodes:
        if n.excluded or not n.item_code:
            continue
        p = path_for(n)
        if p in path_map:
            entry = path_map[p]
            entry["qty"] += n.qty
            entry["revisions"].add(node_revision(n))
            entry["boms"].add(n.bom_used or n.source_bom)
            if (n.user_notes or "").strip():
                entry["user_notes"].add((n.user_notes or "").strip())
        else:
            path_map[p] = {
                "path": p,
                "item_code": n.item_code,
                "item_name": n.item_name,
                "item_group": n.item_group,
                "bom_level": n.bom_level,
                "qty": n.qty,
                "uom": n.uom,
                "revisions": {node_revision(n)},
                "boms": {n.bom_used or n.source_bom},
                "user_notes": {(n.user_notes or "").strip()} if (n.user_notes or "").strip() else set(),
            }
    return path_map


def _rev_str(revs: set) -> str:
    clean = sorted(r for r in revs if r)
    return ", ".join(clean)


def _bom_str(boms: set) -> str:
    clean = sorted(b for b in boms if b)
    return ", ".join(clean)


def _notes_str(notes: set) -> str:
    clean = sorted(n for n in notes if n)
    return " | ".join(clean)


def diff_snapshots_tree(
    nodes_a: List[SnapshotNode],
    nodes_b: List[SnapshotNode],
    snapshot_a_name: str,
    snapshot_b_name: str,
    changes_only: bool = False,
) -> TreeDiffResult:
    """
    Produce the unified merged tree diff.

    changes_only=False -> full tree, changes highlighted in context.
    changes_only=True  -> prune subtrees with no change, keeping ancestors of
                          changes so the path to each change stays visible.
    """
    from .schema import SNAPSHOT_SCHEMA_VERSION

    pa = _build_path_map(nodes_a)
    pb = _build_path_map(nodes_b)

    all_paths = list(OrderedDict.fromkeys(list(pa.keys()) + list(pb.keys())))

    result = TreeDiffResult(
        snapshot_a=snapshot_a_name,
        snapshot_b=snapshot_b_name,
        schema_version=SNAPSHOT_SCHEMA_VERSION,
    )

    # Build a flat dict of path -> TreeDiffNode first, then assemble parent/child.
    nodes_by_path: Dict[Tuple[str, ...], TreeDiffNode] = {}

    for path in all_paths:
        a = pa.get(path)
        b = pb.get(path)
        ref = b or a

        tdn = TreeDiffNode(
            path=path,
            item_code=ref["item_code"],
            item_name=ref["item_name"],
            item_group=ref["item_group"],
            bom_level=ref["bom_level"],
            status=UNCHANGED,
            uom=ref["uom"],
        )

        if a:
            tdn.a_qty = a["qty"]
            tdn.a_revision = _rev_str(a["revisions"])
            tdn.a_bom = _bom_str(a["boms"])
            tdn.a_user_notes = _notes_str(a["user_notes"])
        if b:
            tdn.b_qty = b["qty"]
            tdn.b_revision = _rev_str(b["revisions"])
            tdn.b_bom = _bom_str(b["boms"])
            tdn.b_user_notes = _notes_str(b["user_notes"])

        if a and not b:
            tdn.status = REMOVED
            tdn.categories = [REMOVED]
            tdn.note = "In previous build, not in this one — do not include."
            result.removed += 1
        elif b and not a:
            tdn.status = ADDED
            tdn.categories = [ADDED]
            tdn.note = "New in this build — must be added."
            result.added += 1
        else:
            cats = []
            if a["revisions"] != b["revisions"] and (any(a["revisions"]) or any(b["revisions"])):
                cats.append(REVISION_CHANGED)
            if abs(a["qty"] - b["qty"]) > 1e-9:
                cats.append(QTY_CHANGED)
            if _notes_str(a["user_notes"]) != _notes_str(b["user_notes"]):
                cats.append(USER_NOTES_CHANGED)
            if cats:
                tdn.status = CHANGED
                tdn.categories = cats
                notes = []
                if REVISION_CHANGED in cats:
                    notes.append("Revision {0} → {1}".format(_rev_str(a["revisions"]) or "(none)", _rev_str(b["revisions"]) or "(none)"))
                if QTY_CHANGED in cats:
                    notes.append("Qty {0} → {1}".format(_fmt(a["qty"]), _fmt(b["qty"])))
                if USER_NOTES_CHANGED in cats:
                    notes.append("User notes changed")
                tdn.note = "; ".join(notes)
                result.changed += 1
            else:
                tdn.status = UNCHANGED
                tdn.categories = [UNCHANGED]
                result.unchanged += 1

        nodes_by_path[path] = tdn

    # Assemble parent/child by path prefix.
    roots: List[TreeDiffNode] = []
    for path, tdn in nodes_by_path.items():
        if len(path) <= 1:
            roots.append(tdn)
            continue
        parent_path = path[:-1]
        parent = nodes_by_path.get(parent_path)
        if parent:
            parent.children.append(tdn)
        else:
            # Parent path not present (shouldn't happen for well-formed trees);
            # surface at root rather than dropping.
            roots.append(tdn)

    # Prune for changes-only mode.
    if changes_only:
        def prune(node: TreeDiffNode) -> bool:
            node.children = [c for c in node.children if prune(c)]
            return node.subtree_has_change
        roots = [r for r in roots if prune(r)]

    result.roots = roots
    return result


def flatten_tree(result: TreeDiffResult) -> List[TreeDiffNode]:
    """Depth-first flatten for tabular rendering (report rows / XLSX rows)."""
    out: List[TreeDiffNode] = []

    def walk(node: TreeDiffNode):
        out.append(node)
        for c in node.children:
            walk(c)

    for r in result.roots:
        walk(r)
    return out


def _fmt(q):
    if q is None:
        return "—"
    if abs(q - round(q)) < 1e-9:
        return str(int(round(q)))
    return "{0:.3f}".format(q).rstrip("0").rstrip(".")
