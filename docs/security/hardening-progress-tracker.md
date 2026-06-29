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
| Operational ERPNext DocPerm mapping | Complete | `scripts/update_operational_role_docperms.py`; `custom_docperm.json` has 212 unique rows after `Fixture Export Control` cleanup |
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
| Finance business report access hotfix | Complete in candidate | Root cause and fix documented in `docs/security/finance-stock-report-access-hotfix-2026-06-29.md`; migration patch `v2026_06_29_finance_stock_report_access` applied in candidate; evidence `C:\hub\frappe-sandbox\validation-evidence\finance_business_report_access_hotfix_20260629.json`; focused finance report validation passed 30/30; production validator extended with aggregate Finance Viewer report check |
| Durable governance documentation | Complete | `role-governance-audit.md`, `role-effect-map.md`, `role-migration-validation-gameplan.md` |

## Key automated validation results

| Check | Status | Evidence |
|---|---|---|
| Custom DocPerm fixture parses | Pass | Local parse validation; 212 rows |
| Custom DocPerm unique keys | Pass | 212 unique `(parent, role, permlevel)` keys |
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

1. Review and push the local repo-housekeeping commit when ready.
2. Future candidate restores should self-clean legacy `Engineering - Signoff` holders and validate both Motion and LAM external builders.
3. If any later change touches permissions, wiki fixtures, or workflow gates, rerun:
   - fixture/static validation,
   - candidate migrate,
   - automated audit,
   - GUI smoke tests,
   - direct method negative tests,
   - workflow transition smoke tests.
