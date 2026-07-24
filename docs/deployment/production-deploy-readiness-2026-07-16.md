# Production Deploy Readiness — 2026-07-16

Deploy target evaluated: `main@b03c30d` plus uncommitted convergence patch `v2026_07_16_custom_docperm_legacy_convergence`

Candidate site: `inductone-candidate.localhost`

Production backup restored into candidate: `20260716_043025` from `C:\Users\MichaelKing\Downloads`

## Result

The previous Phase 1 blocker is resolved:

- Custom DocPerm rows converged from `549` to `446`.
- Duplicate Custom DocPerm permission-key groups converged from `103` to `0`.
- Deterministic fixture keys remained intact.
- Effective Custom DocPerm capability delta was `0`; the deleted rows were duplicate legacy DB-local rows, not additional effective grants.

The current deployment gate still fails at the pre-deploy permission gate:

- `Finance Viewer` is missing curated business/audit report access for:
  - `Balance Sheet`
  - `General Ledger`
  - `Trial Balance`

Evidence:

- Restore log: `C:\hub\frappe-sandbox\validation-evidence\candidate_clean_restore_20260716_043025_20260716.txt`
- Restore hashes: `C:\hub\frappe-sandbox\validation-evidence\candidate_clean_restore_20260716_043025_sha256_20260716.txt`
- Role sync: `C:\hub\frappe-sandbox\validation-evidence\candidate_production_role_assignment_sync_20260717T134643Z.json`
- Initial first migrate: `C:\hub\frappe-sandbox\validation-evidence\candidate_migrate_first_20260716.txt`
- Initial second migrate: `C:\hub\frappe-sandbox\validation-evidence\candidate_migrate_second_20260716.txt`
- Convergence patch migrate: `C:\hub\frappe-sandbox\validation-evidence\candidate_migrate_convergence_patch_retry_20260716.txt`
- Convergence idempotency migrate: `C:\hub\frappe-sandbox\validation-evidence\candidate_migrate_convergence_idempotency_20260716.txt`
- Deleted-row snapshot: `C:\hub\frappe-sandbox\validation-evidence\custom_docperm_legacy_convergence_deleted_20260717T140504Z.json`
- Manual idempotency snapshot: `C:\hub\frappe-sandbox\validation-evidence\custom_docperm_legacy_convergence_deleted_20260717T140745Z.json`
- Before effective snapshot: `C:\hub\frappe-sandbox\validation-evidence\custom_docperm_effective_before_cleanup_20260716.json`
- After effective snapshot: `C:\hub\frappe-sandbox\validation-evidence\custom_docperm_effective_after_cleanup_20260716.json`
- Effective delta: `C:\hub\frappe-sandbox\validation-evidence\custom_docperm_effective_cleanup_diff_20260716.json`
- Orphan/outlier counts: `C:\hub\frappe-sandbox\validation-evidence\fixture_orphan_counts_20260716.json`
- Compileall: `C:\hub\frappe-sandbox\validation-evidence\readiness_compileall_20260716.txt`
- Fixture parse: `C:\hub\frappe-sandbox\validation-evidence\readiness_fixture_parse_20260716.txt`
- Usability validation: `C:\hub\frappe-sandbox\validation-evidence\usability_guidance_validation_20260717T141422Z.json`
- Wiki fixture validation: `C:\hub\frappe-sandbox\validation-evidence\wiki_fixture_validation_20260716.json`
- Wiki IA audit: `C:\hub\frappe-sandbox\validation-evidence\wiki_information_architecture_audit_20260717T141423Z.json`
- Pre-deploy gate: `C:\hub\frappe-sandbox\validation-evidence\production_post_deploy_validation_20260717T141426Z.json`

## Phase 0 — Candidate preparation

| Check | Result | Evidence |
|---|---:|---|
| Candidate restored from latest production backup | PASS | `candidate_clean_restore_20260716_043025_20260716.txt` |
| Candidate site config preserved instead of restoring production site config | PASS | `candidate_site_config_preserved_clean_restore_20260716_043025_20260716.json` |
| Candidate app synced to deploy target `b03c30d` | PASS | command output in session; candidate app was pinned to `HEAD=b03c30d` before patch sync |
| Candidate users synced to verified production assignments | PASS | `candidate_production_role_assignment_sync_20260717T134643Z.json` |

## Phase 1 — Migration and fixture convergence

| Check | Result | Evidence |
|---|---:|---|
| First candidate migrate | PASS | `candidate_migrate_first_20260716.txt` |
| Second candidate migrate / idempotency | PASS | `candidate_migrate_second_20260716.txt` |
| Custom DocPerm convergence patch migrate | PASS | `candidate_migrate_convergence_patch_retry_20260716.txt` |
| Post-convergence migrate / idempotency | PASS | `candidate_migrate_convergence_idempotency_20260716.txt` |
| Manual patch-function idempotency | PASS | `custom_docperm_convergence_manual_idempotency_20260716.txt` |

### Custom DocPerm convergence numbers

| Metric | Before | After |
|---|---:|---:|
| Custom DocPerm rows | 549 | 446 |
| Unique `(parent, role, permlevel, if_owner)` keys | 446 | 446 |
| Duplicate groups | 103 | 0 |
| Effective permission changes | — | 0 |

Owner sign-off item: the convergence patch deletes 103 legacy DB-local duplicate `Custom DocPerm` rows in production. The evidence shows those deletes do not change effective Custom DocPerm capabilities in candidate; nevertheless, this is a production permission-table cleanup and should be explicitly acknowledged before deploy.

Deleted rows are snapshotted before deletion. Re-insertion is possible from the snapshot JSON, but the primary rollback remains the fresh pre-deploy production backup.

## Exact patch manifest

| Patch | Purpose | Reversibility note |
|---|---|---|
| `v2026_06_29_finance_stock_report_access` | Restores read/report dependencies needed by Finance Viewer and Operations Viewer stock reports. | Additive Custom DocPerm changes; rollback requires DB restore or explicit cleanup. |
| `v2026_06_29_transaction_role_stock_dependencies` | Grants stock transaction dependency permissions for Operations Manager, Inventory Operator, and Gripper Manufacturer. | Additive Custom DocPerm changes; rollback requires DB restore or explicit cleanup. |
| `v2026_06_29_operations_workspace_visibility` | Makes Operations workspace visible to intended internal roles. | Workspace role rows can be reverted by fixture/app rollback plus migrate; DB restore is cleanest. |
| `v2026_06_29_link_dependency_read_grants` | Adds managed read grants for link-field dependencies while avoiding unmanaged replace-trap doctypes. | Additive Custom DocPerm changes; rollback requires DB restore or explicit cleanup. |
| `v2026_06_29_snapshot_stock_entry_type_permissions` | Snapshot-manages Stock Entry Type permission dependency safely. | Additive/managed permission rows; DB restore is cleanest rollback. |
| `v2026_06_29_hide_unused_quality_workspace` | Hides unused Quality workspace. | Reversible by restoring previous workspace state or app rollback + migrate. |
| `v2026_07_06_balloon_report_access` | Grants/report-manages electrical balloon callout report access. | Reversible by fixture/app rollback + migrate; report rows may remain unless explicitly removed. |
| `v2026_07_08_configuration_option_status_model_cleanup` | Cleans configuration option status model and released-option behavior. | Data/status changes should be rolled back from backup if needed. |
| `v2026_07_10_builder_portal_workspace_cleanup` | Cleans builder portal workspace visibility/content. | Reversible by fixture/app rollback + migrate. |
| `v2026_07_13_release_options_with_approved_signoffs` | Releases configuration options with approved Engineering Signoffs. | Data status changes should be rolled back from backup if needed. |
| `v2026_07_13_wiki_csa_space_links` | Adds/reconciles CSA wiki space links. | Reversible by fixture/app rollback + migrate, with caveat for DB-local wiki edits. |
| `v2026_07_13_external_builder_workspace_isolation` | Restricts external builders to Builder Portal visibility. | Reversible by fixture/app rollback + migrate. |
| `v2026_07_14_operations_manager_account_read` | Adds account read access required by Operations Manager. | Additive Custom DocPerm changes; rollback requires DB restore or explicit cleanup. |
| `v2026_07_15_retire_gui_server_scripts` | Retires GUI server scripts as production source-of-truth. | Reversible by DB restore or by re-enabling scripts deliberately. |
| `v2026_07_15_customer_rooted_fco_locations` | Adds Customer-rooted POR Physical Location hierarchy behavior. | Schema/data changes; DB restore is cleanest rollback. |
| `v2026_07_16_custom_docperm_legacy_convergence` | Deletes legacy random-name duplicate Custom DocPerm rows only when a deterministic fixture-owned row exists for the same permission key. | Deleted rows are snapshotted before deletion; can be reinserted from snapshot if needed. Primary rollback is fresh DB backup restore. |
| `v2026_07_16_finance_core_report_access` | Adds `Finance Viewer` to standard ERPNext `Balance Sheet`, `General Ledger`, and `Trial Balance` reports without fixture-owning the full report definitions. | Additive Report role rows; rollback by removing the role rows or restoring the pre-deploy DB backup. |
| `v2026_07_17_custom_docperm_global_viewer_convergence` | Re-runs deterministic Custom DocPerm convergence after the Global Viewer fixture expansion so newly fixture-owned legacy duplicate rows are removed. | Same rollback surface as the 2026-07-16 convergence patch: deleted rows are snapshotted; primary rollback is fresh DB backup restore. |

## Phase 2 — Full validation suite

| Validation | Result | Notes |
|---|---:|---|
| `python -m compileall inductone_tools scripts` | PASS | `readiness_compileall_20260716.txt` |
| Fixture JSON parse | PASS | 17 fixture JSON files parsed |
| Automated candidate permission audit | PASS | Ran before later gate failure; evidence in `candidate_permission_audit_20260716.txt` |
| Direct method negative tests | PASS | Ran before later gate failure; evidence in `method_negative_tests_20260716.txt` |
| Workflow transition smoke | PASS | Ran before later gate failure; evidence in `workflow_transition_smoke_20260716.txt` |
| CSA lifecycle smoke | PASS | Ran before later gate failure; evidence in generated lifecycle JSON |
| Release-gate matrix | PASS | Ran before later gate failure; evidence in generated release-gate JSON |
| Hardening gates | PASS | `inductone_csa_hardening_gates_20260717T141218Z.json` |
| Engineering Signoff invocation validation | PASS | Drawing trigger absent; native attachment regression passed |
| Usability guidance validation | PASS | Validation script updated to current deviation-control wording |
| Wiki fixture validation | PASS | 16 pages |
| Wiki IA audit | PASS with improvement/review findings | IA findings are advisory, not deploy blockers |
| GUI smoke internal + external builders | NOT RUN | Stopped after regression diff surfaced residual owner-review losses |

## Phase 3 — Pre-deploy gate and regression diff

Pre-deploy permission gate result: PASS.

Evidence:

- `C:\hub\frappe-sandbox\validation-evidence\production_post_deploy_validation_20260717T163945Z.json`
- `C:\hub\frappe-sandbox\validation-evidence\static_link_dependency_audit_20260717T164012Z.json`
- `C:\hub\frappe-sandbox\validation-evidence\workspace_visibility_audit_20260717T164014Z.json`
- `C:\hub\frappe-sandbox\validation-evidence\balloon_report_validation_20260717T164014Z.json`

The previous failure, `finance_viewer_business_report_access`, is resolved. `Finance Viewer` now appears on:

- `Balance Sheet`
- `General Ledger`
- `Trial Balance`

Effective-permission regression diff result: OWNER REVIEW REQUIRED.

Evidence: `C:\hub\frappe-sandbox\validation-evidence\effective_permission_regression_diff_20260717T164155Z.json`

Summary:

- Missing candidate users: `0`
- Expected disabled users missing from candidate: `0`
- Users with residual losses: `6`
- Residual lost capabilities: `1148`

Residual losses grouped by user:

| User | Lost capabilities | Review note |
|---|---:|---|
| `david.moreno@plusonerobotics.com` | 6 | Likely intended broad-role cleanup; owner Bucket-A review required. |
| `jason.minica@plusonerobotics.com` | 38 | Likely intended engineering-role narrowing; owner Bucket-A review required. |
| `wayne.kirk@plusonerobotics.com` | 38 | Likely intended engineering-role narrowing; owner Bucket-A review required. |
| `matt.speer@plusonerobotics.com` | 1062 | Likely intended finance-role narrowing from broad prior access; owner Bucket-A review required. |
| `motion.builder@plusonerobotics.com` | 2 | External builder loss of raw `BOM Export Package` / `Configured BOM Snapshot` access is expected if builder files are delivered through released Configuration Order package/index instead of raw Desk lists. Owner confirmation still required for deployment sign-off. |
| `lam@plusonerobotics.com` | 2 | Same expected external-builder raw-record isolation note as Motion. |

## Out-of-scope orphan-row counts for follow-on triage

No rows were auto-deleted outside the convergence patch scope.

| Area | DB rows/names without fixture equivalent |
|---|---:|
| Custom DocPerm keys | 171 |
| Workspace names | 15 |
| Client Script names | 0 |
| Report names | 198 |
| Custom Field names | 41 |
| Module Onboarding names | 10 |

Evidence: `C:\hub\frappe-sandbox\validation-evidence\fixture_orphan_counts_20260716.json`

## Residual owner review items

- `hana.macinnis@plusonerobotics.com` remains the known undecided account from the production role-assignment sync and still needs owner disposition.
- Owner sign-off is required for the Custom DocPerm duplicate cleanup patch even though candidate shows zero effective permission changes.
- Owner Bucket-A sign-off is required for the residual effective-permission diff losses listed above.

## Owner residual-loss resolution attempt — 2026-07-17

Owner requested a new `Global Viewer` role to replace Matt Speer's broad `System Manager` access with read/report/export/print coverage across every applicable DocType and no mutation/admin authority.

Implemented locally/candidate:

- Added fixture-managed role `Global Viewer` with Desk access.
- Expanded `custom_docperm.json` to deterministic `perm_*` ownership for all applicable non-child DocTypes, including Single DocTypes and system/internal DocTypes per owner decision.
- Global Viewer fixture grant profile: `read=1`, `report=1`, `export=1`, `print=1`; `write/create/delete/submit/cancel/amend/import=0`.
- Updated candidate/production-intent assignments:
  - `matt.speer@plusonerobotics.com` -> `Global Viewer` only; removed `System Manager` and `Finance Viewer`.
  - `jason.minica@plusonerobotics.com` -> `Engineering User`, `Operations Viewer`.
  - `wayne.kirk@plusonerobotics.com` -> `Engineering User`, `Operations Viewer`.
  - `david.moreno@plusonerobotics.com` -> `Engineering User`, `Operations Viewer`; removed `Operations Manager`.

Custom DocPerm convergence after Global Viewer expansion:

| Metric | Result |
|---|---:|
| DB Custom DocPerm rows | 1744 |
| Fixture Custom DocPerm rows | 1744 |
| Unique permission keys | 1744 |
| Duplicate permission-key groups | 0 |
| Non-deterministic Custom DocPerm names | 0 |
| DB Custom DocPerm keys without fixture equivalent | 0 |
| Global Viewer rows | 473 |
| Global Viewer rows with mutation bits | 0 |

Evidence:

- Convergence snapshot from `v2026_07_17_custom_docperm_global_viewer_convergence` written under `C:\hub\frappe-sandbox\validation-evidence\`.
- Effective-permission regression diff: `C:\hub\frappe-sandbox\validation-evidence\effective_permission_regression_diff_20260717T203115Z.json`

Post-fix regression diff:

| User | Result |
|---|---|
| `jason.minica@plusonerobotics.com` | PASS — zero losses |
| `wayne.kirk@plusonerobotics.com` | PASS — zero losses |
| `david.moreno@plusonerobotics.com` | PASS — zero losses |
| `motion.builder@plusonerobotics.com` | Expected raw-record isolation: 2 read losses (`BOM Export Package`, `Configured BOM Snapshot`) |
| `lam@plusonerobotics.com` | Expected raw-record isolation: 2 read losses (`BOM Export Package`, `Configured BOM Snapshot`) |
| `matt.speer@plusonerobotics.com` | BLOCKED — 819 losses total; 817 are mutation/admin losses, but 2 are read losses |

Matt Speer's remaining read losses:

- `DocType:read`
- `Custom DocPerm:read`

Finding: deterministic Custom DocPerm rows exist for `Global Viewer` on both `DocType` and `Custom DocPerm`, and `frappe.permissions.get_valid_perms()` sees them. However, Frappe's `frappe.get_meta()` / `frappe.has_permission()` path does not honor Custom DocPerm rows for these two core metadata DocTypes, so Matt still fails doctype-level read checks on exactly those two records. A narrow `has_permission` hook was evaluated and rejected because Frappe controller hooks can deny but cannot grant doctype-level access that the role permission resolver has already denied.

This means the owner target "Matt has zero read losses while holding no admin/mutation role" is not yet technically satisfied. The remaining choice is a policy/design decision:

1. Accept `DocType` and `Custom DocPerm` as explicit system-metadata exceptions to Global Viewer's read-everything promise; or
2. Keep a broader/admin role for Matt, which violates the no-admin/no-mutation target; or
3. Design a deeper Frappe core-permission override, which is outside the safe fixture/DocPerm model and should not be slipped into this deployment.

## Reversion steps

1. Primary rollback: take a fresh production backup immediately before deployment in Frappe Cloud. If deployment fails, restore that backup from the Frappe Cloud dashboard to return the database to the pre-deploy state.
2. Custom DocPerm convergence rollback: the patch writes a pre-delete snapshot JSON. Deleted `Custom DocPerm` rows can be reinserted from that snapshot if a targeted rollback is preferred, but backup restore remains authoritative.
3. App-version rollback: redeploy the prior production git ref on Frappe Cloud and run `bench --site <production-site> migrate`. This re-syncs fixtures to the prior app state but does not drop additive DB artifacts.
4. Additive-but-not-auto-dropped caveats: new DocTypes, Custom Fields, Custom DocPerms, Reports, Workspaces, and Wiki records introduced by fixtures/patches are not automatically deleted by app-version rollback. A database restore is the authoritative rollback for schema/data convergence.

## Superseding readiness update — 2026-07-20

This update finalizes the permanent permission-model implementation from
`docs/security/permission-model-of-record.md` and supersedes the prior Finance Viewer / Global Viewer blocker.

### Implemented in this tranche

- `Finance Viewer` retired from fixtures and production intent.
- `Global Viewer` is the broad read/report/export/print role for finance, audit, and executive visibility.
- `matt.speer@plusonerobotics.com` is assigned `Global Viewer` only.
- `jason.minica@plusonerobotics.com`, `wayne.kirk@plusonerobotics.com`, and `david.moreno@plusonerobotics.com`
  are assigned `Engineering User` + `Operations Viewer`; none hold `Operations Manager`.
- `nathaniel.pantuso@plusonerobotics.com`, `patty.gomez@plusonerobotics.com`, and
  `michael.king@plusonerobotics.com` are assigned `Inventory Operator`.
- `Fixture Export Control` is restricted to `System Manager` and `InductOne Process Architect` only.
- `InductOne External Builder` can create `InductOne Build Completion` records while remaining denied from raw
  `Item`, `BOM`, `BOM Export Package`, `Configured BOM Snapshot`, and Field Change records.
- `Procurement User` now has the minimal `Company` read grant required by Purchase Order creation.

### Additional patches added to the manifest

| Patch | Purpose | Reversibility note |
|---|---|---|
| `v2026_07_20_finance_viewer_retirement` | Deletes stale `Finance Viewer` Custom DocPerm rows, user/report role rows, Role Profile, and Role after snapshotting them; ensures report role rows converge to `Global Viewer`. | Deleted rows are snapshotted before deletion; primary rollback is fresh DB backup restore. |
| `v2026_07_20_custom_docperm_stale_deterministic_convergence` | Deletes deterministic `perm_*` Custom DocPerm rows that are no longer present in the authoritative fixture, after snapshotting them. This handles fixture removals that Frappe sync does not delete. | Deleted rows are snapshotted before deletion; primary rollback is fresh DB backup restore. |

### 2026-07-20 candidate validation evidence

| Validation | Result | Evidence |
|---|---:|---|
| Candidate user assignment sync | PASS | `C:\hub\frappe-sandbox\validation-evidence\candidate_production_role_assignment_sync_20260720T161703Z.json` |
| Compileall | PASS | Console output, 2026-07-20 |
| Fixture JSON parse | PASS | Console output, 17 fixture files parsed |
| Custom DocPerm convergence | PASS | `C:\hub\frappe-sandbox\validation-evidence\custom_docperm_finance_retirement_convergence_20260720T163501Z.json` |
| Role expectation tests | PASS, 111/111 | `C:\hub\frappe-sandbox\validation-evidence\role_expectation_tests_20260720T163550Z.json` |
| Production post-deploy validator subset | PASS, 15/15 | `C:\hub\frappe-sandbox\validation-evidence\production_post_deploy_validation_20260720T163515Z.json` |
| Static link dependency audit | PASS with accepted `Country` / `User` link-read exceptions only | `C:\hub\frappe-sandbox\validation-evidence\static_link_dependency_audit_20260720T163547Z.json` |
| Workspace visibility audit | PASS | `C:\hub\frappe-sandbox\validation-evidence\workspace_visibility_audit_20260720T163548Z.json` |
| Balloon report validation | PASS, 13/13 | `C:\hub\frappe-sandbox\validation-evidence\balloon_report_validation_20260720T163549Z.json` |
| Pre-deploy permission gate | PASS | Console output, 2026-07-20; same evidence files listed above |
| Effective-permission regression diff | FAIL / owner decision required | `C:\hub\frappe-sandbox\validation-evidence\effective_permission_regression_diff_20260720T163735Z.json` |

### Current convergence numbers

| Metric | Result |
|---|---:|
| DB Custom DocPerm rows | 1696 |
| Fixture Custom DocPerm rows | 1696 |
| Duplicate permission-key groups | 0 |
| DB rows not in fixture by name | 0 |
| Fixture rows missing in DB by name | 0 |
| DB keys without fixture equivalent | 0 |
| Fixture keys missing in DB | 0 |
| `Finance Viewer` Role exists | No |
| Users holding `Finance Viewer` | 0 |
| `Finance Viewer` Custom DocPerm rows | 0 |
| `Finance Viewer` Report-role rows | 0 |
| `Global Viewer` Custom DocPerm rows | 473 |

### Regression-diff blocker

The aggregate permission gate is green, but the final effective-permission regression diff is not green.

Evidence: `C:\hub\frappe-sandbox\validation-evidence\effective_permission_regression_diff_20260720T163735Z.json`

Diff summary:

- Missing candidate users: `0`
- Expected disabled users missing from candidate: `0`
- Users with unexpected losses: `2`
- Unexpected lost capabilities: `1055`
- Expected losses already allowlisted: `823`

Unexpected losses:

| User | Lost capabilities | Interpretation |
|---|---:|---|
| `david.moreno@plusonerobotics.com` | 14 | Candidate follows the locked model (`Engineering User` + `Operations Viewer`) but baseline shows prior InductOne Manager-like create/write capabilities for Build/Configuration/As-Built records. This conflicts with the task expectation that David should have zero losses. |
| `michael.king@plusonerobotics.com` | 1041 | Candidate follows the locked model where `ian.deliz` is the only deliberate `System Manager`; Michael is `InductOne Process Architect` + operational roles. Baseline still has broad System Manager/admin capabilities, creating large expected-cleanup losses that are not yet allowlisted because the task expectation listed only Matt + builders as intended residual losses. |

Owner decision required before deploy:

1. Confirm the locked model is authoritative and these two users' losses are intended cleanup, then update
   `scripts/run_effective_permission_regression_diff.py` allowlists / readiness text accordingly; or
2. Revise the locked permission model and assignment plan to preserve David Moreno's InductOne Manager capability
   and/or Michael King's System Manager capability, then rerun candidate role sync, migrate, convergence, role
   expectations, pre-deploy gate, and regression diff.

I did not silently reclassify these losses because this is exactly the kind of owner-policy boundary the deployment
gate is meant to expose.

PRODUCTION DEPLOY READINESS: GATE FAIL — regression diff requires owner decision for `david.moreno@plusonerobotics.com` and `michael.king@plusonerobotics.com`
