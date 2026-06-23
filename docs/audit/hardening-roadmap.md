# Hardening Roadmap

This roadmap turns the current exploratory audit into an implementation sequence. The goal is to reach handoff-quality ownership without changing the operator experience unexpectedly.

## Guiding constraints

- Production behavior is the baseline.
- Candidate sandbox validates every risky change.
- User experience remains unchanged unless a behavior change is explicitly approved.
- No operational data becomes fixture-managed.
- Server-side gates become authoritative.
- Documentation changes travel with code changes.

## Phase 1: Documentation and validation foundation

Status: in progress.

Purpose: make the system understandable and testable before changing structure.

Tasks:

- [x] Add repo documentation index.
- [x] Add architecture overview.
- [x] Add build-to-instance workflow.
- [x] Add source-of-truth policy.
- [x] Add fixture policy.
- [x] Add sandbox restore runbook.
- [x] Add release checklist.
- [x] Add rollback runbook.
- [x] Add permission matrix draft.
- [x] Add whitelisted method inventory.
- [x] Add generated fixture manifest.
- [x] Add local audit script for fixture drift.
- [x] Add Build Completion lifecycle validation script to repo.
- [x] Apply candidate-tested Draft Build Completion lifecycle fix.

Expected site experience change: none.

## Phase 2: Low-risk code fix and test capture

Purpose: apply the already validated lifecycle correction and capture repeatable validation.

Tasks:

- [ ] Update `build_completion.py` to allow new `Draft` or `Submitted`.
- [ ] Add `Draft -> Submitted` transition.
- [ ] Preserve direct `Accepted` block.
- [ ] Add validation script/test evidence.
- [ ] Run candidate migration and lifecycle validation.

Expected site experience change: fixes the Draft creation path; otherwise unchanged.

## Phase 3: Fixture governance

Purpose: eliminate normal dependence on GUI export/push.

Tasks:

- [ ] Generate full fixture row manifest.
- [ ] Identify app-owned Client Scripts.
- [ ] Replace broad `{"dt": "Client Script"}` filter with an explicit allowlist.
- [ ] Decide whether Workspaces and Wiki pages are repo-owned or DB-owned.
- [ ] Convert `fixture_sync.py` to audit-only or restrict it to System Manager/sandbox use.
- [ ] Add fixture drift comparison procedure.

Expected site experience change: none if allowlist is correct.

Risk: fixture narrowing can accidentally omit deployable config. Must be candidate-tested.

## Phase 4: Permission and role formalization

Purpose: make access control auditable.

Tasks:

- [ ] Confirm intended roles for Sales/Ops/Manufacturing/Builder/Product/System Manager.
- [ ] Complete desired permission matrix.
- [ ] Compare desired matrix to Custom DocPerm and User Permission records.
- [ ] Add or adjust Custom DocPerm only after approval.
- [ ] Add explicit role checks to state-changing whitelisted methods.
- [ ] Add role-based smoke tests.

Expected site experience change: none for authorized users; unauthorized bypasses may be blocked.

Risk: permission changes can lock out legitimate users. Must test by role.

## Phase 5: Server-side lifecycle completion

Purpose: ensure every critical workflow transition is guarded outside the browser.

Candidate lifecycle validators:

- InductOne Build status.
- InductOne Configuration Order status.
- BOM Export Package status.
- Configuration Option release/signoff status.
- As-Built locked immutability.
- Snapshot immutability after release.

Tasks:

- [ ] Define transition table for each stateful DocType.
- [ ] Add server validators through `doc_events`.
- [ ] Ensure every transition has a canonical action method if side effects are required.
- [ ] Add tests for invalid transitions and direct API bypass attempts.

Expected site experience change: none for valid workflows.

Risk: hidden legitimate manual paths may be blocked. Characterization first.

## Phase 6: Integration tests

Purpose: make deployment safety objective.

Tests to add:

- Build Completion lifecycle.
- Workbook upload and parse failure.
- Acceptance transaction success.
- Acceptance transaction rollback cases.
- Serial allocation and concurrency.
- Builder Tranche overlap/exhaustion.
- Instance status transitions.
- Engineering signoff approval/rejection/supersession.
- Part number allocation.
- Fixture migration smoke test.

Expected site experience change: none.

## Phase 7: Content and operator handoff

Purpose: align Wiki, Workspaces, landing pages, and repo docs.

Tasks:

- [ ] Inventory all Wiki pages and Workspaces.
- [ ] Classify as DB-owned operational content or repo-owned controlled documentation.
- [ ] Align operator-facing docs with actual workflow.
- [ ] Add admin runbooks for routine support tasks.
- [ ] Add troubleshooting guide for common failures.

Expected site experience change: content clarity may improve, but should be approved separately.

## Immediate next implementation batch

Recommended next batch after this documentation commit:

1. Apply the candidate-tested Draft Build Completion fix.
2. Add the lifecycle validation script under `scripts/` or `inductone_tools/tests/integration/`.
3. Generate a fixture manifest from current local fixtures.
4. Add a fixture drift audit script.
5. Run candidate migration and validation again.

This batch is low risk and begins converting the audit into enforceable maintenance practice.
