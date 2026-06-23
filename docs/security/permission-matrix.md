# Permission Matrix

This document records the current observed permission posture and the target audit model for InductOne Tools.

It is intentionally conservative. Current observations do not automatically imply the final desired model. Permissions should be changed only after role intent is confirmed and tested in a candidate sandbox.

## Roles observed during audit

InductOne-specific roles observed:

- `OPS-INDUCTONE-GATEKEEP`
- `PRODUCT-INDUCTONE-GATEKEEP`

Other roles observed in Custom DocPerm rows:

- `System Manager`
- `Builder`
- `Manufacturing User`
- `Project Manager`
- `Projects Manager`

## Current observed Custom DocPerm rows

| DocType | Role | Read | Write | Create | Delete | Notes |
|---|---|---:|---:|---:|---:|---|
| InductOne Configuration Option | System Manager | 1 | 1 | 1 | 1 | Full administrative control. |
| InductOne Configuration Option | Project Manager | 1 | 0 | 0 | 0 | Read-only. |
| InductOne Configuration Option | Projects Manager | 1 | 0 | 0 | 0 | Read-only. |
| InductOne Configuration Order | System Manager | 1 | 1 | 1 | 1 | Full administrative control. |
| InductOne Configuration Order | Builder | 1 | 0 | 0 | 0 | Builder read-only. |
| InductOne Build Completion | System Manager | 1 | 1 | 1 | 1 | Full administrative control. |
| InductOne Build Completion | Builder | 1 | 1 | 0 | 0 | Builder can read/write but not create/delete. |
| BOM Export Package | System Manager | 1 | 1 | 1 | 1 | Full administrative control. |
| BOM Export Package | Builder | 1 | 0 | 0 | 0 | Builder read-only. |
| BOM Export Package | Manufacturing User | 1 | 1 | 1 | 0 | Manufacturing can create/write, not delete. |
| Configured BOM Snapshot | System Manager | 1 | 1 | 1 | 1 | Full administrative control. |
| Configured BOM Snapshot | Manufacturing User | 1 | 0 | 0 | 0 | Read-only. |

Several critical DocTypes did not show Custom DocPerm rows in the audited fixture-backed layer. That does not prove they are unprotected; it means the permission model needs explicit review:

- InductOne Build
- InductOne Builder Tranche
- InductOne As-Built Record
- InductOne Instance
- Engineering Signoff
- Part Number Allocation Request

## Target permission model

The target model should be documented and then implemented. Do not infer final policy from current rows alone.

| DocType | Builder | Manufacturing/Ops | Product/Engineering gatekeep | System Manager |
|---|---|---|---|---|
| InductOne Build | Read limited assigned builds; no destructive edits | Create/update through workflow actions | Read; maybe approve/release gates if defined | Full admin |
| InductOne Configuration Option | No access unless needed | Read released options | Create/edit/release through signoff | Full admin |
| InductOne Configuration Order | Read assigned released orders | Create/update through release workflow | Read/review | Full admin |
| BOM Export Package | Read assigned builder packages | Generate/manage packages | Read/review | Full admin |
| InductOne Builder Tranche | No access | Allocate via action only; no direct range edits | Maybe read | Full admin or designated serial admin |
| InductOne Build Completion | Upload/update assigned completion evidence | Review/reject/accept through actions | Read | Full admin |
| InductOne As-Built Record | Read assigned if appropriate | Read locked evidence | Read | Full admin; mutation restricted |
| InductOne Instance | Read assigned units if appropriate | Update lifecycle through allowed actions | Read | Full admin |
| Engineering Signoff | No access | Read | Request/approve/reject/supersede by gatekeeper roles | Full admin |
| Part Number Allocation Request | No access | Request/allocate as authorized | Review as needed | Full admin |

## Server-side enforcement rule

DocPerm controls form and API access, but any whitelisted method that uses `ignore_permissions=True` must enforce its own gate.

For each state-changing whitelisted method, require:

- Explicit role or permission check.
- Explicit current-state check.
- Required-field validation.
- Atomic transaction or clear failure state.
- Audit user/timestamp stamp where relevant.
- No silent partial success.

## Critical method gate recommendations

Add or verify explicit server-side authorization for:

| Method | Risk | Recommended gate |
|---|---|---|
| `build_completion_accept.accept_completion_create_as_built` | Creates As-Built, Instance, closes CO | Ops/System Manager or defined acceptance role. |
| `builder_release.release_to_builder_now` | Releases package to builder and changes operational state | Manufacturing/Ops release role. |
| `serial_allocation.release.allocate_serial_for_build` | Consumes serial from Builder Tranche | Ops/System Manager or serial allocation role. |
| `engineering_signoff.approve_signoff` | Releases controlled engineering artifact | Product/Engineering gatekeeper role. |
| `engineering_signoff.reject_signoff` | Rejects controlled engineering artifact | Product/Engineering gatekeeper role. |
| `fixture_sync.export_and_push_fixtures` | Pushes deployable configuration | System Manager only; preferably sandbox/audit-only. |
| `instance.backfill` functions if exposed | Creates historical support records | System Manager or data migration role only. |

## User Permission considerations

The restored clone had 14 User Permission records. User Permissions are often environment-specific and should usually remain database-owned.

Before fixture-managing User Permissions, answer:

- Are these generic app permissions or real user/vendor assignments?
- Would they be valid on another site?
- Could fixture import grant access to the wrong user?

Default answer: do not fixture User Permissions.

## Role-based smoke tests

For each release that changes permissions or method gates, test:

- System Manager can perform admin actions.
- Builder can see only assigned/read-appropriate records.
- Builder cannot create/delete protected records.
- Manufacturing/Ops can perform intended operational actions.
- Gatekeeper roles can perform signoff actions.
- Unauthorized roles cannot call whitelisted state-changing endpoints directly.

## Handoff requirement

The future owner should not need to inspect random GUI settings to know who can do what. This file should become the authoritative permission intent, while fixtures and server checks become the implementation.
