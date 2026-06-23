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
- [Whitelisted method inventory](security/whitelisted-methods.md)

## Hardening

- [Hardening roadmap](audit/hardening-roadmap.md)

## Documentation maintenance rule

When code or fixtures change behavior, update the relevant documentation in the same commit. If a change affects a button, status transition, permission boundary, whitelisted method, fixture ownership rule, deployment step, or operator workflow, it is documentation-relevant.

## Current evidence base

This documentation is based on:

- Local repo commit `9c51500be775ffe669276dad385cfb6cc07bd197`.
- Restored production backup from `2026-06-22 14:39:33`.
- Baseline sandbox matching deployed production app commit observed during audit.
- Candidate sandbox validation of the Build Completion Draft lifecycle fix.

Known limitation: the restored production clone had zero `InductOne Build Completion` and zero `InductOne As-Built Record` records. Completion and acceptance behavior therefore needs synthetic integration tests in the sandbox rather than relying on historical production examples.
