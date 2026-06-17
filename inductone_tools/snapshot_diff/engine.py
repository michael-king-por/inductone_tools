"""
================================================================================
 SNAPSHOT DIFF ENGINE
================================================================================

Compares two Configured BOM Snapshots line by line and categorizes every
difference. Pure logic -- no Frappe imports, no I/O. Takes normalized
SnapshotNode lists in, produces a structured DiffResult out. This makes it
unit-testable in isolation and keeps the ERPNext coupling confined to
schema.py and the report/loader layers.

THE PURPOSE (why this tool exists)
----------------------------------
A builder built a machine months ago. They are about to build another. They
will lean on muscle memory from last time. Most of that memory is correct and
valuable -- re-deriving it would waste money. But some of it is now WRONG,
because the configuration changed. This engine isolates exactly the parts of
their memory that must be amended: every part added, removed, re-quantified,
re-revisioned, or relocated between the two builds. Nothing more, nothing less.

DIFFERENCE CATEGORIES
---------------------
  ADDED            present in B, absent in A
  REMOVED          present in A, absent in B
  QTY_CHANGED      same part, different quantity
  REVISION_CHANGED same part, different BOM revision (bom_used token differs)
  MOVED            same part, different parent assembly in the tree
  UNCHANGED        same part, same qty, same revision, same parent (suppressed
                   from the headline diff but available for full-context output)

A single part can carry more than one change flag (e.g. qty AND revision). The
engine records all that apply rather than forcing one bucket.
================================================================================
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from .schema import (
    SnapshotNode,
    node_revision,
    revision_identity,
    SNAPSHOT_SCHEMA_VERSION,
)


# Change category constants
ADDED = "ADDED"
REMOVED = "REMOVED"
QTY_CHANGED = "QTY_CHANGED"
REVISION_CHANGED = "REVISION_CHANGED"
MOVED = "MOVED"
UNCHANGED = "UNCHANGED"


@dataclass
class DiffLine:
    """One line of the diff -- one part, with whatever changed about it."""
    item_code: str
    item_name: str
    item_group: str
    categories: List[str] = field(default_factory=list)

    # Side A (the older / reference snapshot)
    a_qty: Optional[float] = None
    a_revision: Optional[str] = None
    a_bom: Optional[str] = None
    a_parent: Optional[str] = None
    a_uom: Optional[str] = None

    # Side B (the newer / target snapshot)
    b_qty: Optional[float] = None
    b_revision: Optional[str] = None
    b_bom: Optional[str] = None
    b_parent: Optional[str] = None
    b_uom: Optional[str] = None

    # Convenience for the human reading the diff
    note: str = ""

    @property
    def is_change(self) -> bool:
        return bool(self.categories) and self.categories != [UNCHANGED]

    @property
    def primary_category(self) -> str:
        """The most operationally significant category, for sorting/coloring."""
        order = [REMOVED, ADDED, REVISION_CHANGED, QTY_CHANGED, MOVED, UNCHANGED]
        for cat in order:
            if cat in self.categories:
                return cat
        return UNCHANGED


@dataclass
class DiffResult:
    snapshot_a: str
    snapshot_b: str
    schema_version: str
    lines: List[DiffLine] = field(default_factory=list)

    # Summary counts
    added: int = 0
    removed: int = 0
    qty_changed: int = 0
    revision_changed: int = 0
    moved: int = 0
    unchanged: int = 0

    @property
    def total_changes(self) -> int:
        return self.added + self.removed + self.qty_changed + self.revision_changed + self.moved

    def changed_lines(self) -> List[DiffLine]:
        return [ln for ln in self.lines if ln.is_change]


def _index_by_part(nodes: List[SnapshotNode]) -> Dict[str, List[SnapshotNode]]:
    """
    Group nodes by part identity. A part can legitimately appear more than once
    in a tree (same component under different assemblies), so each identity maps
    to a LIST of nodes. We aggregate qty across occurrences for the headline
    quantity comparison, but retain occurrences for move detection.
    """
    index: Dict[str, List[SnapshotNode]] = defaultdict(list)
    for n in nodes:
        # Excluded rows were suppressed by a structural effect -- they are not
        # part of the delivered configuration, so they never count in the diff.
        if n.excluded:
            continue
        if not n.item_code:
            continue
        index[revision_identity(n.item_code)].append(n)
    return index


def _aggregate_qty(nodes: List[SnapshotNode]) -> float:
    return sum(n.qty for n in nodes)


def _representative(nodes: List[SnapshotNode]) -> SnapshotNode:
    """Pick a stable representative node for display (lowest bom_level first)."""
    return sorted(nodes, key=lambda n: (n.bom_level, n.node_id))[0]


def _revisions(nodes: List[SnapshotNode]) -> str:
    """Distinct revisions across occurrences, joined for display."""
    revs = sorted({node_revision(n) for n in nodes if node_revision(n)})
    return ", ".join(revs)


def _boms(nodes: List[SnapshotNode]) -> str:
    boms = sorted({(n.bom_used or n.source_bom) for n in nodes if (n.bom_used or n.source_bom)})
    return ", ".join(boms)


def _parents(nodes: List[SnapshotNode], parent_lookup: Dict[str, str]) -> set:
    """The set of parent item codes this part sits under."""
    parents = set()
    for n in nodes:
        pcode = parent_lookup.get(n.parent_node_id or "", "") if n.parent_node_id else ""
        parents.add(pcode)
    return parents


def diff_snapshots(
    nodes_a: List[SnapshotNode],
    nodes_b: List[SnapshotNode],
    snapshot_a_name: str,
    snapshot_b_name: str,
    include_unchanged: bool = False,
) -> DiffResult:
    """
    Core diff. A is the older/reference snapshot, B is the newer/target.

    Returns a DiffResult with one DiffLine per part identity that appears in
    either snapshot, each tagged with the categories that apply.
    """
    index_a = _index_by_part(nodes_a)
    index_b = _index_by_part(nodes_b)

    # node_id -> item_code lookups, for resolving parent relationships to codes
    parent_lookup_a = {n.node_id: n.item_code for n in nodes_a}
    parent_lookup_b = {n.node_id: n.item_code for n in nodes_b}

    all_parts = sorted(set(index_a.keys()) | set(index_b.keys()))

    result = DiffResult(
        snapshot_a=snapshot_a_name,
        snapshot_b=snapshot_b_name,
        schema_version=SNAPSHOT_SCHEMA_VERSION,
    )

    for part in all_parts:
        in_a = part in index_a
        in_b = part in index_b
        a_nodes = index_a.get(part, [])
        b_nodes = index_b.get(part, [])

        rep = _representative(b_nodes if in_b else a_nodes)

        line = DiffLine(
            item_code=rep.item_code,
            item_name=rep.item_name,
            item_group=rep.item_group,
        )

        if in_a:
            line.a_qty = _aggregate_qty(a_nodes)
            line.a_revision = _revisions(a_nodes)
            line.a_bom = _boms(a_nodes)
            line.a_uom = rep.uom
            line.a_parent = ", ".join(sorted(p for p in _parents(a_nodes, parent_lookup_a) if p)) or "(top)"
        if in_b:
            line.b_qty = _aggregate_qty(b_nodes)
            line.b_revision = _revisions(b_nodes)
            line.b_bom = _boms(b_nodes)
            line.b_uom = rep.uom
            line.b_parent = ", ".join(sorted(p for p in _parents(b_nodes, parent_lookup_b) if p)) or "(top)"

        # ---- categorize ----
        if in_a and not in_b:
            line.categories.append(REMOVED)
            line.note = "Present in the previous build; NOT in this one. Do not include."
            result.removed += 1

        elif in_b and not in_a:
            line.categories.append(ADDED)
            line.note = "NEW in this build; was not in the previous one. Must be added."
            result.added += 1

        else:
            # Present in both -- check qty, revision, and placement.
            changed = False

            # Revision change (parsed from BOM token)
            rev_a = set(node_revision(n) for n in a_nodes if node_revision(n))
            rev_b = set(node_revision(n) for n in b_nodes if node_revision(n))
            if rev_a != rev_b and (rev_a or rev_b):
                line.categories.append(REVISION_CHANGED)
                result.revision_changed += 1
                changed = True

            # Qty change (aggregate across occurrences)
            if abs((line.a_qty or 0) - (line.b_qty or 0)) > 1e-9:
                line.categories.append(QTY_CHANGED)
                result.qty_changed += 1
                changed = True

            # Structural move (different set of parent assemblies)
            parents_a = {p for p in _parents(a_nodes, parent_lookup_a) if p}
            parents_b = {p for p in _parents(b_nodes, parent_lookup_b) if p}
            if parents_a != parents_b:
                line.categories.append(MOVED)
                result.moved += 1
                changed = True

            if not changed:
                line.categories.append(UNCHANGED)
                result.unchanged += 1
            else:
                notes = []
                if REVISION_CHANGED in line.categories:
                    notes.append(
                        "Revision changed {0} -> {1}".format(
                            ", ".join(sorted(rev_a)) or "(none)",
                            ", ".join(sorted(rev_b)) or "(none)",
                        )
                    )
                if QTY_CHANGED in line.categories:
                    notes.append(
                        "Qty changed {0} -> {1}".format(line.a_qty, line.b_qty)
                    )
                if MOVED in line.categories:
                    notes.append("Moved to a different assembly")
                line.note = "; ".join(notes)

        if line.is_change or include_unchanged:
            result.lines.append(line)

    # Sort: changes first by significance, then by item code
    sig = {REMOVED: 0, ADDED: 1, REVISION_CHANGED: 2, QTY_CHANGED: 3, MOVED: 4, UNCHANGED: 5}
    result.lines.sort(key=lambda ln: (sig.get(ln.primary_category, 9), ln.item_code))

    return result