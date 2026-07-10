# Permission Hardening Test Plan

This plan defines how to test InductOne access changes before they touch production.

No permission hardening change should be deployed until the relevant persona tests pass in a restored candidate sandbox.

## Personas to test

| Persona | Representative users |
|---|---|
| External Builder - Motion Controls | `motion.builder@plusonerobotics.com` |
| External Builder - LAM | `lam@plusonerobotics.com` |
| InductOne Manager | `michael.king@plusonerobotics.com`, `christina.gt@plusonerobotics.com`, `jim.haws@plusonerobotics.com`, `david.brain@plusonerobotics.com` |
| InductOne Process Architect | initially `michael.king@plusonerobotics.com` |
| Engineering User | engineering approvers plus any explicit delegates who should approve signoffs and allocate part numbers |
| Operations Viewer | representative broad read-only internal user |
| Operations Manager | representative internal operations owner; must be able to submit Sales Orders and manage normal ERPNext operations |
| Inventory Operator | representative inventory/warehouse user |
| Gripper Manufacturer | representative serialized gripper manufacturing/refurbishment user |
| Finance Viewer | representative finance user |
| Procurement User | representative procurement user |
| Ordinary internal user | Select an internal user with no InductOne manager/delegate/builder role |

## External builder expected access

External builders should be able to:

- log in,
- see assigned `InductOne Configuration Order` records,
- open assigned Configuration Orders,
- download generated private/public files attached to assigned Configuration Orders,
- download generated builder package files from the Configuration Order document index,
- download generated hierarchy, balloon callout, flat BOM, release manifest, and builder workbook artifacts from the Configuration Order document index,
- upload or submit an assigned Build Completion workbook through the intended controlled path.

External builders should not be able to:

- list or open raw `Sales Order` records,
- list or open raw `Item` records,
- list or open raw `BOM` records,
- list or open raw `BOM Export Package` records,
- list or open raw `Configured BOM Snapshot` records,
- list unrelated suppliers' Configuration Orders,
- create/edit/delete Builder Tranches,
- use fixture export controls,
- release builds,
- allocate serials,
- accept completions,
- approve engineering signoffs,
- allocate part numbers.

## InductOne Manager expected access

InductOne Managers should be able to:

- create/edit InductOne Builds,
- load/select configuration options,
- generate snapshots and builder packages,
- release to builder,
- allocate serials,
- upload completion workbook,
- review/reject Build Completions,
- accept completions,
- create As-Built/Instance through the acceptance action,
- read relevant generated files and reports.

They should not necessarily be able to:

- edit Builder Tranche ranges unless also `InductOne Process Architect`,
- export/push fixtures unless `InductOne Process Architect` / System Manager policy permits,
- edit/create Configuration Options,
- bypass engineering signoff unless they also hold `Engineering User`.

## Engineering User expected access

Engineering Users should be able to:

- view controlled signoff targets as needed,
- approve/reject/supersede Engineering Signoff records,
- provide rejection/approval notes,
- create/manage Part Number Allocation Requests,
- allocate numbers,
- read Part Number Assignments,
- release assignment to Item/Product Bundle as intended by the workflow.

They should not automatically receive unrelated InductOne operational rights unless separately assigned.

## Operations and support roles

Operations Viewer should be able to read broadly but not mutate.

Operations Manager should be able to perform normal ERPNext operating workflows, including Sales Order submission, Item/BOM/Product Bundle maintenance, Delivery Notes, stock, and production workflows. This role should not grant InductOne action authority by itself.

Inventory Operator should be able to perform assigned inventory movement workflows without gaining Item/BOM/Sales Order master-data ownership.

Gripper Manufacturer should be able to execute serialized gripper work order and refurbishment workflows without gaining unrelated production authority.

Finance Viewer should be read-only with broad audit visibility.

Procurement User should be able to update confirmed procurement-facing vendor/pricing/descriptive item data without gaining engineering release or InductOne authority.

## InductOne Process Architect expected access

InductOne Process Architect should be able to:

- create/edit/retire Builder Tranches,
- manage emergency correction workflows,
- maintain fixtures/configuration,
- inspect all InductOne records,
- run sandbox/release/audit procedures.

This role should be rare.

## Test dimensions

For each persona, test:

- List visibility.
- Form open/read.
- Create.
- Write/edit.
- Delete.
- Report access.
- File download access.
- Button visibility.
- Direct whitelisted method call.
- Linked document traversal.

## Dependent document checks

When granting access to a parent record, verify whether linked documents are required:

| Parent record | Linked/dependent artifacts to verify |
|---|---|
| InductOne Configuration Order | generated document index/files, selected options, delta lines, snapshot link; builder-visible artifact delivery should happen here |
| BOM Export Package | internal generated package files, result rows, configured snapshot link; external builders receive the ZIP through the CO document index, not this raw page |
| Configured BOM Snapshot | internal hierarchy/diff output, generated workbook/report output; external builders receive generated files through the CO document index, not this raw page |
| Build Completion | uploaded workbook File, serial child rows |

If a user needs the generated output but not the raw linked source record, prefer generated files/controlled reports over direct raw DocType access.

## Sandbox implementation process

1. Restore candidate sandbox from production backup.
2. Apply the candidate branch/repo state.
3. Run `bench migrate` so fixtures and `inductone_tools.patches.v2026_06_23_external_builder_permissions` execute.
4. Verify role assignment changes:
   - Motion/LAM have `InductOne External Builder`.
   - Motion/LAM do not have `Builder`.
   - Motion/LAM do not have `Manufacturing User`.
   - Motion/LAM do not have Item Group User Permissions.
   - Motion/LAM retain Supplier User Permissions.
5. Run automated permission checks.
6. Manually smoke-test the UI as representative users.
7. Record failures.
8. Adjust matrix/code/fixtures.
9. Repeat until expected access is proven.
10. Only then promote the same repo state toward production.

## Automated external-builder checks

The June 2026 sandbox validation proved the expected pattern:

- Motion/LAM must see only their assigned Configuration Orders and Build Completions;
- Motion/LAM must not see BOM Export Package, Configured BOM Snapshot, Items, or BOMs as raw Desk pages;
- the generated BOM Export Package ZIP, hierarchy workbook, balloon callout workbook, flat BOM, release manifest, and builder workbook must be reachable through the assigned Configuration Order document index;
- raw `Item` list output was empty for external-builder-only users;
- raw `BOM`, `Sales Order`, `InductOne Build`, and `InductOne Builder Tranche` access was blocked.

Repeat that pattern after any future permission change.

## Candidate smoke-test log

| Date | Persona / user | Result | Notes |
|---|---|---|---|
| 2026-06-24 | Motion external builder / `motion.builder@plusonerobotics.com` | Confirmed pass | User confirmed in browser smoke test after candidate URL, role profile, workspace, and asset fixes. |
| 2026-06-24 | LAM external builder / `lam@plusonerobotics.com` | Confirmed pass | User confirmed LAM no longer sees unrelated Motion/Test supplier artifacts after Role Profile fix. |
| 2026-06-24 | InductOne Process Manager / `jim.haws@plusonerobotics.com` | Confirmed pass | User confirmed Jim's intended process-manager access; Jim remains excluded from Part Number Manager. |

Remaining candidate smoke tests:

- `christina.gt@plusonerobotics.com` or `david.brain@plusonerobotics.com` as Process Manager / Delegate / Part Number Manager.
- one Engineering Signoff Approver: `shaun.edwards@plusonerobotics.com`, `jason.minica@plusonerobotics.com`, `wayne.kirk@plusonerobotics.com`, or `david.moreno@plusonerobotics.com`.
- `Administrator` / System Manager for admin paths and regression checks.

## Required evidence

For each permission batch, capture:

- role assignment diff,
- DocPerm/Custom DocPerm diff,
- User Permission diff,
- list/read/write/create/delete test result,
- file download test result,
- report access test result,
- direct API call test result,
- screenshots or notes for critical UI paths.

## Wiki follow-up

After permission hardening, review the Wiki and landing pages to ensure they describe:

- who can perform each InductOne action,
- what external builders can access,
- what generated artifacts are safe to share,
- what raw ERPNext records are intentionally not shared,
- who to contact for release/signoff/part-number/admin actions.
