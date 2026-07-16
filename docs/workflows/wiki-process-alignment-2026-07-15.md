# Wiki Process Alignment — Codex Build Spec

**Date:** 2026-07-15  **Executor:** Codex (candidate only)  **Branch:** the existing wiki/guidance integration branch

Align the 16 InductOne CSA wiki pages in `inductone_tools/fixtures/wiki_page.json` to **what ERPNext
actually has defined and controlled** — the DocType field definitions in `fixtures/doctype.json` and the
whitelisted Python (`engineering_signoff.py`, `part_numbering.py`, `field_change.py`, `builder_release.py`,
`bom_export.py`). This audit was done against the live code; every fix below cites its evidence.

## Operating rules
1. Candidate only. Do not push, do not deploy to production. Human reviews and merges.
2. Edit `wiki_page.json` content only. Keep the exact-name Wiki fixture filter untouched; keep the released-doc
   "Pending released SharePoint link" placeholders.
3. **Describe the process by what the DocTypes/methods do — do not reintroduce brittle links to specific
   controlled documents.** Owner's directive: rely on ERPNext-defined process, not doc links.
4. Where a page already states the correct model in one section and the wrong model in another, align the whole
   page to the correct one (several pages have a correct intro/footer and a stale middle).

## Cross-cutting corrections (apply wherever they appear)
- **Option statuses:** the only real Config Option statuses are **Draft / Released / Deprecated**
  (`doctype.json:9320`; `Defined-Ops`/`Defined-Product` were retired by
  `patches/v2026_07_08_configuration_option_status_model_cleanup.py`). Remove every mention of Defined-Ops /
  Defined-Product.
- **Approver/allocator roles:** wherever a page names who can approve signoffs or allocate part numbers, it must
  include **InductOne Process Architect** (and System Manager), not just Engineering User
  (`engineering_signoff.py:683-689`, `part_numbering.py:43-53`).
- **Release gate scope:** the builder-release signoff gate checks the **top BOM + top Item + any Product Bundle +
  each selected Configuration Option** (must be Released and approved). There is **no child-BOM tree recursion**
  and **no `target_revision_id` matching** (`builder_release.py:1382-1465`).
- **Governance:** change control is ECR → ECO → ECN. No CCB, no ECB. (Already clean on most pages; verify none reintroduce it.)

## MISALIGNED — must fix

### configuration-options
- Replace the 5-row lifecycle table (Draft / Defined-Product / Defined-Ops / Released / Deprecated) with the **three
  real statuses**. Only **Released** is build-usable; Draft is not.
- Release path = Draft → (mapping_status must be **Complete**) → request Engineering Signoff → **approval flips
  Draft→Released and locks the option**. Manual Draft→Released is blocked (`engineering_signoff.py` on_target_save
  Guard 2). `mapping_status` is a **hard pre-approval gate**, not merely a "manual completeness flag."
- Catalog-load filter is **`status = Released` only** (`client_script.json:65`) — remove "Defined-Ops or Released."
- Deprecation is via **Supersede** (`supersede_config_option` clones a new Draft and marks the original Deprecated);
  Released options are immutable. Remove "set `is_active=0` and status to Deprecated" by hand.
- Role gate: Engineering User / InductOne Process Architect / System Manager.
- The page's own "Policy of record" intro band and "CSA source alignment" footer are already correct — align the body to them.

### engineering-signoff  (worst page)
- **Scope:** signoff applies to **BOM, Product Bundle, Item, and InductOne Configuration Option**
  (`engineering_signoff.py:5-10`). Delete "does not apply to Items" (false — Item auto-signs off on insert and is
  release-gated). Reconcile the body with the footer.
- **Trigger:** a Pending signoff is auto-created on **`after_insert`** of a new BOM/Item/Product Bundle (not
  `before_save`, not on later saves). For a Configuration Option the signoff is **requested manually**
  (`request_signoff`) and only while Draft.
- **Delete the invented "invalidate-on-edit" model** and the "What counts as a signoff-invalidating change" section —
  the code explicitly does NOT invalidate on edit (`engineering_signoff.py:419-421`). The real model is
  "a new record is a new signoff."
- **Delete the "Revoke" feature** — no such method exists.
- **Fix the release-gate section** per the cross-cutting rule (top BOM + Item + Bundle + selected Options; no child
  recursion; no revision match).
- **Add a Configuration Option section:** manual request while Draft → approval = release (Draft→Released + lock);
  `mapping_status = Complete` gate; supersede to revise.
- Add **InductOne Process Architect** (and System Manager) to the "who can approve" statement.
- Lifecycle table: add the **Superseded** signoff status (`doctype.json:27668`).

### bom-export-engineering-overview
- Replace every **"Direct BOM"** with **"Standard BOM"**. `source_mode` has exactly two values —
  `Standard BOM` and `Configured Build` (`doctype.json:5765`; `bom_export.py` default `"Standard BOM"`).
  "Direct BOM" exists nowhere in code; an engineer following the page looks for a dropdown value that isn't there.

### roles-and-permissions
- Replace fabricated role names with the real ones from `role.json` / `custom_docperm.json`:
  `Operations — Read Only` → **Operations Viewer**; the read/write operator role → **Operations Manager**;
  `Builder` → **InductOne External Builder**. `Sales — PM` has no backing role — remove it or reconcile to the real
  role Sales users actually hold.
- Fix the **User → Role Assignments** table to real role/role-profile names (it is currently unassignable).
- Add the real roles the page omits where relevant (Operations Manager, Inventory Operator, Gripper Manufacturer,
  Finance Viewer, Procurement User).
- Correct the **InductOne External Builder** scope: `custom_docperm.json` grants it exactly **InductOne Build
  Completion + InductOne Configuration Order**, Builder-Portal-only, and **no Field Change access**.
- Fix "five role categories" vs the seven rows shown.
- **Keep** the active-role handling as-is — InductOne Manager / InductOne Process Architect are already correctly
  marked active with the "do not treat as retired" note. The 2026-07-14 ruling is satisfied; only the taxonomy names
  are wrong.

## MINOR — accuracy fixes

### inductone-build-pipeline
- Replace "Released or Defined-Ops" (two places: Prerequisites and Stage 2) with **Released** only.
- CO Status Lifecycle table: add the **Cancelled** `co_status` value (`doctype.json:21976`).

### bom-generation-and-engineering-signoff
- Fix the "deep recursive walk of the entire configured BOM tree / every child BOM" overclaim per the cross-cutting
  release-gate rule (top BOM only, plus Item/Bundle/Options).
- Drop the "editing a Product Bundle invalidates its signoff" claim — Product Bundle has only `after_insert` +
  `validate` hooks (`hooks.py:30-33`); nothing re-requests or invalidates on edit.
- Add **InductOne Process Architect** to the signoff-role list.

### part-number-allocation-and-assignment
- Lifecycle summary table: add the **In Development** row (the prose already has it) and ideally Cancelled/Superseded
  (`part_numbering.py:26-32`).
- Step 5: change "Submission triggers the Engineering Signoff hook" to "**Saving** the new BOM record triggers" it
  (`after_insert`, not submit).
- Legacy framing: drop the "any item numbered below `2000475` is legacy" test — the sequence is a **shared global
  suffix with a family prefix**, so a legitimate Part is `1000xxx` (below 2000475 but not legacy). Frame legacy as
  "predates the allocation process / manual or Custom assignments."
- Add **InductOne Process Architect** to allocation authority.

### serialization-rules
- Add that **5G / ConnectOne is a configuration option and is NOT serialized** (state it as a register convention
  per OPS-SER-R01, not code-enforced).
- Optional: enumerate the component prefixes (IPC `POR####`, HMI `HMI-####`, OD `OD-####` ×5, grippers
  `ICC-U/ICC-L`, robots Fanuc F#, RealSense vendor S/N) — deferring to OPS-SER-R01. (Page already correctly uses
  ICC not GRP, `IND-####`, the five families, and legacy preservation.)

### as-built-records-and-instances
- Location tree is **Customer → Site → Lane → Cell → Robot** (`location_type` options `doctype.json:15898`), and
  `Instance.physical_location` is an **unfiltered** Link — Cell-level is a convention, not enforced. Correct the
  "Site → Lane → Cell" phrasing and the "linked to a Cell" implication.
- `deployment_site` is **read-only**, `fetch_from = physical_location.full_path` (`doctype.json:1645/1681`).
  Operations sets **Physical Location** (the link); Deployment Site auto-derives. Fix the "fields filled in by
  Operations" table, which currently lists Deployment Site as a manual free-text entry and omits Physical Location.
- Soften "the system creates one InductOne Field Change per affected Instance" — there is **no** Request→Field Change
  auto-creation. A Field Change is created (importer/operator), then `accept_field_change` locks it and updates the
  Instance (`field_change.py:180-218`).

### deviation-requests
- Remove the "**in-ERPNext Deviation Request workflow**" claim (appears twice) — there is no Deviation DocType or
  workflow. Deviation is governed by the **procedure** (OPS-CFG-DEV-01) plus a **`triage_outcome` label**; the
  importer only routes ECR / Field Change (`field_change.py:454-457`).
- Reconcile the upper "Field-side intake flow" step ("Register accepted FCO/deviation intake in SUP-FCO-R01" as a
  hand-kept register) with the ERPNext-ledger model: `InductOne Field Change Request` is the ledger; **SUP-FCO-R01 is
  a generated export** (`field_change.py:277`).

## ALIGNED — leave as-is (tiny polish only)
- **inductone-snapshot-diff-tool** — accurate; no change.
- **bom-export-package** — accurate (`source_mode` default `Configured Build` correct); no change.
- **inductone-csa-controlled-records-index** — accurate; register-as-generated-export and the retired list (CI Index
  consolidated into OPS-SER-R01, no CCB) are correct.
- **field-change-fco-register** — accurate. Polish: the terminal status value is **`Locked`** (there is no
  "Accepted" status; acceptance = `accepted_by`/`accepted_at` + the Locked state) — use "Locked" if the page says
  "Accepted."
- **inductone-csa-owner-handbook** — accurate; Field Change treated as built, governance correct.
- **inductone-csa-quality-system** — accurate. Polish: the part-number authority row should credit **InductOne
  Process Architect** (and System Manager) alongside Engineering User.

## Validation gate (all PASS)
1. `run_wiki_fixture_validation.py` passes; candidate migrate clean; all 16 pages published and non-empty.
2. Term scan **fails** if any page still contains: `Defined-Ops`, `Defined-Product`, `Direct BOM`, a signoff
   "Revoke", an edit-"invalidat"-ion claim, `Operations — Read Only`, `Operations — InductOne Operator`, `Sales — PM`,
   a `Builder` role name (as opposed to InductOne External Builder), or an "in-ERPNext deviation … workflow."
3. Term scan **confirms** `InductOne Process Architect` now appears in the engineering-signoff, bom-generation, and
   part-number pages' approver/allocator lists.
4. Exact-name fixture filter and the released-doc link placeholders untouched.
5. Report to `docs/workflows/wiki-process-alignment-completion-2026-07-15.md`: per-page PASS/FAIL + the term-scan
   result; final line exactly one of `WIKI PROCESS-ALIGNED: YES` or `… NO — <blockers>`.

## Not a wiki fix — flag for Engineering (owner decision)
- The Config Option Mapping `action` Select carries a spurious 5th value `REPLACE_TARGET_NODE` (`doctype.json:10266`)
  alongside the real four (ADD / REMOVE / REPLACE / QTY_OVERRIDE). The wiki's "Four Actions" is cleaner than the
  fixture. This is a DocType/fixture cleanup, not a wiki edit — do NOT change it as part of this wiki pass.
