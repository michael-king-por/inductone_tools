# Candidate Smoke-Test Checklist

This is the manual smoke-test gate for the InductOne permission hardening work. It is meant to be filled out against the candidate sandbox after automated permission audits pass.

Do not run this against production unless a production test window has been explicitly approved.

## Environment

| Field | Value |
|---|---|
| Candidate URL | `http://inductone-candidate.localhost:8000` |
| Candidate site | `inductone-candidate.localhost` |
| Candidate bench | `/home/michaelplusone/frappe-sandbox/benches/candidate-bench` |
| Validation evidence folder | `C:\hub\frappe-sandbox\validation-evidence` |
| Final automated audit | `candidate_permission_audit_operational_roles_final.jsonl` |
| Candidate-only test password | `InductOne-Sandbox-Test-2026!` if reset script has been run |

## Evidence rule

For every row, record `PASS`, `FAIL`, `BLOCKED`, or `N/A`.

For each failure, record:

- tested user,
- page URL or DocType,
- expected behavior,
- actual behavior,
- screenshot path if useful,
- suspected cause: Role, Role Profile, DocPerm, User Permission, workspace visibility, server method gate, or file permission.

## Preflight gate

| Check | Expected | Result | Notes |
|---|---|---|---|
| Candidate loads | Login/Desk loads at `http://inductone-candidate.localhost:8000` |  |  |
| Baseline untouched | No commands are run against `inductone-baseline.localhost` |  |  |
| Production untouched | No commands are run against `plusonerobotics.v.frappe.cloud` |  |  |
| App state synced | Candidate app was synced from local repo |  |  |
| Migrate passed | `bench --site inductone-candidate.localhost migrate` succeeded |  |  |
| Cache cleared | `bench --site inductone-candidate.localhost clear-cache` run after permission changes |  |  |
| Automated audit exists | Final JSONL audit exists in validation evidence folder |  |  |
| Broad profile cleanup | Christina does not retain `System Manager` in strict target model |  |  |
| Builder scoping | Motion/LAM have Supplier User Permissions and no raw Item/BOM access |  |  |

## Personas

| Persona | Candidate user |
|---|---|
| Process Architect | `michael.king@plusonerobotics.com` |
| InductOne Manager + Engineering + Operations | `christina.gt@plusonerobotics.com` |
| InductOne Manager + Operations | `jim.haws@plusonerobotics.com` |
| InductOne Manager + Engineering + Operations | `david.brain@plusonerobotics.com` |
| Engineering User | `shaun.edwards@plusonerobotics.com`, `jason.minica@plusonerobotics.com`, `wayne.kirk@plusonerobotics.com`, `david.moreno@plusonerobotics.com` |
| External Builder - Motion Controls | `motion.builder@plusonerobotics.com` |
| External Builder - LAM | `lam@plusonerobotics.com` |
| Operations Viewer | `candidate.operations.viewer@example.invalid` |
| Inventory Operator | `candidate.inventory.operator@example.invalid` |
| Gripper Manufacturer | `candidate.gripper.manufacturer@example.invalid` |
| Finance Viewer | `candidate.finance.viewer@example.invalid` |
| Procurement User | `candidate.procurement.user@example.invalid` |

## Workspace and navigation checks

| Persona | Check | Expected | Result | Notes |
|---|---|---|---|---|
| External Builder | Login/navigation | Builder-facing workspace or portal visible |  |  |
| External Builder | Operations workspace | Hidden unless intentionally granted |  |  |
| External Builder | Engineering workspace | Hidden unless intentionally granted |  |  |
| InductOne Manager | InductOne workflow navigation | Can reach build/configuration/completion records |  |  |
| Engineering User | Engineering navigation | Can reach signoff and part-number workflows |  |  |
| Operations Viewer | Operational navigation | Can reach operating records, no mutation buttons |  |  |
| Operations Manager | ERPNext operations navigation | Can reach Items, BOMs, Sales Orders, Delivery Notes, Stock, Work Orders |  |  |
| Finance Viewer | Audit navigation | Can reach sales/purchase/accounting/audit records read-only |  |  |
| Procurement User | Procurement navigation | Can reach Items, Suppliers, Item Prices, Price Lists |  |  |

## External Builder checks

Run for both `motion.builder@plusonerobotics.com` and `lam@plusonerobotics.com`.

| Area | Test | Expected | Result | Notes |
|---|---|---|---|---|
| Login | Log in as builder | Login succeeds |  |  |
| Configuration Order list | Open list | Only assigned supplier handoff records visible |  |  |
| Configuration Order form | Open assigned record | Opens read-only / controlled access only |  |  |
| Configuration Order files | Download generated files | Intended files download |  |  |
| BOM Export Package list | Open list | Only assigned packages visible |  |  |
| BOM Export Package files | Download package | Generated ZIP/PDF/STL/DXF package downloads |  |  |
| Configured BOM Snapshot list | Open list | Only assigned/generated snapshot context visible |  |  |
| Snapshot outputs | Open/download generated outputs | Intended outputs accessible |  |  |
| Build Completion list | Open list | Completion path visible |  |  |
| Build Completion workbook | Upload/update workbook | Controlled upload/update works |  |  |
| Raw Item | Navigate to `/app/item` | Denied or empty/no meaningful records |  |  |
| Raw BOM | Navigate to `/app/bom` | Denied or empty/no meaningful records |  |  |
| Raw Sales Order | Navigate to `/app/sales-order` | Denied or empty/no meaningful records |  |  |
| InductOne Build | Navigate to `/app/inductone-build` | Denied/no release authority |  |  |
| Builder Tranche | Navigate to tranche list | Denied |  |  |
| Engineering Signoff | Navigate to signoff list | Denied |  |  |
| Part Number Allocation | Navigate to allocation request | Denied |  |  |
| Fixture Export | Try export control | Denied |  |  |

## InductOne Manager checks

Run as `christina.gt@plusonerobotics.com`, `jim.haws@plusonerobotics.com`, and `david.brain@plusonerobotics.com` where applicable.

| Area | Test | Expected | Result | Notes |
|---|---|---|---|---|
| InductOne Build | List/open | Allowed |  |  |
| InductOne Build | Create draft | Allowed |  |  |
| InductOne Build | Edit operational fields | Allowed |  |  |
| Configuration Option | List/open | Read allowed |  |  |
| Configuration Option | Create/edit | Denied unless Process Architect |  |  |
| Builder Tranche | List/open | Read-only or denied unless Process Architect |  |  |
| Builder Tranche | Create/edit | Denied unless Process Architect |  |  |
| Snapshot | Generate configured snapshot | Allowed when preconditions satisfied |  |  |
| Configuration Order | Generate/create CO | Allowed |  |  |
| Builder Package | Generate BOM Export Package | Allowed |  |  |
| Release | Release to builder | Allowed for trained manager |  |  |
| Serial Allocation | Allocate serials | Allowed when tranche/preconditions exist |  |  |
| Completion | Upload workbook | Allowed |  |  |
| Completion | Review/reject | Allowed when status permits |  |  |
| Completion | Accept | Allowed when preconditions met |  |  |
| As-Built / Instance | Accept creates records | Created only through controlled action |  |  |
| Fixture Export | Try export | Denied unless Process Architect/System Manager |  |  |

## Process Architect checks

Run as `michael.king@plusonerobotics.com`.

| Area | Test | Expected | Result | Notes |
|---|---|---|---|---|
| Configuration Options | Create/edit/retire | Allowed |  |  |
| Builder Tranches | Create/edit | Allowed |  |  |
| Fixture Export Control | Open | Allowed |  |  |
| Fixture Export Action | Execute in candidate only | Allowed in candidate; do not test production casually |  |  |
| InductOne records | Emergency read/write | Allowed |  |  |
| User Permissions | Inspect builder scoping | Allowed |  |  |

## Engineering User checks

Run as at least one engineering-only user.

| Area | Test | Expected | Result | Notes |
|---|---|---|---|---|
| Engineering Signoff | List/open | Allowed |  |  |
| Engineering Signoff | Approve | Allowed when status permits |  |  |
| Engineering Signoff | Reject | Allowed when status permits |  |  |
| Engineering Signoff | Supersede/revise | Allowed if method/status permits |  |  |
| Part Number Request | List/open | Allowed |  |  |
| Part Number Request | Allocate/generate | Allowed |  |  |
| Part Number Assignment | Read | Allowed |  |  |
| InductOne Build | Create/edit | Denied unless also InductOne Manager |  |  |
| Item/BOM | Create/edit | Denied unless also Operations Manager |  |  |
| Sales Order | Create/submit | Denied unless also Operations Manager |  |  |

## Operations Viewer checks

Run as `candidate.operations.viewer@example.invalid`.

| Area | Test | Expected | Result | Notes |
|---|---|---|---|---|
| Item/BOM/Product Bundle | List/open | Read-only allowed |  |  |
| Sales/Delivery/Stock/Work/Purchase docs | List/open | Read-only allowed |  |  |
| Accounting/audit records | List/open | Read-only allowed where included |  |  |
| InductOne records | List/open | Read-only allowed |  |  |
| Create buttons | Check major DocTypes | No create button or create denied |  |  |
| Edit/save | Attempt edit on representative docs | Denied |  |  |
| Submit/cancel | Attempt if visible | Denied/not visible |  |  |

## Operations Manager checks

Run as `jim.haws@plusonerobotics.com` and/or `christina.gt@plusonerobotics.com`.

| Area | Test | Expected | Result | Notes |
|---|---|---|---|---|
| Item | Create/edit | Allowed |  |  |
| BOM | Create/edit | Allowed |  |  |
| Product Bundle | Create/edit | Allowed |  |  |
| Sales Order | Create/submit/cancel/amend | Allowed if ERPNext status permits |  |  |
| Delivery Note | Create/submit/cancel | Allowed if preconditions permit |  |  |
| Stock Entry | Create/submit/cancel | Allowed |  |  |
| Work Order | Create/submit/cancel | Allowed if preconditions permit |  |  |
| Purchase Order | Create/submit/cancel | Allowed if preconditions permit |  |  |
| Purchase Receipt | Create/submit/cancel | Allowed if preconditions permit |  |  |
| GL Entry / Payment Entry | Create/edit | Denied; accounting mutation not included |  |  |
| Configuration Option | Create/edit | Denied unless Process Architect |  |  |
| Builder Tranche | Create/edit | Denied unless Process Architect |  |  |

## Inventory Operator checks

Run as `candidate.inventory.operator@example.invalid`.

| Area | Test | Expected | Result | Notes |
|---|---|---|---|---|
| Item/BOM/Sales/Purchase/Work Orders | List/open | Read-only allowed |  |  |
| Delivery Note | Create/edit/submit/cancel | Allowed if preconditions permit |  |  |
| Stock Entry | Create/edit/submit/cancel | Allowed |  |  |
| Purchase Receipt | Create/edit/submit/cancel | Allowed if preconditions permit |  |  |
| Material Request | Create/edit/submit/cancel | Allowed if preconditions permit |  |  |
| Pick List | Create/edit/submit/cancel | Allowed if preconditions permit |  |  |
| Stock Reconciliation | Create/edit/submit/cancel | Allowed if preconditions permit |  |  |
| Item/BOM/Sales Order/Work Order | Create/edit/submit | Denied where not listed above |  |  |

## Gripper Manufacturer checks

Run as `candidate.gripper.manufacturer@example.invalid`.

| Area | Test | Expected | Result | Notes |
|---|---|---|---|---|
| Item/BOM/Product Bundle | List/open | Read-only allowed |  |  |
| Work Order | Create/edit/submit/cancel | Allowed for gripper/refurbishment workflow |  |  |
| Stock Entry | Create/edit/submit/cancel | Allowed for manufacturing movement |  |  |
| Pick List | Create/edit/submit/cancel | Allowed |  |  |
| Sales/Purchase docs | Create/edit/submit | Denied |  |  |
| InductOne Build | Create/edit | Denied unless separately assigned |  |  |

## Finance Viewer checks

Run as `candidate.finance.viewer@example.invalid`.

| Area | Test | Expected | Result | Notes |
|---|---|---|---|---|
| Sales records | List/open/export/print | Read-only allowed |  |  |
| Purchase records | List/open/export/print | Read-only allowed |  |  |
| Stock records | List/open/export/print | Read-only allowed |  |  |
| Accounting records | GL Entry, Payment Entry, Journal Entry read-only | Allowed |  |  |
| InductOne records | List/open/export/print | Read-only allowed |  |  |
| Create/edit | Try representative docs | Denied |  |  |
| Submit/cancel | Try if visible | Denied/not visible |  |  |

## Procurement User checks

Run as `candidate.procurement.user@example.invalid`.

| Area | Test | Expected | Result | Notes |
|---|---|---|---|---|
| Item | Open existing Item | Allowed |  |  |
| Item | Edit level-0 description/vendor fields | Allowed |  |  |
| Item | Create new Item | Denied |  |  |
| Item | Edit permlevel-1 fields such as `standard_rate` / `valuation_rate` | Denied by design |  |  |
| Supplier | Open/edit | Allowed |  |  |
| Address/Contact | Open/edit | Allowed |  |  |
| Item Price | Create | Allowed |  |  |
| Item Price | Edit existing | Allowed |  |  |
| Price List/UOM/Item Group/Brand | Open/edit as required | Allowed |  |  |
| Purchase docs | Open | Read-only allowed |  |  |
| Sales Order | Create/edit/submit | Denied |  |  |
| InductOne actions | Try build/signoff/allocation actions | Denied unless separately assigned |  |  |

## Direct API / method checks

| Method family | Authorized roles | Unauthorized personas to test | Result | Notes |
|---|---|---|---|---|
| Release to builder | `InductOne Manager` | External Builder, Operations Viewer, Engineering-only |  |  |
| Allocate serials | `InductOne Manager` | External Builder, Operations Viewer, Engineering-only |  |  |
| Upload/review/accept completion | `InductOne Manager`; builder only for controlled upload/update | Operations Viewer, Engineering-only, unrelated builder |  |  |
| Engineering approve/reject | `Engineering User` | External Builder, Operations Viewer, Operations-only |  |  |
| Part number allocation | `Engineering User` | External Builder, Operations Viewer, Operations-only |  |  |
| Fixture export/push | `InductOne Process Architect` / System Manager policy | Everyone else |  |  |

## File and attachment checks

| Persona | File type | Expected | Result | Notes |
|---|---|---|---|---|
| External Builder | Generated builder ZIP/PDF/STL/DXF | Can download only assigned/generated handoff artifacts |  |  |
| External Builder | Raw source files not in generated handoff | Denied |  |  |
| InductOne Manager | Handoff/completion files | Allowed |  |  |
| Operations Viewer | Business attachments | Read-only where parent visible |  |  |
| Finance Viewer | Audit/business attachments | Read-only where parent visible |  |  |
| Procurement User | Item/Supplier/Item Price attachments | Allowed where parent visible/editable |  |  |

## Final go/no-go gate

| Gate | Required condition | Result | Notes |
|---|---|---|---|
| Fixture validation | `custom_docperm.json` parses and has unique keys |  |  |
| Candidate migrate | Migration succeeds |  |  |
| Automated audit | Final JSONL audit exists and key checks pass |  |  |
| External builders | Motion/LAM pass positive and negative tests |  |  |
| Internal managers | Christina/Jim/David pass intended access without broad Role Profile masking |  |  |
| Engineering | Engineering-only user can sign/allocate but cannot operate unrelated workflows |  |  |
| Operations roles | Viewer/Manager/Inventory/Gripper tests pass |  |  |
| Finance | Finance Viewer read-only audit access passes |  |  |
| Procurement | Procurement edit path passes and Item permlevel-1 remains protected |  |  |
| Wiki follow-up | Wiki/landing pages match final role model |  |  |
| Production plan | Exact commit, data/user assignment steps, rollback, and evidence requirements documented |  |  |

