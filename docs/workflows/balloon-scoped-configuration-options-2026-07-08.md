# Balloon-scoped configuration options

Date: 2026-07-08

## Purpose

REV E electrical BOMs are maintained as 150% masters: configurable callouts can carry both the standard row and the moved/option row in the same BOM. Item-only option resolution is unsafe because the same item can appear on multiple balloons, including fixed occurrences that must survive configuration.

The hardened resolver now supports optional `target_balloon` on:

- `InductOne Configuration Option Mapping`
- `Configured BOM Snapshot Structural Effect`

When `target_balloon` is empty, legacy item-wide behavior remains. When it is populated, REMOVE and REPLACE actions apply only to the row whose `(balloon, item)` matches the mapping/effect.

## Data model

Both fields are fixture-managed Custom Fields:

| DocType | Field | Type | Inserted after |
|---|---|---|---|
| `InductOne Configuration Option Mapping` | `target_balloon` | Data | `target_item` |
| `Configured BOM Snapshot Structural Effect` | `target_balloon` | Data | `target_item` |

The `InductOne Build Script` client script carries `target_balloon` from mapping rows into frozen snapshot structural effects. The server resolver reads only the snapshot effects during export/package generation, so this carry-through is required.

## Reviewed option catalog

The reviewed catalog is defined in `inductone_tools.balloon_scoped_options`.

The deployed catalog is fixture-managed through `inductone_tools/fixtures/inductone_configuration_option.json`, scoped in `hooks.py` by:

```python
{
    "dt": "InductOne Configuration Option",
    "filters": [["option_code", "like", "DEV-%"]]
}
```

This deliberately exports only the reviewed `DEV-*` feature catalog. Future operational options authored outside this feature should not be swept into version control unless explicitly reviewed.

The fixture creates 13 `Draft` options:

- `DEV-BASELINE`
- six standard/default no-op options
- six moved/deviation options

The groups are intentionally independent binary groups so selecting HMI, Stacklight, Fortress, Maglock, IPC, and MCP deviations does not accidentally deselect unrelated decisions.

`scripts/load_balloon_scoped_options.py` remains the authoring/bootstrap tool for fresh candidate instances and for regenerating the reviewed catalog from code. Deployed instances receive the reviewed options via `bench migrate` from the scoped fixture. The options intentionally ship at `Draft`; promoting them to `Released` happens only through governed Engineering Signoff approval.

## BOM-ground-truth corrections found during validation

- The generated brief’s “0921 contains 9” value was treated as a stale artifact. The trusted collision check is that `BOM-1611 027 0921 ELEC-006` contains `1417891` at balloon `315`, qty `3`.
- Balloon `159` is stored in ERPNext as one combined option item code: `MDCM-8FP-10M-R  & MDC-8MP-FW11`, qty `2`. The release-note prose describes two coupled PNs, but the BOM row is the deployable source of truth.

## Validation summary

Candidate validation evidence:

- `/mnt/c/hub/frappe-sandbox/validation-evidence/balloon_trust_basis_corrected_20260707.json`
- `/mnt/c/hub/frappe-sandbox/validation-evidence/balloon_gate_r_baseline_bld0225_20260707/`
- `/mnt/c/hub/frappe-sandbox/validation-evidence/balloon_scoped_options_validation_20260708T052142Z.json`
- `/mnt/c/hub/frappe-sandbox/validation-evidence/balloon_closeout_static_checks_20260708T141107Z.json`
- `/mnt/c/hub/frappe-sandbox/validation-evidence/balloon_scoped_options_validation_20260708T141108Z.json`

The 12-case candidate matrix passed, including the three collision assertions:

- `11283`: balloon 172 option and balloon 173 standard remain independent.
- `1417902`: balloon 193 replacement does not remove the fixed balloon 188 occurrence.
- `1417891`: balloon 154 replacement does not remove the fixed balloon 315 occurrence in `0921`.

Fixture round-trip validation deleted all 13 `DEV-*` candidate records, ran `bench migrate`, confirmed all 13 were recreated from `inductone_configuration_option.json` with `name == option_code`, `status == Draft`, complete descriptions, and complete mappings, then reran parity and the full 12-case resolver matrix without using the loader.

## Hierarchy regression and permanent guard

Follow-up production-data validation found that the deployed hierarchy path could drop the baseline balloon `173` row for item `11283`, qty `2`, while correctly moving balloon `172` to `11283` under IPC. That is the core repeated-item collision for this feature:

- Balloon `172`: `11245` standard, `11283` option.
- Balloon `173`: `11283` standard, `11351` option.

The corrected invariant is single resolution, multiple presentations:

- `bom_export.build_configured_rows` is the canonical balloon-aware resolver.
- `snapshot.hierarchy.populate_snapshot_hierarchy` materializes hierarchy rows from that resolver through an in-memory `BOM Export Package` context.
- `snapshot.hierarchy.generate_hierarchy_workbook` renders only the materialized hierarchy.
- Snapshot diff reads the materialized hierarchy.
- `Configured BOM Snapshot Item` / `.lines` is a balloon-blind material rollup and must not be treated as structural truth.

The hardened candidate suite now asserts flat, hierarchy, and hierarchy-workbook content against `inductone_tools.balloon_scoped_options.expected_resolution` for all 12 configurations. It also asserts cross-stage consistency, so a future divergence between flat and hierarchy fails even if each stage appears internally plausible.

Final candidate evidence after fixture round-trip:

- `/mnt/c/hub/frappe-sandbox/validation-evidence/balloon_scoped_options_validation_20260708T174507Z.json`
- `/mnt/c/hub/frappe-sandbox/validation-evidence/balloon_export_zip_closeout_20260708T174734Z.json`

Regression sentinel: baseline must contain `173 → 11283 qty 2` in flat, hierarchy, and workbook; IPC must contain `172 → 11283 qty 3` and `173 → 11351 qty 2`.


## Status lifecycle and signoff release gate

As of the 2026-07-08 status-model cleanup, the canonical option lifecycle is:

```text
Draft → Released → Deprecated
```

The abandoned intermediate statuses `Defined-Product` and `Defined-Ops` were removed from the `InductOne Configuration Option.status` Select field. Existing `Defined-Ops` / `Defined-Product` records are moved to `Draft` by idempotent patch `v2026_07_08_configuration_option_status_model_cleanup` before the field trim is applied.

`request_signoff` is valid only while an option is `Draft`. `approve_signoff` requires `mapping_status == Complete` and auto-promotes the option to `Released`; `engineering_signoff.on_target_save` blocks manual Draft→Released edits and makes Released/Deprecated options immutable. The candidate proof on 2026-07-08 ran request→approve→Released for all 13 DEV options and confirmed manual release, Released edits, and non-Draft signoff requests are rejected.

The inactive legacy workflow `InductOne Option Cycle` was removed. The `workflow_state` column remains present but empty (`NULL` for all option rows); it is documented as harmless retained schema rather than removed blindly from a live Frappe DocType.
