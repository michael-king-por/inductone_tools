# InductOne Documentation Index

This documentation is written for ownership handoff. It should let a future maintainer understand what the system does, where each behavior lives, how it is deployed, how it is tested, and which areas still need hardening.

## Core system documentation

- [Architecture overview](architecture.md)
- [InductOne build-to-instance workflow](workflows/inductone-build-to-instance.md)
- [Lifecycle and state-machine reference](workflows/lifecycle-reference.md)

## Deployment and source control

- [Source-of-truth policy](deployment/source-of-truth-policy.md)
- [Fixture policy](deployment/fixture-policy.md)
- [Current fixture manifest](deployment/fixture-manifest.md)
- [Sandbox restore and validation runbook](deployment/sandbox-restore.md)
- [Release checklist](deployment/release-checklist.md)
- [Rollback runbook](deployment/rollback.md)

## Security, permissions, and auditability

- [Permission matrix](security/permission-matrix.md)
- [Role governance audit](security/role-governance-audit.md)
- [Role effect map](security/role-effect-map.md)
- [Role migration and validation gameplan](security/role-migration-validation-gameplan.md)
- [Permission hardening test plan](security/permission-test-plan.md)
- [Candidate smoke-test checklist](security/candidate-smoke-test-checklist.md)
- [GUI smoke validation - 2026-06-25](security/gui-smoke-validation-2026-06-25.md)
- [Hardening progress tracker](security/hardening-progress-tracker.md)
- [Whitelisted method inventory](security/whitelisted-methods.md)

## Hardening

- [Hardening roadmap](audit/hardening-roadmap.md)

## Validation suites

- `scripts/run_balloon_scoped_options_validation.py` — candidate-only 12-configuration validation for balloon-scoped electrical options. It generates real `Configured BOM Snapshot` records for build `SAL-ORD-2026-00054-BLD-0225`, materializes hierarchy rows, generates the hierarchy workbook, and asserts flat/hierarchy/workbook output against the independent oracle. This is the permanent guard for the baseline `173 → 11283 qty 2` hierarchy regression.
- `scripts/run_balloon_export_zip_closeout.py` — candidate-only package closeout for baseline, IPC, and everything-moved cable configurations. It references the stage-4 hierarchy evidence and asserts that the part-documentation payload remains stable across cable-only configurations.

## Documentation maintenance rule

When code or fixtures change behavior, update the relevant documentation in the same commit. If a change affects a button, status transition, permission boundary, whitelisted method, fixture ownership rule, deployment step, or operator workflow, it is documentation-relevant.

## Current evidence base

This documentation is based on:

- Local repo commit `9c51500be775ffe669276dad385cfb6cc07bd197`.
- Restored production backup from `2026-06-22 14:39:33`.
- Baseline sandbox matching deployed production app commit observed during audit.
- Candidate sandbox validation of the Build Completion Draft lifecycle fix.

Known limitation: the restored production clone had zero `InductOne Build Completion` and zero `InductOne As-Built Record` records. Completion and acceptance behavior therefore needs synthetic integration tests in the sandbox rather than relying on historical production examples.
