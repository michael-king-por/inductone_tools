# InductOne As-Installed Register + Field Change (FCO) + ERPNext Integration — Codex Build Spec

**Date:** 2026-07-13  **Author:** CSA overhaul (design)  **Executor:** Codex (candidate only)
**Status:** ready to build in candidate. Nothing in this spec touches production.

This is the consolidated, execution-ready build that completes the InductOne Configuration Status
Accounting (CSA) integration in ERPNext: it wires locations, backfills the fielded fleet as Instances,
adds the Field Change (FCO) module tied to those Instances, backfills the historical FCOs, and turns the
`SUP-FCO-R01` register into a generated export. It supersedes the backfill sections of the earlier
piecemeal specs (W8 and addenda).

## Operating rules — absolute
1. **Candidate only** (`inductone-candidate.localhost`). Never touch production; never push; never tag.
   Work on a local integration branch; the human reviews, merges, pushes.
2. **Baseline** (`:8010`) is reference-only.
3. **No `ignore_permissions=True`** in any new whitelisted method. New DocPerms via fixtures only.
4. New DocTypes go in module **`Operations - POR`**, matching the existing InductOne set.
5. Ingest the seed files verbatim (below). Do **not** re-derive or invent data.
6. Any ambiguity or schema conflict → **STOP and report**; do not choose silently.

## Ground truth (owner-confirmed)
- **Governance:** change/release = POR Engineering Change process **ECR → ECO → ECN. No CCB, no ECB.**
  Fleet-wide/design changes are ECRs (GitLab); ERPNext references them by number/link, does not model them.
- **Serials:** legacy fielded units use the `IN`+Julian mfg number (e.g. `IN001024262001`); go-forward and
  POC units use `IND-####` (e.g. `IND-3001`). Both are valid `system_serial` values by era.
- **Onexia = a builder** (Supplier), not a site/customer. "Onexia cell" = a cell built by Onexia.
- **Locations** are a real hierarchical DocType (`POR Physical Location`, nested-set, Site→Lane→Cell→Robot)
  that was orphaned; this build wires it as canonical at depth **Site→Lane→Cell**. SATX internal/reference units are segmented under **Display / Testing** (CEC, Golden Unit) and **Lab** (Amazon POC / outbound transient test units).

## Inputs — seed files (in `scripts/inductone_backfill/seeds/`)
- `location_tree_seed.xlsx` — POR Physical Location rows (Sites, Lanes, Cells; each Cell → instance serial).
- `instance_backfill_seed.xlsx` — sheet **Instances** (11 units: 8 fielded IN-serials + 2 SATX reference
  `REF-*` + Amazon `IND-3001`, each with `physical_location` Cell code, origin, status, config, component
  serials context); sheet **Pending Serial** (WP Primary-3 cells 3-2/3-3 awaiting serials — DO NOT create).
- `fco_instance_map.xlsx` — 19 FCOs → primary Instance (best guess) + confidence + spawn flags + reassignable.
- `fco_jotform_export.xlsx` — raw JotForm submissions (intake source of record).
- `SUP-FCO-R01_operating_backfilled.xlsx` — the backfilled FCO register (schema v2.0, 18 cols) for reference.

## Build phases (ordered; each has a gate)

### Phase 0 — dependencies
- Confirm Customers exist: **UPS, DHL, Amazon, Plus One Robotics** (POR, for internal SATX locations).
  If UPS, DHL, or Plus One Robotics is missing, STOP and report (do not create Customers silently).
  Owner decision of record, 2026-07-14: if `Amazon` is missing, create only a minimal Customer named
  `Amazon` with no additional details; owner will enrich the record later once reliable data is known.

### Phase 1 — POR Physical Location (canonical location tree)
1. Seed `POR Physical Location` from `location_tree_seed.xlsx` as a proper nested-set tree
   (Site `is_group`, Lane `is_group`, Cell leaf). Set customer, `*_code`, `full_path`, parent. Let Frappe
   maintain `lft`/`rgt`. Idempotent (skip existing by `location_code`).
2. Add Link field **`physical_location`** (options: POR Physical Location) to `InductOne Instance`.
   Make `deployment_site` a read-only label synced from the linked Cell's `full_path` (fetch_from or hook).
   Do NOT drop `deployment_site`.
3. **Relax** the three currently-REQD provenance links on `InductOne Instance`
   (`inductone_build`, `as_built_record`, `configuration_order`) so legacy/POC-origin Instances can exist
   without them; enforce them (validation) only for `origin = Born-in-system`.
4. Add `origin` (Select: Born-in-system | Legacy backfill | POC | Internal-Reference) to `InductOne Instance`.

### Phase 2 — Instance backfill
Load `instance_backfill_seed.xlsx` **Instances** sheet: 8 fielded (real IN serials) + 2 SATX `REF-*`
(internal-reference) + `IND-3001` (Amazon POC, staged at POR SA, status At Builder). Set origin, status,
customer, `physical_location` (Cell), component serials. No fabricated provenance. Idempotent by
`system_serial`. **Skip the "Pending Serial" sheet** (see Pending Additions).

### Phase 3 — Field Change module (DocTypes + change mechanism)
1. **`InductOne Field Change Request`** (intake + triage ledger). Naming `FCO-.YYYY.-.###`. Fields:
   date_raised, requester, requester_department, requester_role, intake_source (ERPNext | JotForm Import),
   intake_ref, title, description, reason, customer_project, machine_identifier (free text), scope,
   one_time_or_repeated, est_downtime_h, est_labor_h, parts_cost, implementer, tools_docs, ticket_link,
   **instance** (Link InductOne Instance — the assignment), triage_outcome (Field Change | Deviation | ECR),
   reference (EC/ECR/Epic/ticket), safety_regulatory, disposition, disposition_date, disposition_by,
   **assignment_confidence** (High|Med|Low|Backfill-guess), **assignment_basis**, **assignment_reviewed**
   (+_by/_at), notes. Workflow New→Triaged→Dispositioned→Closed (+Rejected/Cancelled), Ops roles only.
   **DocType `track_changes: 1`.** Doc hook: when `instance` changes, REQUIRE a reason (reject save
   otherwise). This is the tracked-but-changeable assignment mechanism.
2. **`InductOne Field Change`** (per-Instance as-maintained event). Naming `FC-.YYYY.-.####`. Fields:
   **instance** (Link, required), source_request (Link Request), reference (EC #), change_summary,
   implemented_date, implemented_by, post_change_test (Pass|Fail|N/A), as_maintained_updated (Check),
   notes, child table `component_serial_changes` (InductOne Field Change Serial: component, action
   Add|Remove|Replace, old_serial, new_serial). Lock-on-accept mirroring `InductOne As-Built Record`:
   accept stamps accepted_by/at, sets status Locked, updates the Instance as-maintained state; locked
   records are immutable. State mutation in a whitelisted method WITHOUT ignore_permissions; role-gated.
3. **Instance surfacing:** dashboard Connections group on `InductOne Instance` listing its Field Changes;
   client-script indicator (count + latest field-change date). Do not weaken Instance permissions.
4. **Monitor report "FCO Assignments Pending Review":** Requests where assignment_confidence in
   (Low, Backfill-guess) AND assignment_reviewed = 0.
5. **Permissions (fixtures):** create/triage/disposition/accept = Ops roles (Operations Manager,
   InductOne Manager, InductOne Process Architect); Operations Viewer read-only; **external builders NO
   access** to either DocType. Export to `custom_docperm.json`; new DocTypes/child/workflow/report to
   fixtures. Keep the exact-name Wiki fixture filter untouched.

### Phase 4 — FCO backfill aligned to Instances (per `fco_instance_map.xlsx`)
1. Create 19 `InductOne Field Change Request` records from `fco_jotform_export.xlsx` (map Flow Status →
   disposition: Complete→Approved, Denied/Canceled→Rejected/Cancelled, In Progress→Pending). Set
   triage_outcome, reference, and link the **primary Instance** per the map; set assignment_confidence and
   assignment_basis from the map (High/Med/Low). Dedup by intake_ref (Change No).
2. Spawn per-Instance `InductOne Field Change` ONLY where the map's "Spawns per-Instance FC" = **YES**:
   - FCO-2025-007 (EC-25-0223 MDR rollers, completed) → Field Change on Worldport units 3 (IN002024257003)
     and 4 (IN002024257004), as-maintained.
   - FCO-2025-010 (lights/OD retrofit, completed) → Field Change on units 7 (IN001024355007) & 8
     (IN001024355008).
3. **pending** rows (open FCOs 018/019/020): Request only; Field Change spawns on implementation.
   FCO-2026-019 references WP Primary-3 (pending-serial) — Request only, `machine_identifier` set, note.
4. Onexia references = **builder**, not location — record on the Request/Instance builder field, not as a site.

### Phase 5 — Register export + JotForm importer
1. Query Report / export `render_fco_register` producing the SUP-FCO-R01 v2.0 18-column contract from
   Field Change Request rows (joining spawned Field Change data for implemented/as-maintained/test/closed).
   Exportable to xlsx matching `SUP-FCO-R01_operating_backfilled.xlsx` columns/order. State that ERPNext is
   now the source of truth and the SharePoint file is a generated export.
2. JotForm importer (whitelisted method + UI trigger): ingests the JotForm export xlsx format, creates
   Requests, dedup-guarded by intake_ref. Operator pre-trims to new rows; importer stays idempotent.

## Validation gate (all PASS — these prove the integration coheres)
1. `python -m compileall inductone_tools scripts` clean; all fixtures parse; candidate migrate clean.
2. Location tree integrity: every seeded POR Physical Location resolves to a valid parent; Cells are
   leaves; `full_path` matches Site/Lane/Cell.
3. Every non-internal Instance has a non-null `physical_location` → Cell; `deployment_site` label == Cell
   `full_path` (sync proven).
4. Every backfilled Field Change resolves through its Instance to a Cell (no orphan FC).
5. Every `fco_instance_map` row represented: Request exists; mapped serial links to a real Instance (or
   is explicitly pending/organic); spawn/pending/organic handled exactly as the map says. Report counts.
6. As-installed query works: for a Site, list installed Instances + status + latest field change.
7. Reassignment mechanism: editing a Request's `instance` without a reason is rejected; with a reason,
   the change appears in the Version log; low-confidence rows appear in the monitor report.
8. External builders (motion.builder / lam) denied create/read on all new DocTypes (negative test).
9. No `ignore_permissions=True` introduced (grep clean).

## PENDING ADDITIONS — future simple Codex drop-in (documented trail)
These are known-incomplete and intentionally deferred. Each is a small, isolated addition later:

1. **Worldport Primary-3 cells 3-2 & 3-3** (fielded, commissioned Feb 2026; 3-2 built by **Onexia**).
   - Locations ALREADY seeded (`WP-C-3-2`, `WP-C-3-3` under Lane `WP-L-P3`).
   - Blocker: real IND serials + config unknown (not in the 10-unit tracker or GitLab issue titles).
   - Source to obtain: the Worldport project (`plusone-robotics/operations/project_manager/ups/worldport-inductone`,
     e.g. WI #170) or a Worldport-v2 config tracker if one exists.
   - **Drop-in:** add two rows to `instance_backfill_seed.xlsx` Instances sheet (serial, origin=Legacy
     backfill, status Installed/Shipped, physical_location = the seeded Cell, builder Onexia for 3-2),
     re-run Phase 2. FCO-2026-019 then links its Field Change to WP-C-3-2/3-3.
2. **CVG First Article** — a real fielded **UPS** unit (contractual as-built redlines "installed at UPS";
   FAT'd at CVG mid-2024). Likely an EXISTING UPS Instance (one of units 1–4), not a new one.
   - Blocker: serial/identity not in GitLab titles.
   - Source to obtain: CVG FAT checklist / commissioning SharePoint docs (linked in CVG First Article
     project issue #100), or owner confirmation.
   - **Drop-in:** once identified, either tag the existing Instance (add `first_article = 1` note /
     origin annotation) or, if it is genuinely a separate unit, add one row to the Instances sheet.
3. **FedEx Memphis Pilot** — no unit assigned yet (project shell only). Add when a serial exists.

## Report
Write `docs/workflows/inductone-as-installed-fco-erpnext-completion-2026-07-13.md`: gate table (each item
PASS/FAIL + evidence path under `C:\hub\frappe-sandbox\validation-evidence\`), DocType field lists as
built, backfill counts (locations, instances, FCO Requests, spawned Field Changes; pending/organic list),
register-export column mapping, files changed on the integration branch, and a final line exactly one of:
`CSA/FCO/ERPNEXT INTEGRATION CANDIDATE-READY: YES` or `… NO — <blockers>`.
