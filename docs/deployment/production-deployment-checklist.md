# Production Deployment Checklist — InductOne Permission Hardening

This checklist is the production runbook for deploying the InductOne Tools permission hardening work. It assumes the system owner has reviewed and signed `docs/deployment/production-user-assignment-plan.md`.

Do not skip phases. If any go/no-go criterion fails, stop and follow Phase 6.

Before starting, set these variables in the production bench shell:

```bash
export PROD_BENCH="/home/frappe/frappe-bench"          # Example: /home/frappe/frappe-bench
export PROD_SITE="plusonerobotics.v.frappe.cloud"                 # Example: plusonerobotics.v.frappe.cloud
export INDUCTONE_BRANCH="main"        # Example: main
export EXPECTED_COMMIT="406d80a437ab934f9adfdb2a11e599c00cce3ca3"
export EVIDENCE_DIR="$PROD_BENCH/sites/$PROD_SITE/private/deployment-evidence"
export CANDIDATE_BENCH="/home/michaelplusone/frappe-sandbox/benches/candidate-bench"
export CANDIDATE_SITE="inductone-candidate.localhost"
export BASELINE_BENCH="/home/michaelplusone/frappe-sandbox/benches/baseline-bench"
export BASELINE_SITE="inductone-baseline.localhost"
```

`EVIDENCE_DIR` is the authoritative evidence path for the post-deployment validation script. Keep it on the production host during deployment, then copy the generated JSON evidence file into the durable validation evidence archive after verification if needed.

## Phase 0 — Pre-deployment gates

All items in this phase must be true before touching production.

1. [ ] Confirm `docs/deployment/production-user-assignment-plan.md` is signed by the system owner.

   Go/no-go:

   - GO if the approval block is signed and dated.
   - NO-GO if it is unsigned.

2. [ ] Confirm the local repo is on the intended commit.

   Run locally from the repo root:

   ```bash
   git status --short
   git rev-parse HEAD
   ```

   Record the commit SHA here: `___`

   Expected output:

   - `git status --short` shows only changes intentionally included in the deployment commit, or shows a clean working tree after commit.
   - `git rev-parse HEAD` matches the commit approved for deployment.

   Go/no-go:

   - GO if the commit SHA matches the approved deployment commit.
   - NO-GO if the SHA is unknown, unreviewed, or the working tree contains unintended changes.

3. [ ] Confirm all fixture JSON files parse without error.

   Run locally from the repo root:

   ```bash
   python -c "import json, pathlib; files=sorted(pathlib.Path('inductone_tools/fixtures').glob('*.json')); [json.load(open(f, encoding='utf-8')) for f in files]; print('PASS parsed', len(files), 'fixture JSON files')"
   ```

   Expected output:

   ```text
   PASS parsed <N> fixture JSON files
   ```

   Go/no-go:

   - GO if the command exits 0.
   - NO-GO if any JSON parse error occurs.

4. [ ] Confirm BOM Item Custom Field fixture parity against production.

   This is a read-only production check. It prevents fixture sync from
   unintentionally overwriting a live `BOM Item` Custom Field definition during
   `bench migrate`.

   Run on the production host from the production bench:

   ```bash
   cd "$PROD_BENCH"
   "$PROD_BENCH/env/bin/python" "$PROD_BENCH/apps/inductone_tools/scripts/run_custom_field_fixture_parity_check.py" \
     --site "$PROD_SITE" \
     --sites-path "$PROD_BENCH/sites" \
     --fixture-path "$PROD_BENCH/apps/inductone_tools/inductone_tools/fixtures/custom_field.json" \
     --evidence-dir "$EVIDENCE_DIR"
   ```

   Expected output:

   ```text
   Custom Field fixture parity: BOM Item
     WOULD_OVERWRITE: 0
   ```

   Go/no-go:

   - GO if the command exits 0 and reports zero `WOULD_OVERWRITE` fields.
   - NO-GO if any field is classified as `WOULD_OVERWRITE`. Stop before
     deployment and either update the fixture to match production's live
     definition or explicitly approve the fixture as an intentional definition
     change.
   - If any field is classified as `UNMANAGED_ON_SITE`, decide before deployment
     whether to add it to the fixture too or leave it manual and document why.

5. [ ] Confirm Python compiles without error.

   Run locally from the repo root:

   ```bash
   python -m compileall inductone_tools scripts
   ```

   Expected output:

   - Command exits 0.
   - No syntax errors are printed.

   Go/no-go:

   - GO if compileall exits 0.
   - NO-GO if any Python syntax error occurs.

6. [ ] Confirm a production backup has been taken within the last 24 hours and is verified restorable.

   Required evidence:

   - Backup timestamp.
   - Database backup file exists.
   - Private/public files backup exists if files are included.
   - Backup has been restored to a sandbox before deployment, or the restore process has been verified recently.

   Go/no-go:

   - GO if backup is recent and restorable.
   - NO-GO if backup freshness or restoreability is uncertain.

7. [ ] Confirm production bench access.

   Run on the production host:

   ```bash
   cd "$PROD_BENCH"
   bench --version
   bench --site "$PROD_SITE" list-apps
   ```

   Expected output:

   - `bench --version` prints a bench version.
   - `list-apps` includes `frappe`, `erpnext`, `wiki`, and `inductone_tools`.

   Go/no-go:

   - GO if bench access and site resolution work.
   - NO-GO if the user cannot access bench or the site.

8. [ ] Confirm sandbox restore freshness and preparation.

   This is a standing validation step for every future permission/deployment
   cycle. The local environment currently has **no configured automated Frappe
   Cloud / Press backup-pull path**. Unless a Press API/CLI credential is
   deliberately added later, the system owner must download the latest production
   backup set from the Frappe Cloud dashboard and place it in:

   ```text
   C:\hub\frappe-sandbox\production-refresh
   ```

   Required preparation:

   - Baseline: restore the latest production backup, check the app out to the
     current deployed production commit, and leave it pristine. Do not sync
     staged repo changes or run candidate migrations against baseline.
   - Candidate: restore the same latest production backup, sync the staged local
     repo changes, run `bench migrate`, and sync candidate user roles to the
     verified production assignment map.

   Run freshness checks for both sites:

   ```bash
   "$CANDIDATE_BENCH/env/bin/python" \
     "$CANDIDATE_BENCH/apps/inductone_tools/scripts/run_backup_freshness_check.py" \
     --bench "$CANDIDATE_BENCH" \
     --site "$CANDIDATE_SITE" \
     --sites-path "$CANDIDATE_BENCH/sites" \
     --max-age-hours 48 \
     --expected-prod-backup-iso "<latest-production-backup-ISO>"

   "$CANDIDATE_BENCH/env/bin/python" \
     "$CANDIDATE_BENCH/apps/inductone_tools/scripts/run_backup_freshness_check.py" \
     --bench "$BASELINE_BENCH" \
     --site "$BASELINE_SITE" \
     --sites-path "$BASELINE_BENCH/sites" \
     --max-age-hours 48 \
     --expected-prod-backup-iso "<latest-production-backup-ISO>"
   ```

   Go/no-go:

   - GO if both sites are fresh, baseline is on the deployed production commit,
     baseline does not contain the new staged patch(es), and candidate has the
     staged patch(es) applied after migrate.
   - NO-GO if either site is stale, baseline has candidate-only patches applied,
     or candidate has not been migrated with the staged changes.

9. [ ] Pass the pre-deploy permission gate on the candidate site.

   This gate exists so the regression classes already fixed (lost report/link
   dependencies, orphaned internal workspaces, weakened high-risk denials, and
   stale Query Report role tables) cannot ship again. Run it on the candidate
   site (which must be synced to the current repo and to production role
   assignments first):

   ```bash
   "$CANDIDATE_BENCH/env/bin/python" \
     "$CANDIDATE_BENCH/apps/inductone_tools/scripts/run_pre_deploy_permission_gate.py" \
     --site "$CANDIDATE_SITE" \
     --sites-path "$CANDIDATE_BENCH/sites" \
     --evidence-dir "$EVIDENCE_DIR"
   ```

   The gate runs the post-deploy validator, the static link-dependency audit, the
   workspace-visibility audit, and the Electrical Balloon Callouts report
   validation. It applies the owner-accepted exceptions (`Country`/`User` link
   reads; `Builder Portal` external page). It exits 0 only when no non-accepted
   issue remains.

   Then run the effective-permission regression diff against a candidate synced to
   production roles (the final "nobody lost needed access" check):

   ```bash
   "$CANDIDATE_BENCH/env/bin/python" \
     "$CANDIDATE_BENCH/apps/inductone_tools/scripts/sync_candidate_production_role_assignments.py" \
     --site "$CANDIDATE_SITE" \
     --sites-path "$CANDIDATE_BENCH/sites" \
     --confirm-candidate

   "$CANDIDATE_BENCH/env/bin/python" \
     "$CANDIDATE_BENCH/apps/inductone_tools/scripts/run_effective_permission_regression_diff.py" \
     --baseline-site "$BASELINE_SITE" --baseline-sites-path "$BASELINE_BENCH/sites" \
     --candidate-site "$CANDIDATE_SITE" --candidate-sites-path "$CANDIDATE_BENCH/sites" \
     --evidence-dir "$EVIDENCE_DIR"
   ```

   Go/no-go:

   - GO if `run_pre_deploy_permission_gate.py` prints `GATE: PASS` and the regression
     diff shows no unexpected losses beyond owner-accepted Bucket A downgrades.
   - NO-GO if the gate fails or the diff surfaces a new unclassified loss. Resolve in
     candidate before deploying.

## Phase 1 — Take a fresh production backup

1. [ ] Take a fresh backup immediately before migration.

   Run on the production host:

   ```bash
   cd "$PROD_BENCH"
   bench --site "$PROD_SITE" backup --with-files
   ```

   Expected output:

   - Backup completes without error.
   - Frappe prints backup paths, typically under:

     ```text
     sites/$PROD_SITE/private/backups/
     ```

2. [ ] Verify the backup files exist.

   Run:

   ```bash
   ls -lh "$PROD_BENCH/sites/$PROD_SITE/private/backups" | tail -n 10
   ```

   Expected output:

   - A fresh database backup file with the current timestamp.
   - Fresh file backups if `--with-files` produced them.

   Go/no-go:

   - GO if fresh backup files are present.
   - NO-GO if backup command fails or files are missing.

## Phase 2 — Deploy the commit

1. [ ] Push the reviewed commit from the local repo.

   Run locally from the repo root:

   ```bash
   git status --short
   git rev-parse HEAD
   git push origin "$INDUCTONE_BRANCH"
   ```

   Expected output:

   - `git rev-parse HEAD` equals the approved commit SHA recorded in Phase 0.
   - Push succeeds.

   Go/no-go:

   - GO if the approved commit is available on the production remote.
   - NO-GO if the pushed commit differs from the reviewed SHA.

2. [ ] Pull the approved commit into the production bench app directory.

   Run on the production host:

   ```bash
   cd "$PROD_BENCH/apps/inductone_tools"
   git fetch origin
   git checkout "$INDUCTONE_BRANCH"
   git pull --ff-only origin "$INDUCTONE_BRANCH"
   git rev-parse HEAD
   ```

   Expected output:

   - `git pull --ff-only` succeeds.
   - `git rev-parse HEAD` equals `$EXPECTED_COMMIT`.

   Go/no-go:

   - GO if production app directory is exactly on `$EXPECTED_COMMIT`.
   - NO-GO if the pull is non-fast-forward, fails, or lands on a different SHA.

## Phase 3 — Run `bench migrate`

1. [ ] Run migration.

   Run on the production host:

   ```bash
   cd "$PROD_BENCH"
   bench --site "$PROD_SITE" migrate
   ```

   Expected output:

   - Migration completes without traceback.
   - `Executing inductone_tools.patches.v2026_06_23_external_builder_permissions` appears during patch execution if the patch has not previously run.
   - `Executing inductone_tools.patches.v2026_06_29_finance_stock_report_access` appears during patch execution if the finance/report hotfix patch has not previously run.
   - `Executing inductone_tools.patches.v2026_06_29_transaction_role_stock_dependencies` appears during patch execution if the transaction-role dependency hotfix patch has not previously run.
   - `Executing inductone_tools.patches.v2026_06_29_operations_workspace_visibility` appears during patch execution if the Operations workspace visibility patch has not previously run.
   - `Executing inductone_tools.patches.v2026_06_29_link_dependency_read_grants` appears during patch execution if the managed link-read dependency patch has not previously run.
   - `Executing inductone_tools.patches.v2026_06_29_snapshot_stock_entry_type_permissions` appears during patch execution if the Stock Entry Type snapshot-management patch has not previously run.
   - `Executing inductone_tools.patches.v2026_07_06_balloon_report_access` appears during patch execution if the Electrical Balloon Callouts report access patch has not previously run.
   - `Executing inductone_tools.patches.v2026_07_08_configuration_option_status_model_cleanup` appears during patch execution if the configuration option status cleanup patch has not previously run.
   - `Executing inductone_tools.patches.v2026_07_10_builder_portal_workspace_cleanup` appears during patch execution if the builder-portal cleanup patch has not previously run.
   - Fixtures import cleanly, including the BOM Item `User Notes` Custom Field and the app-owned `user_notes` DocFields on `Configured BOM Snapshot Hierarchy` and `BOM Export Package Item`.
   - Fixtures import the app-owned `Electrical Balloon Callouts` Report record.
   - Fixtures import the filtered Workspace records for `Operations`, `Engineering`, and `Builder Portal`.
   - If the patch already appears in Patch Log, migrate should still complete cleanly.

2. [ ] Confirm the patch is in Patch Log.

   Run:

   ```bash
   cd "$PROD_BENCH"
   bench --site "$PROD_SITE" mariadb -e "select patch from \`tabPatch Log\` where patch like '%v2026_06_23_external_builder_permissions%';"
   bench --site "$PROD_SITE" mariadb -e "select patch from \`tabPatch Log\` where patch like '%v2026_06_29_finance_stock_report_access%';"
   bench --site "$PROD_SITE" mariadb -e "select patch from \`tabPatch Log\` where patch like '%v2026_06_29_transaction_role_stock_dependencies%';"
   bench --site "$PROD_SITE" mariadb -e "select patch from \`tabPatch Log\` where patch like '%v2026_06_29_operations_workspace_visibility%';"
   bench --site "$PROD_SITE" mariadb -e "select patch from \`tabPatch Log\` where patch like '%v2026_06_29_link_dependency_read_grants%';"
   bench --site "$PROD_SITE" mariadb -e "select patch from \`tabPatch Log\` where patch like '%v2026_06_29_snapshot_stock_entry_type_permissions%';"
   bench --site "$PROD_SITE" mariadb -e "select patch from \`tabPatch Log\` where patch like '%v2026_07_06_balloon_report_access%';"
   bench --site "$PROD_SITE" mariadb -e "select patch from \`tabPatch Log\` where patch like '%v2026_07_08_configuration_option_status_model_cleanup%';"
   bench --site "$PROD_SITE" mariadb -e "select patch from \`tabPatch Log\` where patch like '%v2026_07_10_builder_portal_workspace_cleanup%';"
   ```

   Expected output:

   ```text
   inductone_tools.patches.v2026_06_23_external_builder_permissions
   inductone_tools.patches.v2026_06_29_finance_stock_report_access
   inductone_tools.patches.v2026_06_29_transaction_role_stock_dependencies
   inductone_tools.patches.v2026_06_29_operations_workspace_visibility
   inductone_tools.patches.v2026_06_29_link_dependency_read_grants
   inductone_tools.patches.v2026_06_29_snapshot_stock_entry_type_permissions
   inductone_tools.patches.v2026_07_06_balloon_report_access
   inductone_tools.patches.v2026_07_08_configuration_option_status_model_cleanup
   inductone_tools.patches.v2026_07_10_builder_portal_workspace_cleanup
   ```

   Go/no-go:

   - GO if `bench migrate` exits 0 and the patch is present in Patch Log.
   - NO-GO if migrate fails, the patch errors, or Patch Log does not contain the patch after migrate. Execute Phase 6 rollback.

## Phase 4 — Role Profile and Super-user cleanup

The migration patch does not handle these production user assignment decisions. Apply them explicitly after migrate completes.

1. [ ] Apply the signed user assignment plan with the bench-execute helper.

   Run on the production host:

   ```bash
   cd "$PROD_BENCH"
   bench --site "$PROD_SITE" execute inductone_tools.production_user_assignment.apply_approved_user_assignments --kwargs '{"confirm":"APPLY_PRODUCTION_USER_ASSIGNMENT_PLAN"}'
   ```

   The helper performs these actions in order:

   1. Disables `alyza.salinas@plusonerobotics.com` by setting `enabled = 0`. It does not delete the user, preserving audit trail.
   2. Disables `quickbooks.integration@plusonerobotics.com`. If a QuickBooks integration owner later re-justifies the account, re-enable it only with explicitly scoped roles.
   3. Clears `role_profile_name`, then replaces roles for:
      - `ian.deliz@plusonerobotics.com` → `System Manager`
      - `matt.speer@plusonerobotics.com` → `Finance Viewer`
      - `matthew.mcmillan@plusonerobotics.com` → `Procurement User`
      - `nathaniel.pantuso@plusonerobotics.com` → `Operations Manager`, `Gripper Manufacturer`
      - `patty.gomez@plusonerobotics.com` → `Operations Manager`

   Expected output:

   ```text
   DISABLED alyza.salinas@plusonerobotics.com
   DISABLED quickbooks.integration@plusonerobotics.com
   ASSIGNED ian.deliz@plusonerobotics.com: role_profile_name cleared; roles=System Manager
   ASSIGNED matt.speer@plusonerobotics.com: role_profile_name cleared; roles=Finance Viewer
   ASSIGNED matthew.mcmillan@plusonerobotics.com: role_profile_name cleared; roles=Procurement User
   ASSIGNED nathaniel.pantuso@plusonerobotics.com: role_profile_name cleared; roles=Operations Manager, Gripper Manufacturer
   ASSIGNED patty.gomez@plusonerobotics.com: role_profile_name cleared; roles=Operations Manager
   SUMMARY applied_actions=7
   ```

   Go/no-go:

   - GO if all seven expected actions print and the command exits 0.
   - NO-GO if any user or role is missing, or if the command exits non-zero. Stop and investigate in candidate before retrying.

## Phase 5 — Post-deployment verification

Use the automated script as the primary verification method. Manual browser checks are secondary confirmation and should not override a failed automated check.

1. [ ] Prepare log directories for standalone Frappe initialization.

   Run on the production host:

   ```bash
   mkdir -p "$PROD_BENCH/sites/$PROD_SITE/logs"
   mkdir -p /home/frappe/logs
   ```

   Note: this prevents `FileNotFoundError` from `frappe.init()` when the validation script runs outside a normal worker/web context.

   Expected output:

   - No output, command exits 0.

   Go/no-go:

   - GO if both directories exist or are created successfully.
   - NO-GO if either command fails.

2. [ ] Run primary automated validation.

   Run on the production host:

   ```bash
   cd "$PROD_BENCH"
   "$PROD_BENCH/env/bin/python" "$PROD_BENCH/apps/inductone_tools/scripts/run_production_post_deploy_validation.py" \
     --site "$PROD_SITE" \
     --sites-path "$PROD_BENCH/sites" \
     --evidence-dir "$EVIDENCE_DIR" \
     --finance-report-user "matt.speer@plusonerobotics.com"
   ```

   Expected output:

   ```text
   PASS legacy_role_absence: No enabled users hold retired legacy roles.
   PASS super_profile_absence: No enabled users hold Super Role Profile.
   PASS external_builder_item_denial_motion: motion.builder@plusonerobotics.com cannot read/list Item.
   PASS external_builder_bom_denial_motion: motion.builder@plusonerobotics.com cannot read/list BOM.
   PASS external_builder_item_denial_lam: lam@plusonerobotics.com cannot read/list Item.
   PASS external_builder_bom_denial_lam: lam@plusonerobotics.com cannot read/list BOM.
   PASS fixture_export_control_viewer_finance_denial: Operations Viewer and Finance Viewer have no read grant on Fixture Export Control.
   PASS finance_viewer_report_dependency_read_access: Finance Viewer can read all finance report dependency DocTypes as matt.speer@plusonerobotics.com.
   PASS finance_viewer_business_report_access: Finance Viewer can access all curated business/audit reports as matt.speer@plusonerobotics.com.
   PASS finance_viewer_critical_stock_report_execution: Finance Viewer can execute Stock Balance and Stock Ledger as matt.speer@plusonerobotics.com.
   PASS transaction_role_stock_dependency_permissions: Transaction roles have required stock dependency DocPerm bits.
   SUMMARY 11/11 passed; evidence=<path>/production_post_deploy_validation_<timestamp>.json
   ```

   Go/no-go:

   - GO if all checks print `PASS` and the script exits 0.
   - NO-GO if any check prints `FAIL` or the script exits non-zero. Execute Phase 6 rollback.

3. [ ] Record the generated JSON evidence file path.

   Evidence file:

   ```text
   ________________________________________________
   ```

4. [ ] Secondary manual spot checks.

   These checks are browser confirmation only. The automated script above is the authority for the role/permission assertions it covers.

   - [ ] External builder spot check:
     - Log in as `motion.builder@plusonerobotics.com`.
     - Confirm the user can reach Builder Portal.
     - Confirm the user cannot reach Items list.
     - Confirm the user cannot reach Sales Orders.
   - [ ] InductOne Manager spot check:
     - Log in as an InductOne Manager user.
     - Confirm the user can open an InductOne Build.
     - Confirm the user cannot open Fixture Export Control.
   - [ ] Engineering User spot check:
     - Log in as `shaun.edwards@plusonerobotics.com`.
     - Confirm the user can open Engineering Signoff.
     - Confirm the user cannot see InductOne Manager workflow actions.
   - [ ] Fixture Export Control check:
     - Confirm a Finance Viewer user cannot access Fixture Export Control.
     - Confirm an Operations Viewer user cannot access Fixture Export Control.

5. [ ] Balloon-scoped hierarchy regression re-validation.

   After the corrective follow-up is deployed, regenerate baseline-only and IPC snapshots for test build `SAL-ORD-2026-00054-BLD-0225`, then run the same balloon-scoped stage ladder read-only against those production snapshots.

   Required sentinel:

   - Baseline-only snapshot contains `172 → 11245 qty 3` and `173 → 11283 qty 2` in flat, hierarchy, and hierarchy workbook.
   - IPC snapshot contains `172 → 11283 qty 3` and `173 → 11351 qty 2` in flat, hierarchy, and hierarchy workbook.
   - Flat, hierarchy, and workbook collision rollups are identical.

   Go/no-go:

   - GO if the sentinel rows are present and the stage ladder passes.
   - NO-GO if baseline `173 → 11283 qty 2` is missing from hierarchy or workbook. Keep `DEV-*` options at `Draft`, do not approve Engineering Signoff/release them, and investigate in candidate before promoting them to `Released`.

   Go/no-go:

   - GO if automated validation passes and manual spot checks match expected behavior.
   - NO-GO if a manual check exposes a real access failure not covered by the script. Execute Phase 6 rollback if the failure matches rollback criteria; otherwise stop and investigate in candidate.

## Phase 6 — Rollback plan

If any Phase 3–5 check fails:

1. [ ] Do not make further changes.
2. [ ] Restore the production database from the Phase 1 backup.
3. [ ] Do not revert the app commit unless migrate itself caused data corruption. Restoring the database returns the site data to pre-migration state.
4. [ ] Investigate the failure in candidate before re-attempting production deployment.

Rollback trigger criteria:

- `bench migrate` exits non-zero.
- The external builder accounts can reach raw Item or BOM records.
- Any InductOne Manager user is locked out of the InductOne Build workflow.
- `System Manager` access is broken.

Restore command pattern:

```bash
cd "$PROD_BENCH"
bench --site "$PROD_SITE" restore "<path-to-phase-1-database-backup>"
bench --site "$PROD_SITE" clear-cache
```

Expected output:

- Restore completes without traceback.
- Site loads after `clear-cache`.

Go/no-go:

- GO to investigate in candidate once production is restored and stable.
- NO-GO to any second production attempt until the failure has been reproduced and fixed in candidate.

## Phase 7 — Sign-off

After all Phase 5 checks pass, record:

| Field | Value |
|---|---|
| Deployment timestamp | 2026-06-25 20:38 UTC |
| Commit SHA deployed | 406d80a437ab934f9adfdb2a11e599c00cce3ca3 |
| Person who performed deployment | Michael King |
| Phase 1 backup path | /home/frappe/frappe-bench/sites/plusonerobotics.v.frappe.cloud/private/backups/ (taken 2026-06-25 prior to migrate) |
| Phase 5 automated evidence JSON | /home/frappe/frappe-bench/sites/plusonerobotics.v.frappe.cloud/private/deployment-evidence/production_post_deploy_validation_20260625T203809Z.json |
| Deviations from this checklist and why | Migration triggered via Frappe Cloud dashboard deploy (not manual git pull + bench migrate); Phase 2/3 console steps were not applicable. Role cleanup applied via bench console direct-DB commands due to IPython list comprehension scoping bug with `user.set()`. |

Final sign-off:

```text
Deployment completed by: Michael King
Date/time: 2026-06-25 20:38 UTC
System owner approval: Michael King (system owner)
```
