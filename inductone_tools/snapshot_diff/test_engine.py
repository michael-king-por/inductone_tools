"""
Standalone validation of the diff engine. No Frappe required.
Builds two synthetic snapshots and verifies every diff category fires correctly.
"""
import sys
sys.path.insert(0, "/home/claude/diff_tool")

from inductone_tools.snapshot_diff.schema import SnapshotNode
from inductone_tools.snapshot_diff.engine import (
    diff_snapshots, ADDED, REMOVED, QTY_CHANGED, REVISION_CHANGED, MOVED, USER_NOTES_CHANGED, UNCHANGED
)


def node(node_id, item_code, qty=1.0, bom_used="", parent_node_id=None,
         item_name="", excluded=False, bom_level=1, user_notes=""):
    return SnapshotNode(
        node_id=node_id, parent_node_id=parent_node_id, bom_level=bom_level,
        item_code=item_code, item_name=item_name or item_code, item_group="Test",
        description="", qty=qty, uom="Nos", bom_used=bom_used, node_type="Leaf",
        is_leaf=True, effect_origin="BASELINE", source_option_code="",
        excluded=excluded, source_bom=bom_used, balloon_numbers="",
        electrical_unit="", source_electrical_bom_rev="", user_notes=user_notes,
    )


# Snapshot A (the older build).
# Note: to test that a LEAF whose own sourcing BOM is unchanged stays UNCHANGED,
# 1000001 sits under a sub-assembly (2000010) whose BOM does NOT bump between
# A and B. The top BOM bumps 003->004, but 1000001's sourcing BOM is the
# sub-assembly BOM, which is stable -> 1000001 should be UNCHANGED.
nodes_a = [
    node("a1", "TOP", qty=1, bom_used="BOM-TOP-003", bom_level=0),
    node("a4", "2000010", qty=1, bom_used="BOM-TOP-003", parent_node_id="a1"),    # sub-asm, sourced from top
    node("a2", "1000001", qty=2, bom_used="BOM-2000010-002", parent_node_id="a4"),# leaf under stable sub-asm BOM
    node("a3", "1000002", qty=1, bom_used="BOM-TOP-003", parent_node_id="a1"),    # leaf under top
    node("a5", "1000099", qty=5, bom_used="BOM-TOP-003", parent_node_id="a1"),    # will be removed
    node("a6", "1000050-LH", qty=1, bom_used="BOM-TOP-003", parent_node_id="a1"),
    node("a7", "1000777", qty=1, bom_used="BOM-2000010-002", parent_node_id="a4"),# under 2000010
    node("a9", "1000888", qty=1, bom_used="BOM-TOP-003", parent_node_id="a1", user_notes=""),
]

# Snapshot B (the newer build, 6 months later).
nodes_b = [
    node("b1", "TOP", qty=1, bom_used="BOM-TOP-004", bom_level=0),       # rev change top 003->004
    node("b4", "2000010", qty=1, bom_used="BOM-TOP-004", parent_node_id="b1"),     # sub-asm now sourced from top-004
    node("b2", "1000001", qty=2, bom_used="BOM-2000010-002", parent_node_id="b4"), # leaf sourcing BOM UNCHANGED (002), same qty, same parent
    node("b3", "1000002", qty=3, bom_used="BOM-TOP-004", parent_node_id="b1"),     # qty 1->3 AND rev token 003->004
    node("b6", "1000050-LH", qty=1, bom_used="BOM-TOP-004", parent_node_id="b1"),  # rev token 003->004
    node("b8", "1000200", qty=1, bom_used="BOM-TOP-004", parent_node_id="b1"),     # NEW added
    node("b7", "1000777", qty=1, bom_used="BOM-TOP-004", parent_node_id="b1"),     # MOVED: was under 2000010, now under TOP; rev token also differs
    node("b9", "1000888", qty=1, bom_used="BOM-TOP-003", parent_node_id="b1", user_notes="Builder verify label orientation"),
]

result = diff_snapshots(nodes_a, nodes_b, "SNAP-A", "SNAP-B", include_unchanged=True)

print("=" * 70)
print(f"Diff: {result.snapshot_a} -> {result.snapshot_b}  (schema {result.schema_version})")
print("=" * 70)
print(f"Added:            {result.added}")
print(f"Removed:          {result.removed}")
print(f"Qty changed:      {result.qty_changed}")
print(f"Revision changed: {result.revision_changed}")
print(f"Moved:            {result.moved}")
print(f"Unchanged:        {result.unchanged}")
print(f"Total changes:    {result.total_changes}")
print("-" * 70)
for ln in result.lines:
    cats = ",".join(ln.categories)
    print(f"  [{cats:30}] {ln.item_code:16} {ln.note}")
print("=" * 70)

# Assertions
codes = {ln.item_code: ln for ln in result.lines}

assert REMOVED in codes["1000099"].categories, "1000099 should be REMOVED"
assert ADDED in codes["1000200"].categories, "1000200 should be ADDED"
assert QTY_CHANGED in codes["1000002"].categories, "1000002 should be QTY_CHANGED"
assert REVISION_CHANGED in codes["1000002"].categories, "1000002 should ALSO be REVISION_CHANGED"
assert REVISION_CHANGED in codes["2000010"].categories, "2000010 (sub-asm) should be REVISION_CHANGED"
assert MOVED in codes["1000777"].categories, "1000777 should be MOVED"
assert USER_NOTES_CHANGED in codes["1000888"].categories, "1000888 should be USER_NOTES_CHANGED"
assert "1000050-LH" in codes, "LH variant must be preserved as distinct identity"
# 1000001's own sourcing BOM (BOM-2000010-002) is unchanged across A and B,
# qty same, parent same -> UNCHANGED, even though the top BOM rev bumped.
# This proves leaves only flag when THEIR sourcing BOM rev changes.
assert UNCHANGED in codes["1000001"].categories, "1000001 should be UNCHANGED (its own sourcing BOM did not bump)"

print("\nALL ASSERTIONS PASSED")
