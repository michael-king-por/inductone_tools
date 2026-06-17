"""
================================================================================
 SNAPSHOT HIERARCHY SCHEMA CONTRACT  --  READ THIS FIRST
================================================================================

This module is the SINGLE point of coupling between the snapshot diff tool and
the way Configured BOM Snapshot data is stored in ERPNext.

WHY THIS FILE EXISTS
--------------------
The diff tool reads the materialized BOM tree out of the
`Configured BOM Snapshot Hierarchy` child table. That child table's field
names and meanings are a CONTRACT. If anyone ever changes how the snapshot
hierarchy is stored -- renames a field, splits the revision out of `bom_used`,
adds a new effect origin, changes node typing -- the diff tool will silently
produce wrong results UNLESS this adapter is updated to match.

THE RULE
--------
Nothing else in the diff tool is allowed to reference a raw hierarchy
fieldname. Every other module consumes the normalized `SnapshotNode` dataclass
produced here. To adapt to a schema change you edit THIS FILE ONLY:

  1. Bump SNAPSHOT_SCHEMA_VERSION below.
  2. Update HIERARCHY_FIELDS to match the new fieldnames.
  3. Update `normalize_row` if the meaning (not just the name) changed.
  4. Add a note to the CHANGE LOG at the bottom of this file.

If the child table is versioned in the future (e.g. a `schema_version` field
on the snapshot), wire that into `assert_schema_compatible` so the tool fails
LOUDLY on an unknown version rather than diffing garbage.

CURRENT CONTRACT  --  Configured BOM Snapshot Hierarchy  (as of 2026-06)
------------------------------------------------------------------------
  node_id                      Data    stable per-row id within a snapshot
  parent_node_id               Data    node_id of the parent row (tree linkage)
  bom_level                    Int     depth in the tree (0 = top)
  item_code                    Link    Item -- the part number
  item_name                    Data
  item_group                   Data
  description                  Long Text
  qty                          Float   quantity at this node
  uom                          Data
  bom_used                     Data    BOM name used to explode this node, if any
  node_type                    Select  Assembly | Leaf
  is_leaf                      Check
  effect_origin                Select  BASELINE | REPLACEMENT | ADDITION
  source_option_code           Data    option that introduced this node, if any
  excluded_by_structural_effect Check  row suppressed by a REMOVE/REPLACE effect
  source_bom                   Data    BOM the row was sourced from
  source_bom_item              Data
  source_bom_item_idx          Int
  balloon_numbers              Data
  electrical_unit              Data
  source_electrical_bom_rev    Data

REVISION DETECTION NOTE
-----------------------
There is no dedicated "revision" column. The revision a part was built against
is carried inside the BOM name in `bom_used` / `source_bom`
(e.g. "BOM-1611 027 0921 ELEC-005" -> revision 005). Revision-change detection
therefore parses the trailing revision token off the BOM name. If a future
schema adds an explicit revision field, prefer it -- update `node_revision()`.
================================================================================
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
import re

# Bump this whenever the contract below changes. The diff report stamps it into
# its output so any saved diff is traceable to the schema it was produced under.
SNAPSHOT_SCHEMA_VERSION = "1.0"

# The child table the hierarchy lives in, and the parent field on the snapshot.
HIERARCHY_CHILD_DOCTYPE = "Configured BOM Snapshot Hierarchy"
SNAPSHOT_DOCTYPE = "Configured BOM Snapshot"
HIERARCHY_PARENTFIELD = "hierarchy"

# The exact fieldnames this tool depends on. If a name changes in the DocType,
# change it HERE and nowhere else.
HIERARCHY_FIELDS = {
    "node_id": "node_id",
    "parent_node_id": "parent_node_id",
    "bom_level": "bom_level",
    "item_code": "item_code",
    "item_name": "item_name",
    "item_group": "item_group",
    "description": "description",
    "qty": "qty",
    "uom": "uom",
    "bom_used": "bom_used",
    "node_type": "node_type",
    "is_leaf": "is_leaf",
    "effect_origin": "effect_origin",
    "source_option_code": "source_option_code",
    "excluded_by_structural_effect": "excluded_by_structural_effect",
    "source_bom": "source_bom",
    "balloon_numbers": "balloon_numbers",
    "electrical_unit": "electrical_unit",
    "source_electrical_bom_rev": "source_electrical_bom_rev",
}


@dataclass
class SnapshotNode:
    """
    Normalized, storage-agnostic representation of one hierarchy row.

    Every consumer in the diff tool works with this, never with raw rows.
    """
    node_id: str
    parent_node_id: Optional[str]
    bom_level: int
    item_code: str
    item_name: str
    item_group: str
    description: str
    qty: float
    uom: str
    bom_used: str
    node_type: str
    is_leaf: bool
    effect_origin: str
    source_option_code: str
    excluded: bool
    source_bom: str
    balloon_numbers: str
    electrical_unit: str
    source_electrical_bom_rev: str

    # Derived, filled in after construction:
    parent_item_code: Optional[str] = None  # resolved via parent_node_id


def _to_float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _to_int(value) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _to_bool(value) -> bool:
    return bool(value) and str(value) not in ("0", "", "None", "False")


def normalize_row(row: dict) -> SnapshotNode:
    """
    Convert one raw hierarchy row (dict) into a SnapshotNode.

    `row` is whatever frappe.get_all / doc.hierarchy yields -- a dict keyed by
    the real fieldnames. All field access goes through HIERARCHY_FIELDS so a
    rename is a one-line change above.
    """
    f = HIERARCHY_FIELDS
    g = row.get
    return SnapshotNode(
        node_id=g(f["node_id"]) or "",
        parent_node_id=g(f["parent_node_id"]) or None,
        bom_level=_to_int(g(f["bom_level"])),
        item_code=(g(f["item_code"]) or "").strip(),
        item_name=g(f["item_name"]) or "",
        item_group=g(f["item_group"]) or "",
        description=g(f["description"]) or "",
        qty=_to_float(g(f["qty"])),
        uom=g(f["uom"]) or "",
        bom_used=(g(f["bom_used"]) or "").strip(),
        node_type=g(f["node_type"]) or "",
        is_leaf=_to_bool(g(f["is_leaf"])),
        effect_origin=g(f["effect_origin"]) or "",
        source_option_code=g(f["source_option_code"]) or "",
        excluded=_to_bool(g(f["excluded_by_structural_effect"])),
        source_bom=(g(f["source_bom"]) or "").strip(),
        balloon_numbers=g(f["balloon_numbers"]) or "",
        electrical_unit=g(f["electrical_unit"]) or "",
        source_electrical_bom_rev=g(f["source_electrical_bom_rev"]) or "",
    )


def assert_schema_compatible(snapshot_doc) -> None:
    """
    Defensive check before diffing. Raises if the snapshot does not look like
    something this contract version understands.

    Today this just confirms the hierarchy table exists and has rows with the
    expected keys. If an explicit schema_version field is added to the snapshot
    in the future, validate it here and refuse unknown versions.
    """
    rows = snapshot_doc.get(HIERARCHY_PARENTFIELD) or []
    if not rows:
        # An empty hierarchy is a legitimate (if unusual) state -- a snapshot
        # with no resolved lines. Let it through; the diff will just show
        # everything as added/removed. We only fail on structural mismatch.
        return

    sample = rows[0].as_dict() if hasattr(rows[0], "as_dict") else dict(rows[0])
    required = {HIERARCHY_FIELDS["node_id"], HIERARCHY_FIELDS["item_code"]}
    missing = required - set(sample.keys())
    if missing:
        raise ValueError(
            "Snapshot hierarchy schema mismatch. Expected fields {0} not found "
            "on '{1}'. The diff tool's schema contract "
            "(snapshot_diff/schema.py, version {2}) is out of date with the "
            "Configured BOM Snapshot Hierarchy DocType. Update the adapter "
            "before diffing.".format(
                sorted(missing), HIERARCHY_CHILD_DOCTYPE, SNAPSHOT_SCHEMA_VERSION
            )
        )


# ----------------------------------------------------------------------------
#  Revision identity  --  ported and hardened from InductOneDiffApp
# ----------------------------------------------------------------------------
#
#  Goal: a part that moved from one BOM revision to another should report as a
#  REVISION CHANGE, not as one part removed plus one part added. And LH/RH
#  handedness must NEVER be collapsed -- a left-hand and right-hand variant are
#  genuinely different parts, not revisions of each other.

# Handedness suffixes that are part identity, never revision noise.
_HANDEDNESS = ("LH", "RH")

# Trailing revision token on a BOM name, e.g. "...-005" -> "005",
# or a trailing single letter "...-A"/"... B" used on some item revisions.
_BOM_REV_RE = re.compile(r"[-\s]([0-9]{1,4}|[A-Z])$")


def node_revision(node: SnapshotNode) -> str:
    """
    Best-effort extraction of the revision a node was built against.

    Source of truth is the BOM name in `bom_used` (falling back to `source_bom`).
    Returns the trailing revision token, or "" if none can be parsed.

    NOTE: if a future schema adds an explicit revision field on the hierarchy
    row, read it here in preference to parsing the BOM name.
    """
    bom = node.bom_used or node.source_bom or ""
    if not bom:
        return ""
    m = _BOM_REV_RE.search(bom.strip())
    return m.group(1) if m else ""


def revision_identity(item_code: str) -> str:
    """
    The part-family identity used to decide whether two rows are 'the same part
    at possibly-different revisions'.

    For the snapshot diff we key parts on item_code directly -- item codes at
    Plus One are stable identities and the revision lives on the BOM, not the
    item code. So two rows with the same item_code but different bom_used
    revisions are the same part, different revision.

    Handedness is preserved: LH and RH live in the item_code itself, so they
    never collapse. This function exists as the explicit hook where, if item
    codes ever DID carry trailing revision letters that needed stripping, you
    would strip them here -- while still refusing to strip LH/RH.
    """
    code = (item_code or "").strip().upper()
    # Defensive: never strip a handedness suffix.
    for hand in _HANDEDNESS:
        if code.endswith("-" + hand) or code.endswith(" " + hand) or code.endswith(hand):
            return code  # identity is the full code; do not touch
    return code


# ============================================================================
#  CHANGE LOG  --  every schema-contract change gets a line here
# ============================================================================
#  1.0  2026-06  Initial contract. Targets Configured BOM Snapshot Hierarchy
#                as built in Release 1.5. Revision parsed from bom_used / 
#                source_bom trailing token. Item code is the part identity;
#                LH/RH never stripped.
# ============================================================================