# InductOne Hardening Progress Tracker

This is the durable progress log for the InductOne permission/workflow hardening effort. It exists so progress is tracked in the repo instead of only in chat context.

## Operating rule

- Production is not mutated unless explicitly authorized.
- Baseline sandbox is reference-only.
- Candidate sandbox is disposable and is the only environment used for destructive restore/migrate/user/password testing.
- Local repo changes are not pushed by Codex.
- Every phase needs implementation evidence and validation evidence.

## Environment snapshot

| Purpose | Value |
|---|---|
| Local repo | `C:\Users\MichaelKing\OneDrive - Plus One Robotics\Documents\GitHub\inductone_tools` |
| Candidate site | `inductone-candidate.localhost` |
| Candidate URL | `http://inductone-candidate.localhost:8000` |
| Candidate bench | `/home/michaelplusone/frappe-sandbox/benches/candidate-bench` |
| Baseline site | `inductone-baseline.localhost` |
| Baseline URL | `http://inductone-baseline.localhost:8010` |
| Baseline bench | `/home/michaelplusone/frappe-sandbox/benches/baseline-bench` |
| Production refresh backup folder | `C:\hub\frappe-sandbox\production-refresh` |
| Validation evidence folder | `C:\hub\frappe-sandbox\validation-evidence` |

## Completed phases

| Phase | Status | Evidence |
|---|---|---|
| Restore production backup to candidate | Complete | Candidate restored from 2026-06-25 production backup; candidate config preserved; production `site_config` not restored |
| Sync local repo to candidate | Complete | Candidate app synced from local repo before migrate |
| Candidate migrate after InductOne role patch | Complete | `bench migrate` succeeded; `v2026_06_23_external_builder_permissions` ran |
| Target role fixtures | Complete | `inductone_tools/fixtures/role.json`; `inductone_tools/fixtures/role_profile.json` |
| InductOne custom permission remap | Complete | `inductone_tools/fixtures/custom_docperm.json`; InductOne roles remapped from legacy roles |
| Server-side gate remap | Complete | `engineering_signoff.py`, `part_numbering.py`, `builder_release.py` updated to target role vocabulary |
| Operational ERPNext DocPerm mapping | Complete | `scripts/update_operational_role_docperms.py`; `custom_docperm.json` has 242 unique rows after finance/report and transaction-role dependency hotfixes |
| Candidate synthetic persona users | Complete | `scripts/create_candidate_persona_users.py`; `candidate_persona_user_creation.txt` |
| Candidate strict role assignment | Complete | `scripts/assign_candidate_target_roles.py`; `candidate_role_assignment_apply_expanded_system_manager_cleanup.txt` |
| Automated operational role audit | Complete | `candidate_permission_audit_operational_roles_final.jsonl` |
| Browser-driven GUI smoke test | Complete | `gui-smoke-2026-06-25T16-32-30-281Z`; 70/70 checks passed |
| Direct API/method negative tests | Complete | `C:\hub\frappe-sandbox\validation-evidence\method_negative_tests_20260625T184047Z.json`; 10/10 checks passed |
| Workflow transition smoke test | Complete | `C:\hub\frappe-sandbox\validation-evidence\workflow_transition_smoke_20260625T184346Z.json`; 6/6 checks passed |
| `Fixture Export Control` access fix | Complete | `C:\hub\frappe-sandbox\validation-evidence\fixture_export_control_access_fix.txt`; Operations Viewer/Finance Viewer denied; `Builder` role absent |
| Wiki role-reference fixture staged | Complete | `C:\hub\frappe-sandbox\validation-evidence\wiki_legacy_term_scan.json`; `C:\hub\frappe-sandbox\validation-evidence\wiki_role_reference_updates.txt`; `C:\hub\frappe-sandbox\validation-evidence\wiki_fixture_validation_final.txt`; `inductone_tools/fixtures/wiki_page.json` |
| Production user assignment plan | Complete | `docs/deployment/production-user-assignment-plan.md`; Super Role Profile decisions incorporated; signed by system owner |
| Production deployment checklist | Complete | `docs/deployment/production-deployment-checklist.md`; primary post-deploy verifier at `scripts/run_production_post_deploy_validation.py` |
| Production deployment | Complete | Deployed and signed off 2026-06-25; production automated validation passed 5/5; evidence `production_post_deploy_validation_20260625T203809Z.json` |
| Post-deployment governance cleanup | Complete | Operations Member Profile users remapped to Operations Viewer; engineering approvers cleaned; `michael.king` trimmed (`Manufacturing User` removed); `david.brain`, `jim.haws`, and `ryan.hannon` stray Project Manager/Operations Member roles removed; full legacy-role sweep returns zero holders across enabled users |
| Repo-housekeeping gap closure | Complete | `C:\hub\frappe-sandbox\validation-evidence\repo_housekeeping_gap_closure_20260626.txt`; patch legacy role list includes `Engineering - Signoff`; validator covers Motion and LAM builders; validator default evidence path is host-neutral |
| Finance business report access hotfix | Complete in candidate | Root cause and fix documented in `docs/security/finance-stock-report-access-hotfix-2026-06-29.md`; migration patch `v2026_06_29_finance_stock_report_access` applied in candidate; evidence `C:\hub\frappe-sandbox\validation-evidence\finance_business_report_access_hotfix_20260629.json` and `C:\hub\frappe-sandbox\validation-evidence\finance_stock_report_execution_hotfix_20260629.json`; focused finance report validation passed 30/30; critical stock report execution passed 8/8 including `Serial and Batch Bundle`; production validator extended with dependency and execution checks |
| Transaction role stock dependency hotfix | Complete in candidate | Root cause and fix documented in `docs/security/transaction-role-stock-dependency-hotfix-2026-06-29.md`; migration patch `v2026_06_29_transaction_role_stock_dependencies` applied in candidate; `custom_docperm.json` increased 224→242 rows with exact transaction-role dependency grants; evidence `C:\hub\frappe-sandbox\validation-evidence\transaction_role_stock_dependency_smoke_20260629T152322Z.json`; execution smoke passed 5/5; full candidate validator passed 10/11 with only known stale candidate `Super` Role Profile failure |
| Operations workspace visibility fix | Complete in candidate | Discovery documented in `docs/security/downstream-loss-sweep-2026-06-29.md`; `Operations` is a Workspace previously restricted to legacy `Operations Member`; patch `v2026_06_29_operations_workspace_visibility` applied in candidate; `inductone_tools/fixtures/workspace.json` exported; evidence `C:\hub\frappe-sandbox\validation-evidence\operations_workspace_visibility_20260629T161917Z.json`; 8/8 visibility checks passed |
| Proactive downstream-loss sweeps | Complete for owner review | Scripts added: `run_workspace_visibility_audit.py`, `run_static_link_dependency_audit.py`, `run_effective_permission_regression_diff.py`; evidence `workspace_visibility_audit_20260629T161943Z.json`, `static_link_dependency_audit_20260629T162008Z.json`, `effective_permission_regression_diff_20260629T162316Z.json`; no auto-grants applied |
| Downstream-loss triage + managed link-read grants | Complete (repo-local) | Triage and gameplan in `docs/security/downstream-loss-triage-2026-06-29.md`. Regression-diff's 10,135 losses triaged into Bucket A (intended downgrades), Bucket B (~792 contaminated — diff candidate not synced to production), Bucket C (28 static link-read gaps). Implemented additive read grants on managed DocTypes (Item, BOM, Sales Order, Supplier for InductOne Manager/Process Architect; Currency for Procurement; Price List for Inventory Operator) via generator + idempotent patch `v2026_06_29_link_dependency_read_grants` with a guard that refuses unmanaged DocTypes (Custom DocPerm replace-trap). `custom_docperm.json` 242→252 rows, 252 unique, 0 dupes. |
| Unmanaged link-target Desk validation + Stock Entry Type snapshot | Complete in candidate | Desk link probe confirmed `Stock Entry Type` blocked Operations Manager and Gripper Manufacturer; static audit showed the same future blocker for Inventory Operator. `Country` and `User` were not Desk-blocking and remain unmanaged. Added generator block + idempotent patch `v2026_06_29_snapshot_stock_entry_type_permissions` to snapshot the full standard `Stock Entry Type` DocPerm set before adding read-only curated rows for Operations Manager, Inventory Operator, Gripper Manufacturer, and (per owner decision) the viewer tier Operations Viewer + Finance Viewer. `custom_docperm.json` 252→261 rows. Evidence: `unmanaged_link_desk_probe_before_stock_entry_type_fix_20260629T193631Z.json`, `unmanaged_link_desk_probe_after_stock_entry_type_inventory_operator_fix_20260629T194243Z.json`, `stock_entry_type_standard_role_read_before_20260629T193654Z.json`, `stock_entry_type_standard_role_read_after_20260629T193823Z.json`, `static_link_dependency_audit_20260629T194323Z.json`. |
| Candidate production-assignment sync + regression diff rerun | Complete for owner review | Candidate users were aligned to verified production role assignments; disabled `alyza.salinas` and `quickbooks.integration`; left `hana.macinnis` unchanged as undecided. Evidence: `candidate_production_role_assignment_sync_20260629T194005Z.json`. Rerun diff evidence: `effective_permission_regression_diff_20260629T194445Z.json`; missing candidate users = 0, expected disabled users = 2, expected external-builder Item/BOM losses = 14, remaining losses = 11,927 across 26 users for owner review / Bucket A classification. |
| Quality workspace owner decision | Complete | Owner confirmed ERPNext Quality module is unused; workspace hidden rather than role-expanded. |
| Durable governance documentation | Complete | `role-governance-audit.md`, `role-effect-map.md`, `role-migration-validation-gameplan.md` |

## Key automated validation results

| Check | Status | Evidence |
|---|---|---|
| Custom DocPerm fixture parses | Pass | Local parse validation; 261 rows |
| Custom DocPerm unique keys | Pass | 261 unique `(parent, role, permlevel)` keys |
| Custom DocPerm replace-trap avoided | Pass | `Country` and `User` confirmed absent from fixture; `Stock Entry Type` snapshot-managed with its full standard DocPerm set before curated read rows are added |
| Christina no longer depends on `Super`/`System Manager` in strict model | Pass | Final audit roles exclude `System Manager` |
| Christina retains intended InductOne Manager / Engineering / Operations access | Pass | Final audit |
| Christina cannot write InductOne process architecture records | Pass | `InductOne Configuration Option` write false |
| Jim has InductOne Manager + Operations Manager access | Pass | Final audit |
| Operations Viewer is read-only | Pass | Final audit |
| Inventory Operator can submit stock movement docs | Pass | Final audit |
| Gripper Manufacturer can submit Work Orders | Pass | Final audit |
| Finance Viewer is broad read-only | Pass | Final audit |
| Procurement User can create/write Item Price but cannot create Item | Pass | Final audit |
| Motion/LAM denied raw Item/BOM access | Pass | Final audit |
| Candidate GUI route/create-button smoke test | Pass | `docs/security/gui-smoke-validation-2026-06-25.md`; 70/70 checks passed |
| Direct whitelisted-method unauthorized calls fail before document lookup | Pass | `method_negative_tests_20260625T184047Z.json`; all checks raised `PermissionError` |
| Christina workflow transition methods reach domain validation without permission denial | Pass | `workflow_transition_smoke_20260625T184346Z.json`; release/accept methods raised domain `ValidationError`, not `PermissionError` |
| `Fixture Export Control` restricted to system/process-owner access | Pass | `fixture_export_control_access_fix.txt`; Operations Viewer/Finance Viewer denied; one `InductOne Process Architect` Custom DocPerm row; Administrator read allowed |
| Generic `Builder` role removed from users | Pass | `fixture_export_control_access_fix.txt`; `Users still holding Builder: none — PASS` |
| Wiki fixture has no legacy role terms | Pass | `wiki_fixture_validation_final.txt`; 3/3 exported pages pass, including em-dash `Engineering — Signoff` check |

| Production deployment artifacts parse/compile locally | Pass | `python -m compileall inductone_tools scripts`; fixture JSON parse check; `scripts/run_production_post_deploy_validation.py` py_compile |
| Production deployment automated validation | Pass | `production_post_deploy_validation_20260625T203809Z.json`; 5/5 checks passed at production sign-off on 2026-06-25 |
| Post-deployment legacy role sweep | Pass | Zero holders across all enabled production users after governance cleanup |
| Repo-housekeeping before/after grep validation | Pass | `repo_housekeeping_gap_closure_20260626.txt`; before gaps confirmed open, after greps confirm all three closed |
| Finance Viewer access to business/audit reports | Pass in candidate | `finance_business_report_access_hotfix_20260629.json`; 30/30 curated Report records include `Finance Viewer`; candidate Finance Viewer persona permitted |
| Finance Viewer execution of critical stock reports | Pass in candidate | `finance_stock_report_execution_hotfix_20260629.json`; Finance Viewer can read `Batch`, `Company`, `Currency`, `Fiscal Year`, `Serial and Batch Bundle`, `Territory`; `Stock Balance` executed with 110 rows and `Stock Ledger` executed with 719 rows |
| Transaction roles execute stock workflows with batch/serial dependencies | Pass in candidate | `transaction_role_stock_dependency_smoke_20260629T152322Z.json`; Inventory Operator material receipt, Operations Manager Sales Order + stock issue, Gripper Manufacturer Work Order + manufacture Stock Entry, and Procurement User Item Price/Purchase Order view all passed |
| Operations Workspace visibility | Pass in candidate | `operations_workspace_visibility_20260629T161917Z.json`; internal roles visible, external builder hidden |
| Workspace visibility audit | Review required | `workspace_visibility_audit_20260629T161943Z.json`; `Quality` still restricted to retired `Builder`, `Builder Portal` external-only |
| Static mandatory Link dependency audit | Triaged; Stock Entry Type fixed | `static_link_dependency_audit_20260629T194323Z.json`; `Stock Entry Type` no longer flagged after snapshot-management. Remaining findings are `Country` (Desk not blocked due standard `All` read) and `User` display/cosmetic links, both intentionally unmanaged. |
| Effective permission regression diff | Reviewed and CLOSED by owner | `effective_permission_regression_diff_20260629T194445Z.json`; candidate synced to production (0 missing, 2 expected disabled, 14 expected external-builder losses). Owner confirmed remaining losses are Bucket A intended: the org does not use ERPNext purchasing or manufacturing beyond grippers, so Operations Viewer's ~44 sales/manufacturing read losses are unused-doctype losses, not regressions. Operations Viewer narrow scope confirmed correct; no expansion. Only `hana.macinnis` remains undecided. |
| Operations Viewer scope decision | Complete (owner) | Confirmed narrow ~40-doctype core stock/sales scope is correct; sales/manufacturing/CRM/POS doctypes are unused and intentionally not read-granted. `Stock Entry Type` read extended to `Operations Viewer` + `Finance Viewer` so the type label resolves when viewing Stock Entries (safe append; standard roles unaffected). `custom_docperm.json` 259→261 rows. |
| Quality workspace prune | Complete in candidate | Owner confirmed ERPNext Quality module unused. Orphaned `Quality` Workspace (restricted to retired `Builder`) hidden via idempotent patch `v2026_06_29_hide_unused_quality_workspace` (`is_hidden=1`, reversible, no content deleted). Candidate migrate applied the patch on 2026-06-30; a second migrate left `is_hidden=1`, proving standard workspace sync does not unhide it. Evidence: `candidate_migrate_20260630_quality_gate.txt`, `candidate_migrate_20260630_quality_idempotency_second.txt`, `workspace_visibility_audit_20260630T192054Z.json`. |
| Backup freshness + sandbox preparation gate | Complete in candidate/baseline | No configured Press/Frappe Cloud automated backup pull path exists locally; owner downloaded the 2026-06-30 backup set to `C:\hub\frappe-sandbox\production-refresh`. Baseline and candidate were refreshed from `20260630_112423`; baseline app checked out to production reference `ba776aa` and left without the new hide-quality patch; candidate was synced to staged repo, migrated, and role-synced. Evidence: `backup_freshness_inductone-candidate_localhost_20260630T191829Z.json`, `backup_freshness_inductone-baseline_localhost_20260630T191831Z.json`, `sandbox_preparation_20260630T1922Z.json`. |
| Pre-deploy permission gate | Complete in candidate | `scripts/run_pre_deploy_permission_gate.py` orchestrates the post-deploy validator + static link-dependency audit + workspace-visibility audit into one `GATE: PASS/FAIL` with an owner-accepted exception allowlist (`Country`/`User` link reads; `Builder Portal` workspace). Candidate dry-run on 2026-06-30 exited 0 and printed `GATE: PASS`. Evidence: `pre_deploy_permission_gate_20260630_console.txt`, `production_post_deploy_validation_20260630T192115Z.json`, `static_link_dependency_audit_20260630T192200Z.json`, `workspace_visibility_audit_20260630T192201Z.json`. |
| `hana.macinnis` disposition | Owner action | Owner to delete the user account (no curated target role assigned). |

## Open gates before production

| Gate | Status | Blocking action |
|---|---|---|
| Manual/browser GUI smoke tests | Complete | Browser-driven candidate test passed 70/70; deeper workflow action tests still separate |
| Direct API/method negative tests | Complete | Candidate direct-method test passed 10/10; unauthorized users receive `PermissionError` before document lookup |
| Workflow transition tests | Complete | Candidate transition smoke passed 6/6; Christina can reach release/accept methods and is blocked only by domain prerequisites |
| `Fixture Export Control` access fix | Complete | Candidate denies Operations Viewer/Finance Viewer and retains System Manager/Process Architect path |
| Wiki/landing page update | Complete | Candidate wiki role references updated and exported as filtered `Wiki Page` fixture |
| Production user assignment plan | Complete | `docs/deployment/production-user-assignment-plan.md`; Super Role Profile decisions incorporated; signed by system owner |
| Production deployment plan | Complete | `docs/deployment/production-deployment-checklist.md`; includes backup, deploy, migrate, role cleanup, primary automated verification, rollback, and sign-off |
| Production deployment execution | Complete | Deployed and signed off 2026-06-25; 5/5 automated production validation passed |
| Repo-housekeeping commit | Complete | Local-only commit brings repository in line with deployed production reality and extends future validation to both external builders |
| Procurement field policy | Partially resolved | Current decision: use `Item Price` for pricing; do not give Item permlevel-1 write |
| Accounting mutation policy | Resolved for now | Operations Manager/Finance Viewer do not mutate accounting docs |

## Next recommended sequence

1. **Deploy the staged hotfix patches to production** (highest priority). Six patches are committed/staged locally but not yet on production: `v2026_06_29_finance_stock_report_access`, `v2026_06_29_transaction_role_stock_dependencies`, `v2026_06_29_operations_workspace_visibility`, `v2026_06_29_link_dependency_read_grants`, `v2026_06_29_snapshot_stock_entry_type_permissions`, and `v2026_06_29_hide_unused_quality_workspace`. Until deployed, `patty.gomez`, `nathaniel.pantuso`, and any future `Inventory Operator` carry the live Stock Entry Type Desk-link gap. Deploy via Frappe Cloud dashboard; migrate runs all idempotently.
   - **Before deploying, run the pre-deploy permission gate** (`scripts/run_pre_deploy_permission_gate.py`) on a candidate synced to repo + production roles; require `GATE: PASS` plus a clean regression diff. See deployment checklist Phase 0 item 7.
2. **Owner-review residual effective-permission losses** from `effective_permission_regression_diff_20260629T194445Z.json`; do not auto-grant from the list. Classify `hana.macinnis@plusonerobotics.com` separately because her target role assignment remains undecided.
3. Future candidate restores should self-clean legacy `Engineering - Signoff` holders and validate both Motion and LAM external builders.
4. If any later change touches permissions, wiki fixtures, or workflow gates, rerun:
   - fixture/static validation,
   - candidate migrate,
   - automated audit,
   - GUI smoke tests,
   - direct method negative tests,
   - workflow transition smoke tests.
