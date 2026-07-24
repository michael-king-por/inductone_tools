# InductOne Permission Model of Record

**Status: LOCKED by system owner.** This is the single source of truth for *intent*:
what user types exist and what each is for. The implementation lives in `fixtures/role.json`,
`fixtures/role_profile.json`, and `fixtures/custom_docperm.json`; the enforcement lives in the
role-expectation test (below). If those disagree with this document, this document wins and they are fixed.

Change control: any change to a role's purpose or boundary rides the Engineering Change / hardening process,
updates this document, and **must** update the role-expectation test in the same change.

## Global principles

1. Read-only roles (`Operations Viewer`, `Global Viewer`) never carry write/create/delete/
   submit/cancel bits. Ever.
2. External builders are **Builder Portal only** and supplier-scoped; they never see raw internal records or the
   Field Change (FCO) DocTypes.
3. Framework metadata (`DocType`, `Custom DocPerm`) read/write is **System-Manager-only by Frappe design** and
   cannot be granted by Custom DocPerm. Any role's "read everything" stops at this boundary.
4. No enabled user holds a broad Role Profile (`Super` / `System Manager` / `All`) except the single deliberate
   System Manager.
5. Permission rows are fixture-owned and convergence-clean: deterministic `perm_*` names, zero DB-only rows,
   zero duplicate permission-key groups.
6. One authoritative source per artifact; permissions are not hand-edited in production.

## Role charter

### System Manager  *(framework role, deliberately assigned)*
- **Purpose:** system administration.
- **Can:** everything, including framework metadata, user/role administration, and integrations.
- **Holders:** `ian.deliz` only — the single deliberate sysadmin.

### InductOne Process Architect
- **Purpose:** owns the InductOne configuration and process architecture; highest InductOne authority.
- **Can:** release/write Configuration Options via Engineering Signoff; supersede released options; allocate part
  numbers; approve/reject Engineering Signoffs; define the configuration model.
- **Cannot:** system administration; framework-metadata read/write.
- **Holders:** `michael.king`.

### InductOne Manager
- **Purpose:** InductOne operational management — fleet, field changes, builds.
- **Can:** manage `InductOne Instance`; create/triage/disposition/accept `InductOne Field Change Request` and
  `InductOne Field Change`; manage Builds and Configuration Orders; read across InductOne.
- **Cannot:** write/release Configuration Options or process architecture (Process Architect only); approve
  Engineering Signoffs; system admin.
- **Holders:** `michael.king`, `christina.gt`, `jim.haws`, `david.brain`.

### Engineering User
- **Purpose:** engineering authority — signoffs, part numbers, engineering reports.
- **Can:** approve/reject Engineering Signoffs (BOM, Item, Product Bundle, Configuration Option); allocate part
  numbers; read BOM/Item; run engineering reports (e.g. Electrical Balloon Callouts).
- **Cannot:** create/submit operational transactions (Sales Orders); mutate accounting; system admin.
- **Holders:** `shaun.edwards`, plus the owner/manager set (`michael.king`, `christina.gt`, `david.brain`,
  `jason.minica`, `wayne.kirk`, `david.moreno`).

### Operations Manager
- **Purpose:** operations transaction management.
- **Can:** create/submit Sales Orders and stock issues; read/select Account for Sales Orders; operational workflows.
- **Cannot:** Engineering Signoff approval; write Configuration Options/architecture; accounting mutation; admin.
- **Holders:** `patty.gomez`, `nathaniel.pantuso`, plus `michael.king`, `christina.gt`, `jim.haws`, `david.brain`.

### Operations Viewer
- **Purpose:** read-only operational visibility over the core stock/sales scope.
- **Can:** read the ~40-DocType core stock/sales scope and its dependencies (Item, BOM, Sales Order, Stock Entry,
  Warehouse, Supplier, GL Entry, etc.).
- **Cannot:** any create/write/submit; unused sales/manufacturing/CRM/POS doctypes are intentionally out of scope.
- **Holders:** `jason.minica`, `wayne.kirk`, `david.moreno`. None of these may hold `Operations Manager`.

### Inventory Operator
- **Purpose:** stock-movement execution.
- **Can:** submit stock movement documents (Material Receipt, Stock Entry) and their batch/serial dependencies.
- **Cannot:** sales/accounting mutation; admin.
- **Holders:** `nathaniel.pantuso`, `patty.gomez`, `michael.king`.

### Gripper Manufacturer
- **Purpose:** gripper manufacturing workflows.
- **Can:** submit Work Orders and manufacture Stock Entries for grippers.
- **Cannot:** broad operations/finance mutation; external/internal data outside the gripper workflow.
- **Holders:** `nathaniel.pantuso`.

### Procurement User
- **Purpose:** procurement and pricing.
- **Can:** create/write Item Price; create/view Purchase Orders.
- **Cannot:** create Item; write Item permlevel-1 fields; accounting mutation; admin.
- **Holders:** `matthew.mcmillan`.

### Finance Viewer  *(RETIRED — refactored into Global Viewer)*
Finance/audit read visibility is now served by **Global Viewer**. There is no separate finance-only viewer role:
anyone needing broad read visibility (finance, audit, executive) gets Global Viewer. The `Finance Viewer` role,
its Custom DocPerm rows, and its report grants (Balance Sheet / General Ledger / Trial Balance) are removed —
Global Viewer already covers those reports. If a finance-*only*-scoped viewer is ever needed (e.g. an external
accountant who must not see operational or engineering data), re-add it deliberately.

### Global Viewer
- **Purpose:** universal read/report/export visibility (finance / audit / executive) with no mutation and no admin. Supersedes the former Finance Viewer role.
- **Can:** read + report + export all business, operational, and financial data, all system configuration, and
  every report.
- **Cannot:** write/create/delete/submit/cancel anything; system administration.
- **Framework carve-out (owner-accepted):** cannot read raw `DocType` or `Custom DocPerm` metadata — these are
  System-Manager-only by Frappe design and are not business data or reports. This is the intended boundary, not a gap.
- **Holders:** `matt.speer`.

### InductOne External Builder
- **Purpose:** external build suppliers — Builder Portal only.
- **Can:** the Builder Portal only: their supplier-scoped `InductOne Configuration Order` and
  `InductOne Build Completion`, status-gated to Released / Awaiting Completion / Closed.
- **Cannot:** raw `BOM Export Package` or `Configured BOM Snapshot` Desk records; Field Change DocTypes; Draft
  Configuration Orders; any other workspace; any internal ERPNext data.
- **Holders:** `motion.builder` (Motion Controls), `lam` (LAM), each supplier-scoped by User Permission.

## Role-expectation test (the permanent enforcement)

A persona user is created per role in candidate. For each role the test asserts, and fails on any drift:

- **Positive (must have):** the "Can" capabilities above, exercised as real actions — create/submit/approve the
  documents the role owns; open the workspaces, pages, and reports the role needs; read/export the data it needs.
- **Negative (must not have):** the "Cannot" boundaries — denied create/write/submit on out-of-scope doctypes;
  denied workspaces; external builders denied raw records and FCO; viewers denied all mutation; only System Manager
  reads framework metadata.

The test is derived from this charter (charter = intent, test = lock). It runs in candidate, is required in the
pre-deploy gate, and is re-run on any change touching roles, Custom DocPerm, workflows, or workspaces. A change to
a role's intent is not "done" until this test encodes the new expectation and passes.
