# Release Checklist

This checklist is for deploying InductOne Tools changes to Frappe Cloud.

Do not treat a Git push as a release by itself. A release is complete only after migration and post-deploy smoke checks succeed.

## Pre-release classification

Classify the change:

| Change type | Examples | Required validation |
|---|---|---|
| Documentation only | Docs, comments | Markdown review; no migration needed. |
| Python behavior | hooks, whitelisted methods, validation | Candidate migrate plus targeted tests. |
| Fixture/schema | DocType, Client Script, Custom DocPerm | Candidate migrate plus fixture diff and UI smoke test. |
| Permission/security | roles, DocPerm, method role checks | Candidate role-based smoke tests. |
| Workflow lifecycle | status transitions, acceptance, release | Integration tests and rollback/failure tests. |

## Pre-release checklist

- [ ] Repo working tree contains only intentional changes.
- [ ] Documentation updated for behavior/process changes.
- [ ] Candidate sandbox restored from recent production backup.
- [ ] Candidate app code matches intended release commit.
- [ ] `bench migrate` succeeds in candidate.
- [ ] Validation scripts pass.
- [ ] `scripts/audit_fixtures.py` passes in repo-only mode.
- [ ] `scripts/audit_fixtures.py` passes against candidate DB if fixtures changed.
- [ ] Fixture diff reviewed.
- [ ] Permission impact reviewed.
- [ ] A rollback path is known.
- [ ] User-facing behavior changes, if any, are explicitly approved.

## Candidate validation checklist

- [ ] `bench --site <candidate> list-apps` recorded.
- [ ] `bench --site <candidate> migrate` recorded.
- [ ] Affected workflow smoke-tested.
- [ ] No unexpected Client Script rows added/removed.
- [ ] No operational records fixture-managed.
- [ ] Scheduler and email settings confirmed safe in local sandbox.

## Frappe Cloud deployment checklist

- [ ] Push branch/commit to GitHub.
- [ ] Confirm Frappe Cloud sees intended commit.
- [ ] Run/update app on Frappe Cloud.
- [ ] Confirm migration completes.
- [ ] Do not manually repair production via GUI unless an emergency occurs.

## Post-deploy smoke test

Run only safe, non-destructive checks unless a change explicitly requires deeper testing:

- [ ] Login works.
- [ ] InductOne workspace/landing path loads.
- [ ] InductOne Build form loads.
- [ ] Configuration Option form loads.
- [ ] Configuration Order form loads.
- [ ] Build Completion form loads.
- [ ] Instance form loads.
- [ ] Expected Client Scripts are present and enabled.
- [ ] No obsolete Client Scripts reappeared.
- [ ] Critical buttons render for authorized users.
- [ ] Critical buttons are hidden or blocked for unauthorized users.

## Evidence to retain

Add release notes with:

- Commit hash.
- Migration result.
- Validation result.
- Any fixture changes.
- Any known limitations.
- Post-deploy smoke-test result.

## Stop conditions

Stop the release and do not proceed if:

- Candidate migration fails.
- Fixture diff includes unexplained deletions/additions.
- A critical workflow cannot be smoke-tested.
- A permission change locks out an expected role.
- A server-side validation blocks an existing intended workflow.
- Rollback path is unclear for a risky change.
