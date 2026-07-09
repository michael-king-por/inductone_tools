# InductOne CSA Prime-Time Gap Assessment

Date: 2026-07-09  
Environment validated: candidate sandbox only  
Candidate site: `inductone-candidate.localhost`  
Candidate bench: `/home/michaelplusone/frappe-sandbox/benches/candidate-bench`  
Evidence folder: `C:\hub\frappe-sandbox\validation-evidence`

This report records what was validated in candidate, what intentions are now clear and evidence-backed, and what still blocks a defensible claim that the InductOne CSA process is 100% complete, hardened, presentable, and ready for unsupervised production ownership.

## Executive status

The InductOne option-resolution and evidence-generation layer is in strong shape. The candidate bench reproduced the REV E option math, generated per-option snapshot diffs, validated builder package part-documentation stability, and passed the permission hardening gates.

The system is not yet 100% prime-time as a complete CSA lifecycle because the full business workflow has not been proven from Sales Order / Build creation through release, builder acknowledgement, completion upload, review, acceptance, and As-Built instance creation on a realistic build. Current transition validation proves role gates and method reachability, not the complete domain-success path.

## Candidate preparation and mechanical checks

| Check | Result | Evidence / note |
|---|---:|---|
| Candidate app code synced from local repo working tree | PASS | Candidate app import restored; `inductone_tools.__init__` no longer zero-byte |
| Candidate migrate | PASS | `bench --site inductone-candidate.localhost migrate` completed |
| Server scripts enabled | PASS | `server_script_enabled=True` |
| Candidate backup freshness check | PASS with caveat | `backup_freshness_inductone-candidate_localhost_20260709T162635Z.json`; newest backup file was `20260630_112423-plusonerobotics_v_frappe_cloud-private-files.tar`, validated under a 720-hour threshold, not a same-day restore |
| Python compile | PASS | `python -m compileall inductone_tools scripts` |
| Fixture JSON parse | PASS | 11 fixture files parsed |

## Validated intentions

### 1. Role hardening and direct API denial

| Intent | Result | Evidence |
|---|---:|---|
| Unauthorized users cannot call critical signoff methods directly | PASS | `method_negative_tests_20260709T162635Z.json` |
| Unauthorized users cannot allocate part numbers directly | PASS | `method_negative_tests_20260709T162635Z.json` |
| External builders cannot call release / accept methods directly | PASS | `method_negative_tests_20260709T162635Z.json` |
| Candidate role assignments can be synced to production governance state | PASS | `candidate_production_role_assignment_sync_20260709T162752Z.json` |
| Production post-deploy permission validator passes in candidate | PASS | `production_post_deploy_validation_20260709T162805Z.json` |
| Static link audit has only accepted exceptions | PASS | `static_link_dependency_audit_20260709T162830Z.json` |

Accepted static-link exceptions observed by the gate:

- `Country` link reads for `Address.country`.
- `User` link reads for display/audit fields such as `reserved_by` / `generated_by`.
- `Builder Portal` is intentionally external-builder-only.

### 2. Builder access and isolation

| Intent | Result | Evidence |
|---|---:|---|
| External builders are denied raw Item access | PASS | `production_post_deploy_validation_20260709T162805Z.json` |
| External builders are denied raw BOM access | PASS | `production_post_deploy_validation_20260709T162805Z.json` |
| Both external builders are covered (`motion.builder`, `lam`) | PASS | `production_post_deploy_validation_20260709T162805Z.json` |
| Operations workspace visible to internal roles | PASS | `operations_workspace_visibility_20260709T164224Z.json` |
| Operations workspace hidden from external builders | PASS | `operations_workspace_visibility_20260709T164224Z.json` |
| Builder Portal role restriction is external-builder-only | PASS | `workspace_role_tables_20260709T164335Z.jsonl` |
| Quality workspace is hidden | PASS | `workspace_role_tables_20260709T164335Z.jsonl` |

Workspace role table snapshot:

- `Builder Portal`: roles = `InductOne External Builder`, `is_hidden=0`.
- `Operations`: roles = `Operations Manager`, `Operations Viewer`, `Engineering User`, `Procurement User`, `Finance Viewer`, `InductOne Manager`, `InductOne Process Architect`, `is_hidden=0`.
- `Quality`: roles = `Builder`, `is_hidden=1`.

Note: generic `has_permission("Workspace")` is not a reliable test for Desk page visibility because Workspace documents are public DocType records. Use Workspace role rows and browser/Desk route smoke tests for page visibility assertions.

### 3. Finance / operations report dependencies

| Intent | Result | Evidence |
|---|---:|---|
| Finance Viewer can execute critical stock reports | PASS | `production_post_deploy_validation_20260709T162805Z.json` |
| Finance/Operations read-only dependency DocTypes are present | PASS | `production_post_deploy_validation_20260709T162805Z.json` |
| Fixture Export Control remains denied to viewer/finance roles | PASS | `production_post_deploy_validation_20260709T162805Z.json` |

This covers the previously found Matt Speer regression class: Stock Balance / Stock Ledger dependencies.

### 4. DEV option catalog status, descriptions, and release gatekeeping

| Intent | Result | Evidence |
|---|---:|---|
| 13 `DEV-%` options are present, active, and released in candidate DB | PASS | Direct DB inspection on 2026-07-09 |
| Option descriptions pass self-check | PASS | `configuration_option_description_self_check_20260709T163940Z.json` |
| Manual Draft -> Released mutation is blocked | PASS | `configuration_option_signoff_release_proof_20260709T163941Z.json` |
| Signoff/release proof passes for the 13 DEV options | PASS | `configuration_option_signoff_release_proof_20260709T163941Z.json` |

The status inventory script returned FAIL because candidate also contains non-DEV options in Draft/Deprecated states:

```json
{
  "Deprecated": 1,
  "Draft": 19,
  "Released": 13
}
```

The 13 DEV options themselves were confirmed live as `Released` and `is_active=1`. This is not a blocker for the DEV option set, but it is a presentability issue unless the remaining Draft/Deprecated catalog entries are intentionally hidden or clearly governed.

### 5. REV E balloon-scoped option resolution

| Intent | Result | Evidence |
|---|---:|---|
| Build `SAL-ORD-2026-00054-BLD-0225` exists in candidate | PASS | `balloon_scoped_options_validation_20260709T163356Z.json` |
| REV E master BOM is active/submitted | PASS | `balloon_scoped_options_validation_20260709T163356Z.json` |
| REV E configurable balloon fingerprint is present | PASS | 26 configurable balloon rows found |
| `0921` fixed `1417891` balloon 315 is present | PASS | `balloon_scoped_options_validation_20260709T163356Z.json` |
| Build Script carries `target_balloon` through the freeze path | PASS | `balloon_scoped_options_validation_20260709T163356Z.json` |
| `target_balloon` custom fields are fixture-managed | PASS | `balloon_scoped_options_validation_20260709T163356Z.json` |
| All 12 option matrix cases resolve and populate hierarchy/workbook | PASS | `balloon_scoped_options_validation_20260709T163356Z.json` |

The first run at `20260709T162854Z` hit MariaDB deadlocks while inserting hierarchy rows for `baseline_only`, `ipc`, and `hmi`. A clean rerun passed all 12 cases. Treat this as a reliability observation: the semantic option math is validated, but the hierarchy population path should ideally become retry-safe/idempotent around deadlocks.

### 6. Generated documents and evidence artifacts

| Artifact / document path | Result | Evidence |
|---|---:|---|
| Per-option snapshot diff XLSX + JSON for 7 deviations | PASS | `per_option_snapshot_diff_index_20260709T164043Z.json`, `per_option_snapshot_diff_manifest_20260709T164043Z.md` |
| Baseline vs MCP relocated | PASS | `snapshot_diff_SAL-ORD-2026-00054-BLD-0225_baseline_vs_mcp_relocated_20260709T164043Z.xlsx/json` |
| Baseline vs IPC relocated | PASS | `snapshot_diff_SAL-ORD-2026-00054-BLD-0225_baseline_vs_ipc_relocated_20260709T164043Z.xlsx/json` |
| Baseline vs HMI relocated | PASS | `snapshot_diff_SAL-ORD-2026-00054-BLD-0225_baseline_vs_hmi_relocated_20260709T164043Z.xlsx/json` |
| Baseline vs Stacklight relocated | PASS | `snapshot_diff_SAL-ORD-2026-00054-BLD-0225_baseline_vs_stacklight_relocated_20260709T164043Z.xlsx/json` |
| Baseline vs Fortress relocated | PASS | `snapshot_diff_SAL-ORD-2026-00054-BLD-0225_baseline_vs_fortress_relocated_20260709T164043Z.xlsx/json` |
| Baseline vs Maglock relocated | PASS | `snapshot_diff_SAL-ORD-2026-00054-BLD-0225_baseline_vs_maglock_relocated_20260709T164043Z.xlsx/json` |
| Baseline vs Everything moved | PASS | `snapshot_diff_SAL-ORD-2026-00054-BLD-0225_baseline_vs_everything_moved_20260709T164043Z.xlsx/json` |
| Builder package part-documentation payload is stable across cable deviations | PASS | `balloon_export_zip_closeout_20260709T163618Z.json` |
| User notes round-trip through resolver, snapshot hierarchy, package item, workbook, and diff | PASS | `user_notes_roundtrip_validation_1783614553.json` |
| Balloon report returns expected rows | PASS | `balloon_report_validation_20260709T162833Z.json` |

The package closeout validates that configuration-derived artifacts may vary while part-documentation payloads remain stable for these cable-only deviations:

- `baseline_only`: 340 part-documentation entries.
- `ipc`: 340 part-documentation entries.
- `everything_moved`: 340 part-documentation entries.
- Baseline vs IPC part-document identity: PASS.
- Baseline vs Everything Moved part-document identity: PASS.

## Current prime-time gaps

These are the remaining blockers or hardening opportunities before the system can honestly be described as 100% complete, hardened, presentable, and ready for full ownership handoff.

### Closed gap — Full business lifecycle is now proven end-to-end in candidate

Closed on 2026-07-09 by `scripts/run_inductone_csa_lifecycle_smoke.py`. Passing evidence: `inductone_csa_lifecycle_smoke_20260709T171616Z.json`.

The smoke created synthetic candidate Build `SAL-ORD-2026-00054-BLD-0455`, generated snapshot/hierarchy/CO/package artifacts, ensured top-BOM signoff, allocated serial `IND-3006`, released to builder, acknowledged as `motion.builder@plusonerobotics.com`, uploaded a filled completion workbook, reviewed it, accepted it, created locked As-Built `SAL-ORD-2026-00054-BLD-0455-ASBUILT-460`, and created Instance `IND-3006`.

Two implementation defects were found and fixed during this gate:

- `flat_bom_status = Pending` was still written by the CO after-insert hook even though the DocType now allows only `Queued/Running/Complete/Failed`; fixed to `Queued`.
- Accepted As-Built serial rows were not copied into `InductOne Instance.component_serials`; fixed and asserted. Final passing smoke shows As-Built serial rows = 34 and Instance component serial rows = 34.

### Gap 2 — Snapshot hierarchy insertion should be retry-safe

The first artifact validation pass hit MariaDB `QueryDeadlockError` during hierarchy insertion. A clean rerun passed, so this is not a semantic option failure. Still, a prime-time process should not depend on rerunning a validation script after a deadlock.

Recommended hardening:

- Add retry handling around `_clear_snapshot_hierarchy` / `_insert_hierarchy_rows` or the outer `populate_snapshot_hierarchy` call.
- Write an execution test that intentionally reruns hierarchy population on the same snapshot and proves idempotency under repeated calls.

### Gap 3 — Catalog status inventory still contains Draft/Deprecated non-DEV options

The 13 DEV options are released and valid. Candidate also contains other active inventory states:

- 19 Draft.
- 1 Deprecated.

This may be intentional, but it is not presentable unless:

- Draft/Deprecated options are hidden from normal build selection.
- The catalog page/print format clearly separates Released vs Draft/Deprecated.
- There is an owner-approved policy for keeping draft options in the same DocType.

### Gap 4 — Release readiness breadth is still partially architectural

The release code includes readiness checks for top BOM engineering signoff, and helper code exists for broader readiness inspection. The validated release proof does not yet demonstrate every intended gate across:

- Top Item.
- Product Bundle.
- Selected configuration options.
- Top BOM.
- Generated package artifacts.

This should be closed by a candidate full-release validation script that fails if any required signoff/gate is missing.

### Gap 5 — Builder portal access should get one browser-driven smoke pass after each workspace change

Workspace role tables are correct, and external builders are denied raw Item/BOM access. However, Desk behavior can differ from raw DocPerm queries. The previous browser-driven GUI smoke was valuable; this report did not rerun the full browser smoke.

Recommended hardening:

- Re-run browser route smoke for `motion.builder` and `lam`.
- Confirm visible landing page is Builder Portal.
- Confirm Operations/Engineering/Stock/Items/Sales Orders/BOMs are not reachable from Desk.
- Capture screenshots or route result JSON.

### Gap 6 — “No assumptions” documentation still needs production-owner annotation

The architecture docs now map the intended object chain, but several business policies require owner confirmation before the documentation can be considered handoff-complete:

- Whether generated validation snapshots on real builds are acceptable or should use scratch builds only.
- Which Draft/Deprecated configuration options should remain visible anywhere.
- Whether the Builder Portal should be the only visible page for external builders, or whether generic Home/Stock public workspaces must be explicitly hidden from their sidebar experience.
- The exact acceptance criteria for “builder completion reviewed” versus “accepted as-built.”

## Recommended next validation gate

The candidate lifecycle smoke now passes, and the first follow-up hardening gate has also passed.

Closed on 2026-07-09:

1. `acknowledge_builder_release()` now has direct role/supplier gating.
2. Unauthorized Operations Viewer acknowledgement is denied before document lookup.
3. Wrong-supplier external builder acknowledgement is denied before state mutation.
4. Release readiness negative checks fail closed for missing serial, snapshot, CO, package, and top BOM.
5. Repeated hierarchy population is idempotent on the candidate snapshot: 1,307 rows before/after two runs.
6. Motion and LAM browser route smoke passed 22/22 checks with screenshots.

Next highest-value validation gate:

1. Expand the release-readiness negative matrix to selected Configuration Option not Released, Product Bundle signoff missing, Top Item signoff missing, package exists but is not Complete, and CO snapshot drift.
2. Convert the “what happens next” status guidance into UI affordances on the Build/CO forms.
3. Package the evidence bundle for owner handoff.

## Evidence index from this validation pass

- `backup_freshness_inductone-candidate_localhost_20260709T162635Z.json`
- `method_negative_tests_20260709T162635Z.json`
- `workflow_transition_smoke_20260709T162738Z.json`
- `candidate_production_role_assignment_sync_20260709T162752Z.json`
- `production_post_deploy_validation_20260709T162805Z.json`
- `static_link_dependency_audit_20260709T162830Z.json`
- `workspace_visibility_audit_20260709T162832Z.json`
- `balloon_report_validation_20260709T162833Z.json`
- `balloon_scoped_options_validation_20260709T163356Z.json`
- `balloon_export_zip_closeout_20260709T163618Z.json`
- `configuration_option_status_inventory_20260709T163924Z.json`
- `configuration_option_description_self_check_20260709T163940Z.json`
- `configuration_option_signoff_release_proof_20260709T163941Z.json`
- `per_option_snapshot_diff_index_20260709T164043Z.json`
- `per_option_snapshot_diff_manifest_20260709T164043Z.md`
- `operations_workspace_visibility_20260709T164224Z.json`
- `workspace_role_tables_20260709T164335Z.jsonl`
- `user_notes_roundtrip_validation_1783614553.json`


- `inductone_csa_lifecycle_smoke_20260709T171616Z.json`
- `inductone_csa_hardening_gates_20260709T190616Z.json`
- `method_negative_tests_20260709T190708Z.json`
- `gui-smoke-external-builders-20260709T1930Z/`
- `candidate_migrate_inductone_csa_wiki_hardening_20260709T1932Z.txt`
