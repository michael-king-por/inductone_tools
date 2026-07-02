# BOM Item User Notes data flow

Date: 2026-07-02

## Purpose

Electrical engineering needs a per-line, builder-facing note that lives on the
specific BOM Item occurrence, not on the Item master. This mirrors the existing
per-line electrical metadata model:

- `custom_electrical_unit`
- `custom_source_electrical_bom_rev`
- `custom_balloon_numbers`

The new field is `custom_user_notes` on `BOM Item`, exposed as **User Notes**.

## Field model

| Layer | Doctype / object | Field | Notes |
|---|---|---|---|
| Source BOM line | `BOM Item` Custom Field | `custom_user_notes` | Small Text, label `User Notes`, translatable off, no-copy off |
| Structured BOM resolver row | Python row dict | `user_notes` | Sourced from `BOM Item.custom_user_notes`; defaults to empty string |
| Frozen hierarchy snapshot | `Configured BOM Snapshot Hierarchy` | `user_notes` | App-owned child DocField exported in `doctype.json` |
| Builder workbook | Configured BOM Hierarchy XLSX | `User Notes` column | Rendered beside `Electrical Unit` and `Source Rev` |
| Export package results | `BOM Export Package Item` | `user_notes` | Carries notes into package audit/results rows |
| Snapshot diff schema | `SnapshotNode.user_notes` | `user_notes` | Schema version bumped to `1.1`; note-only deltas emit `USER_NOTES_CHANGED` |

`Configured BOM Snapshot Item` was intentionally not extended. That child table
is the flat configured-items table and is not populated by the existing
electrical per-line metadata path. Extending it would create an unused field and
make the data model less clear.

## Import path finding

No custom electrical BOM spreadsheet import/parser was found in this app for
BOM Item metadata. The repo uses standard ERPNext/BOM data structures and
custom export/snapshot code after the BOM Item rows already exist.

Operationally, electrical BOM spreadsheet imports should map the spreadsheet
notes column to the ERPNext BOM Item field **User Notes**
(`custom_user_notes`) using the same standard import path currently used for
the existing BOM Item electrical metadata fields.

## Fixture decision

`custom_field.json` previously exported no Custom Field rows. This change adds
`BOM Item` to the filtered Custom Field fixture allowlist and exports the six
existing/current BOM Item custom fields:

- `custom_orientation`
- `custom_option_tagging`
- `custom_balloon_numbers`
- `custom_electrical_unit`
- `custom_source_electrical_bom_rev`
- `custom_user_notes`

This is intentional. The existing electrical/balloon fields were production
metadata dependencies but were not repo-distributed before this change.

Because these fields are now fixture-managed, production deployment must prove
that the fixture definitions match the live production Custom Field definitions
before `bench migrate` runs. Fixture sync updates matching Custom Field records
to the fixture definition; a mismatch would overwrite production's live
definition.

Deployment gate:

```bash
"$PROD_BENCH/env/bin/python" "$PROD_BENCH/apps/inductone_tools/scripts/run_custom_field_fixture_parity_check.py" \
  --site "$PROD_SITE" \
  --sites-path "$PROD_BENCH/sites" \
  --fixture-path "$PROD_BENCH/apps/inductone_tools/inductone_tools/fixtures/custom_field.json" \
  --evidence-dir "$EVIDENCE_DIR"
```

The gate must report zero `WOULD_OVERWRITE` fields before deployment. Any
`UNMANAGED_ON_SITE` BOM Item Custom Field must be explicitly classified as
either a remaining manual field or a gap that should be added to the fixture.

## Candidate validation evidence

Candidate site: `inductone-candidate.localhost`

Evidence:

- `C:\hub\frappe-sandbox\validation-evidence\user_notes_candidate_field_setup.json`
- `C:\hub\frappe-sandbox\validation-evidence\user_notes_roundtrip_validation_1783013299.json`
- `C:\hub\frappe-sandbox\validation-evidence\custom_field_fixture_parity_20260702T175001Z.json`

Validated:

1. `BOM Item.custom_user_notes` flows into `explode_bom_tree_structured`.
2. Existing electrical metadata, description, and qty still flow.
3. `Configured BOM Snapshot Hierarchy.user_notes` is populated.
4. `BOM Export Package Item.user_notes` is populated.
5. The builder-facing hierarchy workbook contains a `User Notes` column and the exact note value.
6. Snapshot diff detects a note-only change as `USER_NOTES_CHANGED`.
7. BOM Item rows without notes default to empty string without error.
