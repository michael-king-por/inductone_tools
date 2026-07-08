# Validation report — balloon-scoped configuration options

Date: 2026-07-08

## Trust basis

Candidate only. Production was not mutated.

Production app commit basis supplied by owner:

| App | Commit |
|---|---|
| Frappe | `588e443` |
| ERPNext | `b5f7846` |
| Wiki | `2372f85` |
| InductOne Tools | `685661d` |

Corrected candidate trust evidence:

- `C:\hub\frappe-sandbox\validation-evidence\balloon_trust_basis_corrected_20260707.json`

Important correction: the brief’s statement that `0921 ELEC-006` contains 9 configurable rows is treated as a stale artifact. The trusted `0921` check is the fixed collision row `1417891` at balloon `315`, qty `3`.

## Implemented locally

- Added fixture-managed `target_balloon` Custom Fields to:
  - `InductOne Configuration Option Mapping`
  - `Configured BOM Snapshot Structural Effect`
- Added `Configured BOM Snapshot Structural Effect` to the Custom Field fixture filter in `hooks.py`.
- Updated the enabled `InductOne Build Script` fixture to carry `target_balloon` into frozen snapshot structural effects.
- Updated `bom_export.py` so balloon-scoped REMOVE/REPLACE resolves by `(balloon, item)`.
- Added idempotent replacement dedupe for overlapping options such as IPC + HMI or IPC + Maglock.
- Added `inductone_tools.balloon_scoped_options` catalog/oracle module.
- Added loader and candidate validation scripts:
  - `scripts/load_balloon_scoped_options.py`
  - `scripts/run_balloon_scoped_options_validation.py`

## Candidate validation

Evidence:

- `C:\hub\frappe-sandbox\validation-evidence\balloon_scoped_options_validation_20260708T052142Z.json`
- `C:\hub\frappe-sandbox\validation-evidence\balloon_closeout_static_checks_20260708T053927Z.json`
- `C:\hub\frappe-sandbox\validation-evidence\balloon_export_zip_closeout_20260708T054837Z.json`

Preconditions passed:

- BLD-0225 exists.
- `BOM-1611 027 0931 ELEC-004` is active and submitted.
- REV E configurable balloon fingerprint found 26/26 expected rows.
- `BOM-1611 027 0921 ELEC-006` contains `1417891` at balloon `315`, qty `3`.
- Candidate DB has both fixture-managed `target_balloon` Custom Fields.
- Candidate `InductOne Build Script` contains balloon carry-through.

All 12 option combinations passed:

| Case | Moved options | Result |
|---:|---|---|
| 1 | baseline only | PASS |
| 2 | MCP | PASS |
| 3 | IPC | PASS |
| 4 | HMI | PASS |
| 5 | Stacklight | PASS |
| 6 | Fortress | PASS |
| 7 | Maglock | PASS |
| 8 | MCP + IPC | PASS |
| 9 | MCP + Fortress | PASS |
| 10 | IPC + HMI | PASS |
| 11 | MCP + IPC + HMI + Stacklight + Fortress + Maglock | PASS |
| 12 | IPC + Maglock | PASS |

The validation script creates synthetic candidate snapshots, freezes structural effects with `target_balloon`, runs `build_configured_rows`, materializes snapshot hierarchy, generates hierarchy workbooks, and verifies:

- snapshot effects carry `target_balloon`;
- configured balloon rows match the independent oracle;
- collision flat quantities match the independent oracle;
- hierarchy population succeeds;
- hierarchy workbook generation succeeds.

## Close-out validation

### Client Script parity

PASS. The close-out static check compared the production-basis `Client Script` rows to the repo-managed fixture set.

| Check | Result |
|---|---|
| Production-basis script count | 26 |
| Repo fixture script count | 26 |
| Missing / extra script names | None |
| Differing script | `InductOne Build Script` only |
| Diff classification | Only `target_balloon` carry-through additions |
| Explicitly unchanged examples | `minimal`, `Attachment_display`, `generate_zip`, `Fixture Export Control Script` |

The `Custom Field` fixture check also passed with the exact expected 8 managed rows.

### Build-page option group behavior

PASS. The same close-out static check verified the intended client-side grouping model from the reviewed DEV option catalog:

- 13 active DEV options.
- 7 rendered groups.
- `Electrical Cable Baseline` contains only `DEV-BASELINE`.
- Each of the six position groups contains exactly its standard + deviation pair.
- All groups are required.
- Default selection resolves to baseline + six standards with extensions off.
- Cross-group selections such as IPC + HMI do not deselect each other.
- Same-group moved selections deselect the standard.
- Required group validation passes when all groups have a selection and fails when one group is empty.

### BOM Export Package ZIP semantics

PASS with corrected artifact semantics.

The hierarchy workbook is a snapshot-generation artifact and is expected to differ per option set. The ZIP close-out therefore references the stage-4 workbook evidence from:

```text
C:\hub\frappe-sandbox\validation-evidence\balloon_scoped_options_validation_20260708T052142Z.json
```

It does not re-test the workbook inside the BOM Export Package ZIP.

The BOM Export Package ZIP validation generated candidate packages for `baseline_only`, `ipc`, and `everything_moved`, classified each ZIP entry, and asserted only the part-documentation document set across cable-only deviations.

| Case | Part-documentation entries | Configuration/package-derived entries | Result |
|---|---:|---:|---|
| `baseline_only` | 340 | 1 | PASS |
| `ipc` | 340 | 1 | PASS |
| `everything_moved` | 340 | 1 | PASS |

Part-documentation identity comparisons:

| Comparison | Result | Notes |
|---|---|---|
| `baseline_only` vs `everything_moved` | PASS | 340 vs 340 identities; no missing/extra entries; raw ZIP paths also matched |
| `baseline_only` vs `ipc` | PASS | 340 vs 340 identities; no missing/extra entries; raw ZIP paths also matched |

Collision re-assertions were run against the resolved configured rows/flat quantities, not the ZIP, and passed for all three ZIP close-out cases.

Candidate note: attaching the generated ZIPs through Frappe hit the candidate site's configured 10 MB server-side file-size ceiling, so the close-out script inspected the generated ZIP bytes directly using the same package ZIP builder. The generated ZIP byte sizes were approximately 57.25 MB per case. This is an environment configuration observation, not a part-documentation stability failure.

## BOM-ground-truth correction found

Balloon `159` is a single ERPNext BOM Item row:

```text
MDCM-8FP-10M-R  & MDC-8MP-FW11
```

The loader therefore creates one replacement mapping for balloon `159`, not two. This is correct for the deployed ERPNext data model.

## Not yet claimed

This report does not claim a production deployment, and it does not claim a browser-click UI validation.

This report intentionally does **not** claim BOM Export Package ZIP byte-for-byte equality. ZIP byte equality is not the correct assertion because generated package artifacts can include package/time-specific metadata and watermarked PDFs. The claimed ZIP gate is that the part-documentation document identity set remains stable across the reviewed cable-only option configurations, while configuration-derived artifacts are allowed to vary.

## Readiness verdict

READY TO MERGE for code review, subject to the normal human review/push/deploy process. Production was not touched.

## Option fixture tracking

Addendum 2 result: PASS / READY.

The reviewed `DEV-*` option catalog is now fixture-managed as configuration, not operational data.

### Fixture scope

`hooks.py` now exports only the reviewed development catalog:

```python
{
    "dt": "InductOne Configuration Option",
    "filters": [["option_code", "like", "DEV-%"]]
}
```

The child `InductOne Configuration Option Mapping` rows ride inside each parent option document. The child DocType is not exported as a separate record fixture.

### Portability check

Candidate parent naming is portable:

| Count | Result |
|---:|---|
| 13 `DEV-*` options | `name == option_code` for all 13 |
| 13 `DEV-*` options | `status == Defined-Ops` for all 13 |

The exported child mapping rows omit child-row `name` values and carry semantic fields: action, target item, target balloon, replacement item, quantity, and row order.

### Exported fixture

New fixture:

```text
inductone_tools/fixtures/inductone_configuration_option.json
```

Export result:

| Check | Result |
|---|---|
| Fixture option count | 13 |
| Non-`DEV-*` option leakage | None |
| Parent names | stable / deterministic |
| Mapping rows include `target_balloon` where expected | PASS |
| Fixture ↔ candidate DB ↔ oracle parity | PASS |

Option list:

- `DEV-BASELINE`
- `DEV-PANEL-MCP-STD`
- `DEV-PANEL-MCP`
- `DEV-PANEL-IPC-STD`
- `DEV-PANEL-IPC`
- `DEV-COMP-HMI-STD`
- `DEV-COMP-HMI`
- `DEV-COMP-STACK-STD`
- `DEV-COMP-STACK`
- `DEV-COMP-FORTRESS-STD`
- `DEV-COMP-FORTRESS`
- `DEV-COMP-MAGLOCK-STD`
- `DEV-COMP-MAGLOCK`

### Parity evidence

Candidate parity evidence:

```text
C:\hub\frappe-sandbox\validation-evidence\balloon_closeout_static_checks_20260708T141107Z.json
```

The close-out checker now validates:

- Client Script parity.
- Custom Field fixture shape.
- `DEV-*` option fixture parity against candidate DB and `inductone_tools.balloon_scoped_options`.
- Build-page group/default/exclusivity behavior.

All checks passed.

### Migrate round-trip evidence

Round-trip procedure on candidate:

1. Deleted all 13 `DEV-*` `InductOne Configuration Option` records.
2. Confirmed candidate count was 0.
3. Ran `bench --site inductone-candidate.localhost migrate`.
4. Confirmed migrate recreated all 13 records from fixture, all at `Defined-Ops`.
5. Reran fixture parity.
6. Reran the full 12-case candidate resolver matrix without `--load-options`.

Post-round-trip validation evidence:

```text
C:\hub\frappe-sandbox\validation-evidence\balloon_closeout_static_checks_20260708T141107Z.json
C:\hub\frappe-sandbox\validation-evidence\balloon_scoped_options_validation_20260708T141108Z.json
```

All 12 resolver cases passed after fixture recreation.

### Operational note

`scripts/load_balloon_scoped_options.py` remains the authoring/bootstrap tool for fresh candidate instances. Production and deployed environments receive these reviewed options through `bench migrate` from the scoped fixture. The options intentionally ship as `Defined-Ops`; release to `Released` remains a governed human action.
