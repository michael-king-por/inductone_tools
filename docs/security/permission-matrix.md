# Permission Matrix

This document records the current observed permission posture and the target audit model for InductOne Tools.

It is intentionally conservative. Current observations do not automatically imply the final desired model. Permissions should be changed only after role intent is confirmed and tested in a candidate sandbox.

## June 25, 2026 target model

The current target model is documented in [Role Governance Audit](role-governance-audit.md). That document supersedes the earlier transitional role names below.

Target custom roles:

- `InductOne Manager`
- `InductOne Process Architect`
- `Operations Viewer`
- `Operations Manager`
- `Inventory Operator`
- `Gripper Manufacturer`
- `Engineering User`
- `InductOne External Builder`
- `Finance Viewer`
- `Procurement User`

Legacy/transitional roles should not be used as the final authority layer:

- `InductOne Process Manager`
- `InductOne Architect`
- `Engineering Signoff Delegate`
- `Part Number Manager`
- `Engineering - Signoff`
- `OPS-INDUCTONE-GATEKEEP`
- `PRODUCT-INDUCTONE-GATEKEEP`
- generic `Builder`
- generic `Manufacturing User`
- generic `Project Manager` / `Projects Manager`

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

## Confirmed target personas

The following target personas were confirmed during the June 2026 hardening review.

| Persona / role | Intended users | Purpose |
|---|---|---|
| External Builder | `motion.builder@plusonerobotics.com`, `lam@plusonerobotics.com` | Access assigned builder-facing handoff artifacts and upload completion workbooks. |
| InductOne Process Manager | `michael.king@plusonerobotics.com`, `christina.gt@plusonerobotics.com`, `jim.haws@plusonerobotics.com`, `david.brain@plusonerobotics.com` | Own normal InductOne workflow: create/edit Builds, release to builder, allocate serials, upload/review/reject/accept completions. |
| InductOne Architect/Admin | initially `michael.king@plusonerobotics.com` | Maintain Builder Tranches, architecture, fixtures, schema, and emergency correction paths. |
| Engineering Signoff Approver | `shaun.edwards@plusonerobotics.com`, `jason.minica@plusonerobotics.com`, `wayne.kirk@plusonerobotics.com`, `david.moreno@plusonerobotics.com` | Official engineering approval/rejection of controlled engineering artifacts. |
| Engineering Signoff Delegate | `michael.king@plusonerobotics.com`, `christina.gt@plusonerobotics.com`, `david.brain@plusonerobotics.com` | Explicit delegate role for approving/rejecting signoffs on engineering's behalf. |
| Part Number Manager | `michael.king@plusonerobotics.com`, `christina.gt@plusonerobotics.com`, `david.brain@plusonerobotics.com`, engineering approvers | Allocate part numbers. |
| System Manager | sharply reduced admin set | ERPNext/site administration only; not a substitute for InductOne workflow access. |

Deprecated or transitional roles:

- `OPS-INDUCTONE-GATEKEEP`
- `PRODUCT-INDUCTONE-GATEKEEP`

These appear deprecated by intent. They should not be used for new permission hardening unless deliberately repurposed.

## Implemented repo model

As of the June 23, 2026 hardening implementation, the repository includes:

- `inductone_tools.external_builder_permissions`, which enforces external-builder query scoping in code.
- `permission_query_conditions` hooks for:
  - `Item`,
  - `BOM`,
  - `InductOne Configuration Order`,
  - `BOM Export Package`,
  - `InductOne Build Completion`,
  - `Configured BOM Snapshot`.
- `has_permission` hooks for raw `Item` and `BOM` denial.
- role fixtures for:
  - `InductOne External Builder`,
  - `InductOne Process Manager`,
  - `InductOne Architect`,
  - `Engineering Signoff Delegate`,
  - `Part Number Manager`.
- a role profile fixture for `InductOne External Builder`.
- a migration patch: `inductone_tools.patches.v2026_06_23_external_builder_permissions`.

The patch intentionally stops using the generic `Builder` role and the generic `Builder` Role Profile for external InductOne supplier access because sandbox testing showed that profile can rehydrate broad roles (`Builder`, `Manufacturing User`) and expose raw ERPNext `Item`/`BOM` access. External builder users are moved to the `InductOne External Builder` role and Role Profile instead.

The patch also removes Item Group User Permissions from the external builder accounts and keeps only Supplier scoping:

- `motion.builder@plusonerobotics.com` -> `Motion Controls`
- `lam@plusonerobotics.com` -> `LAM`

Configured BOM Snapshot access is indirect: an external builder can list/open snapshots only when the snapshot is linked to a Configuration Order or BOM Export Package assigned to one of that user's Supplier values.

External builder workspace access is also moved from the old `Builder` role to `InductOne External Builder`. The intended external landing surface is `Builder Portal`. The old `Build` workspace is deprecated and should stay hidden; Operations and Engineering workspaces are not intended for supplier users.

Known UI nuance: Frappe's implicit `Desk User` role can still make some report/export/print affordances appear enabled for `Item`, but the query condition returns no rows for external-builder-only users. This must be included in UI smoke testing.

## Target permission model

The target model should be documented and then implemented. Do not infer final policy from current rows alone.

| DocType | External Builder | InductOne Process Manager | Engineering Approver / Delegate | InductOne Architect/Admin | System Manager |
|---|---|---|---|---|
| InductOne Build | No direct access unless proven necessary | Create/edit/manage assigned/internal Builds | Read if needed | Full architect/admin | Full admin |
| InductOne Configuration Option | No direct access | Read released/usable options | Approve/reject/supersede through signoff | Admin as needed | Full admin |
| InductOne Configuration Order | Read assigned builder-facing orders | Create/update/release workflow | Read if needed | Full architect/admin | Full admin |
| BOM Export Package | Read/download assigned generated packages only | Generate/manage packages | Read if needed | Full architect/admin | Full admin |
| Configured BOM Snapshot | Read assigned generated snapshots/diff output only | Generate/read snapshots | Read if needed | Full architect/admin | Full admin |
| Raw Item / BOM / Sales Order | No access through InductOne builder workflow | Access only if separately required by ERPNext duties | Access only if separately required | Admin as needed | Full admin |
| InductOne Builder Tranche | No access | Allocate serials only through controlled action | No access | Create/edit/retire tranches | Full admin |
| InductOne Build Completion | Upload completion workbook / update assigned evidence as intentionally exposed | Upload/review/reject/accept through actions | Read if needed | Full architect/admin | Full admin |
| InductOne As-Built Record | Read assigned locked evidence only if useful | Read locked evidence | Read if needed | Full architect/admin; mutation restricted | Full admin |
| InductOne Instance | Usually no access unless support reference needed | Read/update lifecycle through allowed actions | Read if needed | Full architect/admin | Full admin |
| Engineering Signoff | No access | Request/read as needed | Approve/reject/supersede | Full architect/admin | Full admin |
| Part Number Allocation Request | No access | Allocate only if assigned Part Number Manager | Read/review/allocate if assigned | Full architect/admin | Full admin |
| Fixture Export Control | No access | No access | No access | System/architect only | Full admin |

## External builder access intent

External builders should receive generated handoff artifacts, not live engineering/ERP source records.

They should be able to access:

- assigned `InductOne Configuration Order` records,
- assigned `BOM Export Package` records,
- generated files attached to those packages/orders,
- assigned `Configured BOM Snapshot` and generated diff/snapshot outputs,
- assigned `InductOne Build Completion` records or controlled upload path for completion workbook submission.

They should not be able to access:

- raw `Item` records,
- raw `BOM` records,
- `Sales Order` records,
- unrelated supplier/build records,
- `InductOne Builder Tranche`,
- fixture/export/admin tooling.

This must be validated in a sandbox by testing list/form/file/report access as `motion.builder@plusonerobotics.com` and `lam@plusonerobotics.com`.

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

## Confirmed next permission-hardening work

1. Run `bench migrate` in a candidate sandbox and verify the migration patch result.
2. Confirm external builders use `InductOne External Builder`, not `Builder`.
3. Confirm external builders no longer have `Manufacturing User` or Item Group User Permissions.
4. Confirm assigned Supplier User Permissions remain correct.
5. Reduce broad `System Manager` assignment in candidate after access smoke tests pass.
6. Run effective-access tests for:
   - process manager,
   - external builder,
   - engineering approver,
   - engineering delegate,
   - part number manager,
   - ordinary internal user.

## Handoff requirement

The future owner should not need to inspect random GUI settings to know who can do what. This file should become the authoritative permission intent, while fixtures and server checks become the implementation.
