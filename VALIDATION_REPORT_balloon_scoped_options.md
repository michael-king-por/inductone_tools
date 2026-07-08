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

## Hierarchy fix + full-suite validation

Date: 2026-07-08

### Root-cause confirmation

Production-data validation found a real hierarchy defect in the deployed balloon-scoped feature: the baseline-only snapshot dropped the legitimate standard cable row at balloon `173`, item `11283`, qty `2`. The master BOM ground truth is:

| Balloon | Standard | Option |
|---|---|---|
| `172` | `11245`, qty `3` | `11283`, qty `3` |
| `173` | `11283`, qty `2` | `11351`, qty `2` |

The defect was the exact regression this feature was meant to prevent: the same item code, `11283`, is an option row at balloon `172` and a standard row at balloon `173`. Any item-only remove/suppress path can remove too much.

Code review confirmed that `populate_snapshot_hierarchy` is intended to consume `bom_export.build_configured_rows` through an in-memory `BOM Export Package` stub. The corrective architecture is therefore single-resolution / multiple views: `build_configured_rows` is the canonical balloon-aware resolver, and hierarchy snapshots, hierarchy workbooks, snapshot diffs, and BOM Export Package output derive from that resolver. The `Configured BOM Snapshot Item` (`lines`) child table remains a balloon-blind material rollup and is not structural truth.

### Fix status

The local/current branch contains the balloon-aware resolver behavior that production commit `685661d` did not have:

- `target_balloon` is carried into snapshot structural effects.
- `REMOVE` suppression uses `(target_balloon, target_item)` when a balloon is present.
- `REPLACE` occurrence selection and deduplication include balloon identity.
- Duplicate BOM occurrences are preserved for hierarchy generation.
- The hierarchy populator explicitly documents that `.lines` must not be used for structural truth.

### Hardened validation suite

`scripts/run_balloon_scoped_options_validation.py` now enforces the full stage ladder for all 12 configurations:

1. Structural effects carry `target_balloon`.
2. Flat resolver output matches the independent oracle.
3. Materialized hierarchy content matches the independent oracle.
4. Generated hierarchy workbook content matches the independent oracle.
5. Flat, hierarchy, and workbook agree with each other on managed balloons and collision rollups.
6. Non-managed material remains conserved versus the baseline-only snapshot.

The suite also records observed managed/collision rollups so the sentinel regression is auditable from the JSON evidence, not merely inferred from a pass/fail line.

### Candidate validation result

Candidate was synced to current local `main` content, migrated, and loaded with the 13 reviewed `DEV-*` options before validation. Final post-round-trip evidence:

```text
C:\hub\frappe-sandbox\validation-evidence\balloon_scoped_options_validation_20260708T174507Z.json
C:\hub\frappe-sandbox\validation-evidence\balloon_export_zip_closeout_20260708T174734Z.json
C:\hub\frappe-sandbox\validation-evidence\dev_option_fixture_roundtrip_delete_20260708T174430Z.json
C:\hub\frappe-sandbox\validation-evidence\dev_option_fixture_roundtrip_after_migrate_20260708T174454Z.json
```

All 12 configurations passed all enforced stages:

| # | Configuration | Result |
|---:|---|---|
| 1 | baseline only | PASS |
| 2 | MCP | PASS |
| 3 | IPC | PASS |
| 4 | HMI | PASS |
| 5 | Stacklight | PASS |
| 6 | Fortress | PASS |
| 7 | Maglock | PASS |
| 8 | MCP + IPC | PASS |
| 9 | IPC + HMI | PASS |
| 10 | IPC + Maglock | PASS |
| 11 | MCP + Fortress | PASS |
| 12 | all six moved | PASS |

Explicit sentinel/collision results from final evidence:

| Case | Flat | Hierarchy | Workbook |
|---|---|---|---|
| Baseline | `172→11245 q3`, `173→11283 q2` | `172→11245 q3`, `173→11283 q2` | same |
| IPC | `172→11283 q3`, `173→11351 q2` | `172→11283 q3`, `173→11351 q2` | same |
| Everything moved | `172→11283 q3`, `173→11351 q2` | `172→11283 q3`, `173→11351 q2` | same |

The package closeout passed for baseline, IPC, and everything-moved. The part-documentation identity set was stable across those cable-only configurations: 340 part-documentation entries in each compared payload. Configuration-derived artifacts remain expected to vary by configuration.

### Artifact derivation trace

| Artifact | Derivation path |
|---|---|
| Flat configured rows / BOM Export Package item payload | `bom_export.build_configured_rows` |
| Materialized snapshot hierarchy | `snapshot.hierarchy.populate_snapshot_hierarchy` → in-memory package stub → `bom_export.build_configured_rows` |
| Hierarchy workbook | `snapshot.hierarchy.generate_hierarchy_workbook` reads materialized `Configured BOM Snapshot Hierarchy` |
| Snapshot diff | `snapshot_diff.loader.load_snapshot_nodes` reads materialized `Configured BOM Snapshot Hierarchy` |
| `Configured BOM Snapshot Item` / `.lines` | Balloon-blind material rollup; not structural truth; not used as the source for hierarchy/workbook/diff truth |

### Human-gated production re-validation

After human review, merge/deploy the corrective follow-up, then regenerate baseline and IPC snapshots on `SAL-ORD-2026-00054-BLD-0225` in production and run the same stage ladder read-only against those production snapshots. The required sentinel is baseline `173 → 11283 qty 2` present in hierarchy/workbook/flat, and IPC `172 → 11283 qty 3`, `173 → 11351 qty 2`.

Overall verdict: **READY for human review / governed deployment.**

## Status model + descriptions + signoff-release proof — 2026-07-08

### Verdict

**READY for human review / governed deployment.** Candidate validation passed the status cleanup, description grammar/resolver self-check, fixture round-trip, signoff→release proof, and final balloon-scoped stage ladder.

Important candidate-state note: the candidate DEV options intentionally end this proof at `Released` because the signoff proof approved all 13. The repo fixture still ships them as `Draft`; production options should remain `Draft` until a human approves each Engineering Signoff.

### Evidence

- A1 status inventory: `C:\hub\frappe-sandbox\validation-evidence\configuration_option_status_inventory_20260708T185558Z.json`
- A2 status cleanup: `C:\hub\frappe-sandbox\validation-evidence\configuration_option_status_cleanup_a2_20260708T185713Z.json`
- A3/A4 status trim + workflow removal: `C:\hub\frappe-sandbox\validation-evidence\configuration_option_status_trim_a3_a4_20260708T185821Z.json`
- Description self-check before round-trip: `C:\hub\frappe-sandbox\validation-evidence\configuration_option_description_self_check_20260708T185833Z.json`
- Fixture round-trip delete: `C:\hub\frappe-sandbox\validation-evidence\dev_option_fixture_roundtrip_delete_status_model_20260708T190205Z.json`
- Fixture round-trip recreate: `C:\hub\frappe-sandbox\validation-evidence\dev_option_fixture_roundtrip_after_migrate_status_model_20260708T190254Z.json`
- Description self-check after round-trip: `C:\hub\frappe-sandbox\validation-evidence\configuration_option_description_self_check_20260708T190255Z.json`
- Resolver ladder after round-trip: `C:\hub\frappe-sandbox\validation-evidence\balloon_scoped_options_validation_20260708T190312Z.json`
- Signoff release proof: `C:\hub\frappe-sandbox\validation-evidence\configuration_option_signoff_release_proof_20260708T190543Z.json`
- Final post-release resolver ladder: `C:\hub\frappe-sandbox\validation-evidence\balloon_scoped_options_validation_20260708T190558Z.json`

### A1/A2/A3/A4 status-model cleanup

- A1 inventory passed before changes: 33 total options, with `Defined-Ops` held only by the 13 reviewed `DEV-*` options; no `Defined-Product` rows existed. The inactive `InductOne Option Cycle` workflow existed with `is_active = 0`.
- A2 patch `v2026_07_08_configuration_option_status_model_cleanup` moved all 13 DEV options to `Draft`. Candidate post-patch counts: `Draft = 19`, `Released = 13`, `Deprecated = 1`.
- A3 trimmed the canonical `status` Select options to exactly `Draft`, `Released`, `Deprecated`. No rows hold retired statuses after migrate.
- A4 removed the inactive `InductOne Option Cycle` workflow. The `workflow_state` column remains present but all option rows are `NULL`; it is left as a documented harmless column rather than removed blindly.

### Description self-check

The self-check validates that each `builder_description` contains exactly one `Configuration effect:` marker and one `Notes:` marker, renders into non-empty sections, and that each moved option names exactly the resolver-derived part codes in its Configuration effect. `internal_notes` are checked as high-level rationale and fail if they contain known catalog part codes.

All 13 options passed before and after fixture round-trip.

### Full authored descriptions

#### `DEV-BASELINE` — Deviation — All Standard (Baseline)

Internal notes:

```text
Use for the standard electrical cable configuration when no electrical panel or component relocation deviations are required.
```

Builder description:

```text
Standard electrical cable baseline for the InductOne REV E electrical BOM.

Configuration effect:
All managed balloon callouts resolve to the standard BOM rows, and option/extension rows are pruned from the configurable electrical cable balloons.

Notes:
Always applied as the single-member required baseline group and not independently deselectable. Every other DEV option layers on this baseline.
```

#### `DEV-PANEL-MCP-STD` — MCP Panel — Standard

Internal notes:

```text
Use when the MCP panel remains in its standard location. Select the paired relocated option only when the MCP panel is moved from standard.
```

Builder description:

```text
MCP panel remains in the standard location.

Configuration effect:
No change. Baseline standard cabling applies.

Notes:
Default selection for this required option group. Mutually exclusive with the paired relocated option.
```

#### `DEV-PANEL-MCP` — Deviation — MCP Panel Relocated

Internal notes:

```text
Use when the MCP panel is relocated and the standard cable set needs the relocation extension cabling.
```

Builder description:

```text
MCP panel relocated from the standard electrical layout.

Configuration effect:
Adds extension rows: balloon 143 -> 1407402 (M12 D-CODE 5M extension); balloon 145 -> MCVP-12MMFP-5M (M23 12-pole 5M); balloon 149 -> 1276573 (M12 L-CODE 5M); balloon 156 -> RSM RKM 30-5M/S101 (7/8 in 3-pin 5M). No standard-row substitutions are made by this option.

Notes:
Paired with the standard option in the same required group; select only one. If this overlaps with the IPC panel relocation or a component relocation, the balloon-scoped resolver applies the same moved row once and prevents double cabling.
```

#### `DEV-PANEL-IPC-STD` — IPC Panel — Standard

Internal notes:

```text
Use when the IPC panel remains in its standard location. Select the paired relocated option only when the IPC panel is moved from standard.
```

Builder description:

```text
IPC panel remains in the standard location.

Configuration effect:
No change. Baseline standard cabling applies.

Notes:
Default selection for this required option group. Mutually exclusive with the paired relocated option.
```

#### `DEV-PANEL-IPC` — Deviation — IPC Panel Relocated

Internal notes:

```text
Use when the IPC panel is relocated and the electrical cable package needs the longer relocated-panel cable set.
```

Builder description:

```text
IPC panel relocated from the standard electrical layout.

Configuration effect:
Replaces balloon 137 with MCVP-19MFP-10M x2 (M23 x19 10M); balloon 140 with 1407379 (M12 D-CODE 10M); balloon 141 with 1407486 (M12 X-CODE 10M); balloon 144 with 1407363 (RJ45-M12 D 10M); balloon 154 with 1417892 (M12 A 4-pin 10M); balloon 159 with MDCM-8FP-10M-R  & MDC-8MP-FW11 x2 (M12 8-pin 10M combined item); balloon 172 with 11283 x3 (RJ45 6M); balloon 173 with 11351 x2 (RJ45 15M); balloon 190 with 1291280 (M12 L 10M); balloon 191 with 1000517 x4 (USB-A 10M extension plus 1M locking lead); balloon 193 with 1417903 (M12 A 5-pin 10M). Adds extension rows: balloon 145 -> MCVP-12MMFP-5M and balloon 156 -> RSM RKM 30-5M/S101.

Notes:
Paired with the standard option in the same required group; select only one. If this overlaps with the IPC panel relocation or a component relocation, the balloon-scoped resolver applies the same moved row once and prevents double cabling.
```

#### `DEV-COMP-HMI-STD` — HMI — Standard

Internal notes:

```text
Use when the HMI remains in its standard location. Select the paired relocated option only when the HMI is moved from standard.
```

Builder description:

```text
HMI remains in the standard location.

Configuration effect:
No change. Baseline standard cabling applies.

Notes:
Default selection for this required option group. Mutually exclusive with the paired relocated option.
```

#### `DEV-COMP-HMI` — Deviation — HMI Relocated

Internal notes:

```text
Use when the HMI is relocated and only the HMI-related electrical cables need the relocated lengths.
```

Builder description:

```text
HMI relocated from the standard electrical layout.

Configuration effect:
Replaces balloon 140 with 1407379 (M12 D-CODE 10M); balloon 141 with 1407486 (M12 X-CODE 10M); balloon 154 with 1417892 (M12 A 4-pin 10M). No other managed balloons are changed by this option.

Notes:
Paired with the standard option in the same required group; select only one. If this overlaps with the IPC panel relocation or a component relocation, the balloon-scoped resolver applies the same moved row once and prevents double cabling.
```

#### `DEV-COMP-STACK-STD` — Stacklight — Standard

Internal notes:

```text
Use when the stacklight remains in its standard location. Select the paired relocated option only when the stacklight is moved from standard.
```

Builder description:

```text
Stacklight remains in the standard location.

Configuration effect:
No change. Baseline standard cabling applies.

Notes:
Default selection for this required option group. Mutually exclusive with the paired relocated option.
```

#### `DEV-COMP-STACK` — Deviation — Stacklight Relocated

Internal notes:

```text
Use when the stacklight is relocated and only the stacklight electrical cable needs the relocated length.
```

Builder description:

```text
Stacklight relocated from the standard electrical layout.

Configuration effect:
Replaces balloon 193 with 1417903 (M12 A 5-pin 10M). No other managed balloons are changed by this option.

Notes:
Paired with the standard option in the same required group; select only one. If this overlaps with the IPC panel relocation or a component relocation, the balloon-scoped resolver applies the same moved row once and prevents double cabling.
```

#### `DEV-COMP-FORTRESS-STD` — Fortress — Standard

Internal notes:

```text
Use when the Fortress safety component remains in its standard location. Select the paired relocated option only when Fortress is moved from standard.
```

Builder description:

```text
Fortress safety component remains in the standard location.

Configuration effect:
No change. Baseline standard cabling applies.

Notes:
Default selection for this required option group. Mutually exclusive with the paired relocated option.
```

#### `DEV-COMP-FORTRESS` — Deviation — Fortress Relocated

Internal notes:

```text
Use when Fortress is relocated and only the Fortress electrical cable needs the relocated length.
```

Builder description:

```text
Fortress safety component relocated from the standard electrical layout.

Configuration effect:
Replaces balloon 137 with MCVP-19MFP-10M x2 (M23 x19 10M). No other managed balloons are changed by this option.

Notes:
Paired with the standard option in the same required group; select only one. If this overlaps with the IPC panel relocation or a component relocation, the balloon-scoped resolver applies the same moved row once and prevents double cabling.
```

#### `DEV-COMP-MAGLOCK-STD` — Magnet Lock — Standard

Internal notes:

```text
Use when the magnet lock remains in its standard location. Select the paired relocated option only when the magnet lock is moved from standard.
```

Builder description:

```text
Magnet lock remains in the standard location.

Configuration effect:
No change. Baseline standard cabling applies.

Notes:
Default selection for this required option group. Mutually exclusive with the paired relocated option.
```

#### `DEV-COMP-MAGLOCK` — Deviation — Magnet Lock Relocated

Internal notes:

```text
Use when the magnet lock is relocated and only the magnet-lock electrical cable needs the relocated length.
```

Builder description:

```text
Magnet lock relocated from the standard electrical layout.

Configuration effect:
Replaces balloon 159 with MDCM-8FP-10M-R  & MDC-8MP-FW11 x2 (M12 8-pin 10M combined item). No other managed balloons are changed by this option.

Notes:
Paired with the standard option in the same required group; select only one. If this overlaps with the IPC panel relocation or a component relocation, the balloon-scoped resolver applies the same moved row once and prevents double cabling.
```

### Fixture round-trip

Candidate deleted all 13 `DEV-*` option records and 38 mapping child rows, ran `bench migrate`, and confirmed fixtures recreated all 13 records at `Draft` with matching `internal_notes`, matching `builder_description`, and expected mapping counts. A full 12-case resolver ladder then passed from the fixture-recreated catalog.

### Engineering Signoff → auto-Release proof

The candidate proof ran against all 13 recreated Draft options as `michael.king@plusonerobotics.com`:

- manual Draft→Released save was blocked by `on_target_save`;
- `request_signoff` succeeded from Draft;
- `approve_signoff` succeeded with `mapping_status == Complete`;
- each option became `Released`;
- each signoff became `Approved`;
- release side-effect comments were stamped;
- Released option edit attempts were blocked;
- `request_signoff` on Released options was rejected.

### Final balloon-scoped ladder

After the signoff proof left candidate options Released, the full 12-case balloon-scoped validation passed again. Flat, hierarchy, and workbook outputs still matched the independent oracle, including the collision sentinel rows.
