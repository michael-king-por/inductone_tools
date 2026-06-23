# Sandbox Restore and Validation Runbook

This runbook describes the defensible local testing model for InductOne changes.

The purpose of a sandbox is not merely to "see if it opens." The purpose is to prove that a proposed change can be applied to a production-shaped site without changing unintended behavior.

## Sandbox roles

Use two local sites when possible:

| Site | Purpose |
|---|---|
| Baseline | Restored production behavior. Do not migrate or modify casually. |
| Candidate | Restored from the same backup, then updated with proposed code/fixtures. |

The baseline is the control. The candidate is where changes are tested.

## Restore inputs

From Frappe Cloud backups:

- Database backup: `.sql.gz`
- Public files: `.tar`
- Private files: `.tar`

Keep the backup files immutable. Do not edit them or overwrite them during testing.

## Safety settings after restore

Immediately apply:

```bash
bench --site <site> set-config pause_scheduler 1
bench --site <site> set-config mute_emails 1
bench --site <site> set-config developer_mode 1
bench --site <site> clear-cache
```

Use a local-only hostname and port:

```bash
bench --site <site> set-config host_name http://<site>:<port>
```

Do not run integration/export/email actions until outbound-network behavior is understood and deliberately controlled.

## Baseline rule

Do not run `bench migrate` against the baseline unless the point of the test is specifically to validate current deployed code migration. A baseline restored from production should remain a reference for production database behavior.

## Candidate process

For each implementation batch:

1. Restore a fresh candidate from the same production backup.
2. Install or update the candidate app code.
3. Apply proposed local changes.
4. Run `bench migrate`.
5. Run validation scripts.
6. Compare critical database state before/after.
7. Smoke-test the affected UI path.
8. Record evidence.

## Minimum validation commands

From the candidate bench:

```bash
bench --site <candidate-site> list-apps
bench --site <candidate-site> migrate
bench --site <candidate-site> clear-cache
```

Then run the relevant integration validation scripts.

## Evidence to capture

For each tested change, capture:

- App commits.
- `bench migrate` result.
- Validation script output.
- Relevant DB row counts.
- Relevant fixture diff.
- Any UI smoke-test notes.

Example evidence categories:

```text
APP_COMMITS
frappe ...
erpnext ...
wiki ...
inductone_tools ...

MIGRATE
success

VALIDATION
all_passed: true

DB CHECKS
Build Completion count unchanged unless test intentionally creates/rolls back records.
Only expected Client Scripts present.
```

## Production-like validation areas

The restored production clone currently has no Build Completion or As-Built records. For those workflows, create synthetic candidate-only records and roll them back or delete them after testing.

Do not infer acceptance-path correctness from absence of production data.

## Local credentials

Use local-only credentials for restored sites. Never document production passwords in the repo.

## Handoff expectation

A future maintainer should be able to:

1. Restore a backup locally.
2. Apply proposed app changes.
3. Run documented validation.
4. Decide whether the change is safe to deploy.

If that cannot be done, the release process is not yet handoff-ready.
