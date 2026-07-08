"""Balloon-scoped InductOne electrical configuration option catalog.

The REV E electrical BOMs are 150% masters: configurable callouts carry both
the Standard row and the Option row in the source BOM. The option resolver must
therefore address rows by the occurrence-local key ``(target_balloon,
target_item)`` when pruning or replacing material. Empty ``target_balloon``
keeps the pre-existing item-wide behavior.

This module deliberately keeps the reviewed catalog and the independent
expected-value oracle together so loader and validation scripts do not drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


MASTER_ELECTRICAL_BOM = "BOM-1611 027 0931 ELEC-004"
COLLISION_REFERENCE_BOM = "BOM-1611 027 0921 ELEC-006"


@dataclass(frozen=True)
class Substitution:
    balloon: str
    standard_item: str
    option_items: tuple[str, ...]
    moved_by: tuple[str, ...]


@dataclass(frozen=True)
class Extension:
    balloon: str
    item: str
    added_by: tuple[str, ...]
    partner_balloon: str
    partner_item_note: str


SUBSTITUTIONS: tuple[Substitution, ...] = (
    Substitution("137", "MCVP-19MFP-5M", ("MCVP-19MFP-10M",), ("DEV-PANEL-IPC", "DEV-COMP-FORTRESS")),
    Substitution("140", "1407378", ("1407379",), ("DEV-PANEL-IPC", "DEV-COMP-HMI")),
    Substitution("141", "1407485", ("1407486",), ("DEV-PANEL-IPC", "DEV-COMP-HMI")),
    Substitution("144", "1407362", ("1407363",), ("DEV-PANEL-IPC",)),
    Substitution("154", "1417891", ("1417892",), ("DEV-PANEL-IPC", "DEV-COMP-HMI")),
    # The release-note prose describes balloon 159 as two coupled PNs, but the
    # ERPNext BOM stores the option as one combined Item code. The BOM row is
    # the validation/deployment ground truth.
    Substitution("159", "WKC 8T-4-RSC 8T", ("MDCM-8FP-10M-R  & MDC-8MP-FW11",), ("DEV-PANEL-IPC", "DEV-COMP-MAGLOCK")),
    Substitution("172", "11245", ("11283",), ("DEV-PANEL-IPC",)),
    Substitution("173", "11283", ("11351",), ("DEV-PANEL-IPC",)),
    Substitution("190", "1425016", ("1291280",), ("DEV-PANEL-IPC",)),
    Substitution("191", "1007-300-0002-02", ("1000517",), ("DEV-PANEL-IPC",)),
    Substitution("193", "1417902", ("1417903",), ("DEV-PANEL-IPC", "DEV-COMP-STACK")),
)

EXTENSIONS: tuple[Extension, ...] = (
    Extension("143", "1407402", ("DEV-PANEL-MCP",), "142", "1192150"),
    Extension("145", "MCVP-12MMFP-5M", ("DEV-PANEL-MCP", "DEV-PANEL-IPC"), "146", "MCVP-12MFP-15M"),
    Extension("149", "1276573", ("DEV-PANEL-MCP",), "150", "1292210/U60/15"),
    Extension("156", "RSM RKM 30-5M/S101", ("DEV-PANEL-MCP", "DEV-PANEL-IPC"), "155", "RSM RKM 36-15M/S3059"),
)

STANDARD_OPTION_CODES: tuple[str, ...] = (
    "DEV-PANEL-MCP-STD",
    "DEV-PANEL-IPC-STD",
    "DEV-COMP-HMI-STD",
    "DEV-COMP-STACK-STD",
    "DEV-COMP-FORTRESS-STD",
    "DEV-COMP-MAGLOCK-STD",
)

MOVED_OPTION_CODES: tuple[str, ...] = (
    "DEV-PANEL-MCP",
    "DEV-PANEL-IPC",
    "DEV-COMP-HMI",
    "DEV-COMP-STACK",
    "DEV-COMP-FORTRESS",
    "DEV-COMP-MAGLOCK",
)

OPTION_GROUPS = {
    "DEV-BASELINE": "Electrical Cable Baseline",
    "DEV-PANEL-MCP-STD": "MCP Panel Position",
    "DEV-PANEL-MCP": "MCP Panel Position",
    "DEV-PANEL-IPC-STD": "IPC Panel Position",
    "DEV-PANEL-IPC": "IPC Panel Position",
    "DEV-COMP-HMI-STD": "HMI Position",
    "DEV-COMP-HMI": "HMI Position",
    "DEV-COMP-STACK-STD": "Stacklight Position",
    "DEV-COMP-STACK": "Stacklight Position",
    "DEV-COMP-FORTRESS-STD": "Fortress Position",
    "DEV-COMP-FORTRESS": "Fortress Position",
    "DEV-COMP-MAGLOCK-STD": "Maglock Position",
    "DEV-COMP-MAGLOCK": "Maglock Position",
}

OPTION_NAMES = {
    "DEV-BASELINE": "Deviation — All Standard (Baseline)",
    "DEV-PANEL-MCP-STD": "MCP Panel — Standard",
    "DEV-PANEL-MCP": "Deviation — MCP Panel Relocated",
    "DEV-PANEL-IPC-STD": "IPC Panel — Standard",
    "DEV-PANEL-IPC": "Deviation — IPC Panel Relocated",
    "DEV-COMP-HMI-STD": "HMI — Standard",
    "DEV-COMP-HMI": "Deviation — HMI Relocated",
    "DEV-COMP-STACK-STD": "Stacklight — Standard",
    "DEV-COMP-STACK": "Deviation — Stacklight Relocated",
    "DEV-COMP-FORTRESS-STD": "Fortress — Standard",
    "DEV-COMP-FORTRESS": "Deviation — Fortress Relocated",
    "DEV-COMP-MAGLOCK-STD": "Magnet Lock — Standard",
    "DEV-COMP-MAGLOCK": "Deviation — Magnet Lock Relocated",
}

INTERNAL_NOTES = {
    "DEV-BASELINE": (
        "Use for the standard electrical cable configuration when no electrical panel "
        "or component relocation deviations are required."
    ),
    "DEV-PANEL-MCP-STD": (
        "Use when the MCP panel remains in its standard location. Select the paired "
        "relocated option only when the MCP panel is moved from standard."
    ),
    "DEV-PANEL-MCP": (
        "Use when the MCP panel is relocated and the standard cable set needs the "
        "relocation extension cabling."
    ),
    "DEV-PANEL-IPC-STD": (
        "Use when the IPC panel remains in its standard location. Select the paired "
        "relocated option only when the IPC panel is moved from standard."
    ),
    "DEV-PANEL-IPC": (
        "Use when the IPC panel is relocated and the electrical cable package needs "
        "the longer relocated-panel cable set."
    ),
    "DEV-COMP-HMI-STD": (
        "Use when the HMI remains in its standard location. Select the paired relocated "
        "option only when the HMI is moved from standard."
    ),
    "DEV-COMP-HMI": (
        "Use when the HMI is relocated and only the HMI-related electrical cables need "
        "the relocated lengths."
    ),
    "DEV-COMP-STACK-STD": (
        "Use when the stacklight remains in its standard location. Select the paired "
        "relocated option only when the stacklight is moved from standard."
    ),
    "DEV-COMP-STACK": (
        "Use when the stacklight is relocated and only the stacklight electrical cable "
        "needs the relocated length."
    ),
    "DEV-COMP-FORTRESS-STD": (
        "Use when the Fortress safety component remains in its standard location. "
        "Select the paired relocated option only when Fortress is moved from standard."
    ),
    "DEV-COMP-FORTRESS": (
        "Use when Fortress is relocated and only the Fortress electrical cable needs "
        "the relocated length."
    ),
    "DEV-COMP-MAGLOCK-STD": (
        "Use when the magnet lock remains in its standard location. Select the paired "
        "relocated option only when the magnet lock is moved from standard."
    ),
    "DEV-COMP-MAGLOCK": (
        "Use when the magnet lock is relocated and only the magnet-lock electrical "
        "cable needs the relocated length."
    ),
}

STANDARD_BUILDER_NOTES = (
    "Default selection for this required option group. Mutually exclusive with "
    "the paired relocated option."
)

MOVED_BUILDER_NOTES = (
    "Paired with the standard option in the same required group; select only one. "
    "If this overlaps with the IPC panel relocation or a component relocation, the "
    "balloon-scoped resolver applies the same moved row once and prevents double "
    "cabling."
)

BUILDER_DESCRIPTIONS = {
    "DEV-BASELINE": (
        "Standard electrical cable baseline for the InductOne REV E electrical BOM.\n\n"
        "Configuration effect:\n"
        "All managed balloon callouts resolve to the standard BOM rows, and option/"
        "extension rows are pruned from the configurable electrical cable balloons.\n\n"
        "Notes:\n"
        "Always applied as the single-member required baseline group and not "
        "independently deselectable. Every other DEV option layers on this baseline."
    ),
    "DEV-PANEL-MCP-STD": (
        "MCP panel remains in the standard location.\n\n"
        "Configuration effect:\n"
        "No change. Baseline standard cabling applies.\n\n"
        "Notes:\n"
        f"{STANDARD_BUILDER_NOTES}"
    ),
    "DEV-PANEL-MCP": (
        "MCP panel relocated from the standard electrical layout.\n\n"
        "Configuration effect:\n"
        "Adds extension rows: balloon 143 -> 1407402 (M12 D-CODE 5M extension); "
        "balloon 145 -> MCVP-12MMFP-5M (M23 12-pole 5M); balloon 149 -> 1276573 "
        "(M12 L-CODE 5M); balloon 156 -> RSM RKM 30-5M/S101 (7/8 in 3-pin 5M). "
        "No standard-row substitutions are made by this option.\n\n"
        "Notes:\n"
        f"{MOVED_BUILDER_NOTES}"
    ),
    "DEV-PANEL-IPC-STD": (
        "IPC panel remains in the standard location.\n\n"
        "Configuration effect:\n"
        "No change. Baseline standard cabling applies.\n\n"
        "Notes:\n"
        f"{STANDARD_BUILDER_NOTES}"
    ),
    "DEV-PANEL-IPC": (
        "IPC panel relocated from the standard electrical layout.\n\n"
        "Configuration effect:\n"
        "Replaces balloon 137 with MCVP-19MFP-10M x2 (M23 x19 10M); balloon 140 "
        "with 1407379 (M12 D-CODE 10M); balloon 141 with 1407486 (M12 X-CODE 10M); "
        "balloon 144 with 1407363 (RJ45-M12 D 10M); balloon 154 with 1417892 "
        "(M12 A 4-pin 10M); balloon 159 with MDCM-8FP-10M-R  & MDC-8MP-FW11 x2 "
        "(M12 8-pin 10M combined item); balloon 172 with 11283 x3 (RJ45 6M); "
        "balloon 173 with 11351 x2 (RJ45 15M); balloon 190 with 1291280 "
        "(M12 L 10M); balloon 191 with 1000517 x4 (USB-A 10M extension plus "
        "1M locking lead); balloon 193 with 1417903 (M12 A 5-pin 10M). Adds "
        "extension rows: balloon 145 -> MCVP-12MMFP-5M and balloon 156 -> "
        "RSM RKM 30-5M/S101.\n\n"
        "Notes:\n"
        f"{MOVED_BUILDER_NOTES}"
    ),
    "DEV-COMP-HMI-STD": (
        "HMI remains in the standard location.\n\n"
        "Configuration effect:\n"
        "No change. Baseline standard cabling applies.\n\n"
        "Notes:\n"
        f"{STANDARD_BUILDER_NOTES}"
    ),
    "DEV-COMP-HMI": (
        "HMI relocated from the standard electrical layout.\n\n"
        "Configuration effect:\n"
        "Replaces balloon 140 with 1407379 (M12 D-CODE 10M); balloon 141 with "
        "1407486 (M12 X-CODE 10M); balloon 154 with 1417892 (M12 A 4-pin 10M). "
        "No other managed balloons are changed by this option.\n\n"
        "Notes:\n"
        f"{MOVED_BUILDER_NOTES}"
    ),
    "DEV-COMP-STACK-STD": (
        "Stacklight remains in the standard location.\n\n"
        "Configuration effect:\n"
        "No change. Baseline standard cabling applies.\n\n"
        "Notes:\n"
        f"{STANDARD_BUILDER_NOTES}"
    ),
    "DEV-COMP-STACK": (
        "Stacklight relocated from the standard electrical layout.\n\n"
        "Configuration effect:\n"
        "Replaces balloon 193 with 1417903 (M12 A 5-pin 10M). No other managed "
        "balloons are changed by this option.\n\n"
        "Notes:\n"
        f"{MOVED_BUILDER_NOTES}"
    ),
    "DEV-COMP-FORTRESS-STD": (
        "Fortress safety component remains in the standard location.\n\n"
        "Configuration effect:\n"
        "No change. Baseline standard cabling applies.\n\n"
        "Notes:\n"
        f"{STANDARD_BUILDER_NOTES}"
    ),
    "DEV-COMP-FORTRESS": (
        "Fortress safety component relocated from the standard electrical layout.\n\n"
        "Configuration effect:\n"
        "Replaces balloon 137 with MCVP-19MFP-10M x2 (M23 x19 10M). No other "
        "managed balloons are changed by this option.\n\n"
        "Notes:\n"
        f"{MOVED_BUILDER_NOTES}"
    ),
    "DEV-COMP-MAGLOCK-STD": (
        "Magnet lock remains in the standard location.\n\n"
        "Configuration effect:\n"
        "No change. Baseline standard cabling applies.\n\n"
        "Notes:\n"
        f"{STANDARD_BUILDER_NOTES}"
    ),
    "DEV-COMP-MAGLOCK": (
        "Magnet lock relocated from the standard electrical layout.\n\n"
        "Configuration effect:\n"
        "Replaces balloon 159 with MDCM-8FP-10M-R  & MDC-8MP-FW11 x2 "
        "(M12 8-pin 10M combined item). No other managed balloons are changed "
        "by this option.\n\n"
        "Notes:\n"
        f"{MOVED_BUILDER_NOTES}"
    ),
}


def option_codes() -> list[str]:
    return list(OPTION_NAMES)


def _baseline_remove_mappings() -> list[dict]:
    rows: list[dict] = []
    order = 10
    for sub in SUBSTITUTIONS:
        for item in sub.option_items:
            rows.append(_mapping_remove(sub.balloon, item, order))
            order += 10
    for ext in EXTENSIONS:
        rows.append(_mapping_remove(ext.balloon, ext.item, order))
        order += 10
    return rows


def _moved_option_mappings(code: str) -> list[dict]:
    rows: list[dict] = []
    order = 10
    for sub in SUBSTITUTIONS:
        if code in sub.moved_by:
            for option_item in sub.option_items:
                rows.append(_mapping_replace(sub.balloon, sub.standard_item, option_item, order))
                order += 10
    for ext in EXTENSIONS:
        if code in ext.added_by:
            rows.append(_mapping_add(ext.balloon, ext.item, order))
            order += 10
    return rows


def _mapping_remove(balloon: str, item: str, row_order: int) -> dict:
    return {
        "action": "REMOVE",
        "target_item": item,
        "target_balloon": balloon,
        "replace_with_item": "",
        "replace_scope": "ALL_OCCURRENCES",
        "replace_count": 1,
        "structural_effect_mode": "SUPPRESS_TARGET_NODE",
        "preserve_target_item_identity": 1,
        "expand_mode": "AS_ITEM_ONLY",
        "qty_source": "FIXED",
        "qty_fixed": 1,
        "required_for_release": 1,
        "row_order": row_order,
    }


def _mapping_replace(balloon: str, standard_item: str, option_item: str, row_order: int) -> dict:
    return {
        "action": "REPLACE",
        "target_item": standard_item,
        "target_balloon": balloon,
        "replace_with_item": option_item,
        "replace_scope": "ALL_OCCURRENCES",
        "replace_count": 1,
        # The mapping DocType does not allow REPLACE_TARGET_NODE directly.
        # The InductOne Build client script resolves AUTO + REPLACE +
        # AS_ITEM_ONLY into REPLACE_TARGET_NODE when freezing snapshot effects.
        "structural_effect_mode": "AUTO",
        "preserve_target_item_identity": 1,
        "expand_mode": "AS_ITEM_ONLY",
        "qty_source": "FIXED",
        "qty_fixed": 1,
        "required_for_release": 1,
        "row_order": row_order,
    }


def _mapping_add(balloon: str, item: str, row_order: int) -> dict:
    return {
        "action": "ADD",
        "target_item": item,
        "target_balloon": balloon,
        "replace_with_item": "",
        "replace_scope": "ALL_OCCURRENCES",
        "replace_count": 1,
        "structural_effect_mode": "ADD_BRANCH",
        "preserve_target_item_identity": 1,
        "expand_mode": "AS_ITEM_ONLY",
        "qty_source": "FIXED",
        "qty_fixed": 1,
        "required_for_release": 1,
        "row_order": row_order,
    }


def catalog_specs() -> list[dict]:
    specs = []
    for idx, code in enumerate(option_codes(), start=1):
        if code == "DEV-BASELINE":
            mappings = _baseline_remove_mappings()
            is_default = 1
        elif code in STANDARD_OPTION_CODES:
            mappings = []
            is_default = 1
        else:
            mappings = _moved_option_mappings(code)
            is_default = 0

        specs.append({
            "option_code": code,
            "option_name": OPTION_NAMES[code],
            "option_category": "Electrical",
            "option_group": OPTION_GROUPS[code],
            "option_group_required": 1,
            "is_default_selection": is_default,
            "is_active": 1,
            "status": "Draft",
            "mapping_status": "Complete",
            "owner_role": "Ops",
            "sort_order": idx * 10,
            "internal_notes": INTERNAL_NOTES[code],
            "builder_description": BUILDER_DESCRIPTIONS[code],
            "mappings_table": mappings,
        })
    return specs


def upsert_catalog(frappe_module=None) -> list[dict]:
    """Create/update the reviewed option catalog in the connected Frappe site."""

    if frappe_module is None:
        import frappe as frappe_module  # type: ignore

    frappe = frappe_module
    results = []
    for spec in catalog_specs():
        option_code = spec["option_code"]
        existing = frappe.db.get_value("InductOne Configuration Option", {"option_code": option_code}, "name")
        if existing:
            doc = frappe.get_doc("InductOne Configuration Option", existing)
            action = "updated"
        else:
            doc = frappe.new_doc("InductOne Configuration Option")
            action = "created"

        for field in [
            "option_code",
            "option_name",
            "option_category",
            "option_group",
            "option_group_required",
            "is_default_selection",
            "is_active",
            "status",
            "mapping_status",
            "owner_role",
            "sort_order",
            "internal_notes",
            "builder_description",
        ]:
            doc.set(field, spec[field])

        doc.set("mappings_table", [])
        for mapping in spec["mappings_table"]:
            doc.append("mappings_table", mapping)

        if existing:
            doc.save(ignore_permissions=True)
        else:
            doc.insert(ignore_permissions=True)
        results.append({
            "option_code": option_code,
            "name": doc.name,
            "action": action,
            "mapping_count": len(spec["mappings_table"]),
        })

    frappe.db.commit()
    return results


def selected_moved_codes(selected_option_codes: Iterable[str]) -> set[str]:
    selected = set(selected_option_codes)
    return {code for code in MOVED_OPTION_CODES if code in selected}


def expected_resolution(selected_option_codes: Iterable[str], frappe_module=None) -> dict:
    """Return expected configurable-balloon and collision rollup values.

    This oracle does not call ``build_configured_rows`` and does not read a
    snapshot. When connected to Frappe, it reads the master BOM Item rows for
    quantities so the table stays tied to the production BOM data rather than a
    copied spreadsheet.
    """

    frappe = frappe_module
    moved = selected_moved_codes(selected_option_codes)
    by_balloon: dict[str, list[dict]] = {}

    for sub in SUBSTITUTIONS:
        use_option = any(code in moved for code in sub.moved_by)
        if use_option:
            by_balloon[sub.balloon] = [
                {
                    "item_code": item,
                    "qty": _bom_qty(frappe, MASTER_ELECTRICAL_BOM, sub.balloon, item),
                }
                for item in sub.option_items
            ]
        else:
            by_balloon[sub.balloon] = [{
                "item_code": sub.standard_item,
                "qty": _bom_qty(frappe, MASTER_ELECTRICAL_BOM, sub.balloon, sub.standard_item),
            }]

    for ext in EXTENSIONS:
        present = any(code in moved for code in ext.added_by)
        by_balloon[ext.balloon] = []
        if present:
            by_balloon[ext.balloon].append({
                "item_code": ext.item,
                "qty": _bom_qty(frappe, MASTER_ELECTRICAL_BOM, ext.balloon, ext.item),
            })

    flat: dict[str, float] = {}
    for rows in by_balloon.values():
        for row in rows:
            flat[row["item_code"]] = flat.get(row["item_code"], 0.0) + float(row["qty"] or 0)

    # Fixed collision occurrences outside the configurable rows.
    for bom, balloon, item in [
        (MASTER_ELECTRICAL_BOM, "188", "1417902"),
        (COLLISION_REFERENCE_BOM, "315", "1417891"),
    ]:
        qty = _bom_qty(frappe, bom, balloon, item)
        flat[item] = flat.get(item, 0.0) + float(qty or 0)

    return {
        "selected_moved_options": sorted(moved),
        "by_balloon": by_balloon,
        "flat": flat,
    }


def _bom_qty(frappe, bom: str, balloon: str, item_code: str) -> float:
    if frappe is None:
        return 1.0
    rows = frappe.get_all(
        "BOM Item",
        filters={
            "parent": bom,
            "item_code": item_code,
            "custom_balloon_numbers": balloon,
        },
        fields=["qty"],
        limit=2,
    )
    if not rows:
        raise ValueError(f"Expected BOM Item not found: {bom} balloon {balloon} item {item_code}")
    if len(rows) > 1:
        raise ValueError(f"Ambiguous BOM Item rows: {bom} balloon {balloon} item {item_code}")
    return float(rows[0].qty or 0)
