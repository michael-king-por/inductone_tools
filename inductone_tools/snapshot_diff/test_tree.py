import sys
sys.path.insert(0, "/home/claude/diff_tool")

from inductone_tools.snapshot_diff.schema import SnapshotNode
from inductone_tools.snapshot_diff.tree import (
    diff_snapshots_tree, flatten_tree, CHANGED
)
from inductone_tools.snapshot_diff.engine import (
    ADDED, REMOVED, QTY_CHANGED, REVISION_CHANGED, UNCHANGED
)


def node(node_id, item_code, qty=1.0, bom_used="", parent_node_id=None,
         item_name="", excluded=False, bom_level=1):
    return SnapshotNode(
        node_id=node_id, parent_node_id=parent_node_id, bom_level=bom_level,
        item_code=item_code, item_name=item_name or item_code, item_group="Test",
        description="", qty=qty, uom="Nos", bom_used=bom_used, node_type="Leaf",
        is_leaf=True, effect_origin="BASELINE", source_option_code="",
        excluded=excluded, source_bom=bom_used, balloon_numbers="",
        electrical_unit="", source_electrical_bom_rev="",
    )


nodes_a = [
    node("a1", "TOP", qty=1, bom_used="BOM-TOP-003", bom_level=0),
    node("a4", "2000010", qty=1, bom_used="BOM-TOP-003", parent_node_id="a1", bom_level=1),
    node("a2", "1000001", qty=2, bom_used="BOM-2000010-002", parent_node_id="a4", bom_level=2),
    node("a3", "1000002", qty=1, bom_used="BOM-2000010-002", parent_node_id="a4", bom_level=2),
    node("a5", "1000099", qty=5, bom_used="BOM-TOP-003", parent_node_id="a1", bom_level=1),
]

nodes_b = [
    node("b1", "TOP", qty=1, bom_used="BOM-TOP-004", bom_level=0),
    node("b4", "2000010", qty=1, bom_used="BOM-TOP-004", parent_node_id="b1", bom_level=1),
    node("b2", "1000001", qty=2, bom_used="BOM-2000010-003", parent_node_id="b4", bom_level=2),  # rev change
    node("b3", "1000002", qty=4, bom_used="BOM-2000010-003", parent_node_id="b4", bom_level=2),  # qty + rev
    node("b8", "1000300", qty=1, bom_used="BOM-2000010-003", parent_node_id="b4", bom_level=2),  # added under sub-asm
    # 1000099 removed
]

print("=" * 78)
print("FULL TREE (context) MODE")
print("=" * 78)
res = diff_snapshots_tree(nodes_a, nodes_b, "SNAP-A", "SNAP-B", changes_only=False)
for n in flatten_tree(res):
    indent = "    " * n.bom_level
    marker = {"ADDED": "+", "REMOVED": "-", "CHANGED": "~", "UNCHANGED": " "}[n.status]
    print(f"{marker} {indent}{n.item_code:14} [{n.status:9}] {n.note}")
print(f"\nAdded={res.added} Removed={res.removed} Changed={res.changed} Unchanged={res.unchanged}")

print()
print("=" * 78)
print("CHANGES-ONLY MODE (ancestors kept for context)")
print("=" * 78)
res2 = diff_snapshots_tree(nodes_a, nodes_b, "SNAP-A", "SNAP-B", changes_only=True)
for n in flatten_tree(res2):
    indent = "    " * n.bom_level
    marker = {"ADDED": "+", "REMOVED": "-", "CHANGED": "~", "UNCHANGED": " "}[n.status]
    print(f"{marker} {indent}{n.item_code:14} [{n.status:9}] {n.note}")

# Assertions
flat = {n.item_code: n for n in flatten_tree(res)}
assert flat["TOP"].status == CHANGED, "TOP rev changed"
assert flat["1000001"].status == CHANGED and REVISION_CHANGED in flat["1000001"].categories
assert flat["1000002"].status == CHANGED and QTY_CHANGED in flat["1000002"].categories and REVISION_CHANGED in flat["1000002"].categories
assert flat["1000099"].status == REMOVED
assert flat["1000300"].status == ADDED

# Changes-only must keep TOP and 2000010 (ancestors of changes) but drop nothing with a change
flat2 = {n.item_code: n for n in flatten_tree(res2)}
assert "TOP" in flat2 and "2000010" in flat2, "ancestors of changes must remain"
assert "1000300" in flat2, "added node must remain"

print("\nALL TREE ASSERTIONS PASSED")