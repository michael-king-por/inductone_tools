# Downstream Permission-Loss Triage & Gameplan — 2026-06-29

## Purpose

After the role overhaul, a baseline↔candidate effective-permission diff produced
~10,135 user/doctype/capability "losses." This document triages that signal,
records two structural findings that change how the fix must be applied, states
exactly what was implemented, and gives the validated gameplan + reversal for the
remainder. It is the defensible record for this round.

Evidence files (validation-evidence folder):
- `effective_permission_regression_diff_20260629T162316Z.json`
- `static_link_dependency_audit_20260629T162008Z.json`
- `workspace_visibility_audit_20260629T161943Z.json`
- `unmanaged_link_desk_probe_before_stock_entry_type_fix_20260629T193631Z.json`
- `unmanaged_link_desk_probe_after_stock_entry_type_inventory_operator_fix_20260629T194243Z.json`
- `stock_entry_type_standard_role_read_before_20260629T193654Z.json`
- `stock_entry_type_standard_role_read_after_20260629T193823Z.json`
- `candidate_production_role_assignment_sync_20260629T194005Z.json`
- `static_link_dependency_audit_20260629T194323Z.json`
- `effective_permission_regression_diff_20260629T194445Z.json`

## Finding 1 — the 10,135 losses are three buckets, not one list

| Bucket | ~Count | Meaning | Action |
|---|---:|---|---|
| A — Intended downgrades | ~9,000 | Power users (Super / Stock / Accounts / Sales Manager sprawl) cut to one focused role. Lost `Production Plan`, `Routing`, `Workstation`, `Asset*`, `Bank*`, `Payroll`, etc. | Not regressions. Validate by **executing the user's real job**, not by reading the loss list. |
| B — Contaminated rows | ~792 | The diff's candidate user→role assignments do **not** match production. E.g. diff `austin.dominguez` still has `Operations Member, Sales Manager, Manufacturing Manager`; production `austin` is `Operations Viewer` only. The rows measure *Builder removal from old roles*, not the real downgrade. | **Invalid until the diff candidate is synced to production.** Re-run, then re-read. |
| C — Real link-read gaps | 28 (static audit) | A role can write a DocType but cannot read a DocType it links to (same class as the Finance/Matt regression). | Validated and largely fixed below. |

**The 10,135 number is not a to-do list.** Bucket A is the hardening working as
designed; Bucket B is a measurement artifact; only Bucket C is actionable, and
Bucket C is 28 items — which collapse further below.

## Finding 2 — the Custom DocPerm "replace" trap

In Frappe, if **any** `Custom DocPerm` row exists for a DocType, the framework
ignores **all** of that DocType's standard `DocPerm` rows and uses only the
custom set. Therefore adding the *first* Custom DocPerm row to a DocType that is
not already fixture-managed silently strips standard access for **every other
role** (including System Manager) on that DocType.

Of the Bucket C link targets:

- **Managed already** (safe to append a row): `Item`, `BOM`, `Sales Order`,
  `Supplier`, `Price List`, `Currency`.
- **Unmanaged** (adding a row = regression): `Country`, `Stock Entry Type`, `User`.

## Finding 3 — effective permission is the union of a user's roles

The static audit flags a role in isolation. Real access is the union of all roles
a user holds. Intersecting the 28 findings with the **actual production role
assignments** collapses them sharply:

| Audit finding | Live? | Why |
|---|---|---|
| InductOne Manager/Architect → Item, BOM, Sales Order, Supplier (8) | **No** | Every holder (christina, david.brain, david.moreno, jim, michael) also holds Operations Manager, which already grants these reads. |
| Inventory Operator → Price List, Stock Entry Type | **No** | No user currently holds Inventory Operator. |
| Procurement User → Currency | **Yes** (matthew.mcmillan) | Currency is **managed** → safe to fix now. |
| Operations Manager → Country, Stock Entry Type | **Yes** (7 ops users) | Both **unmanaged** → replace-trap. |
| Gripper Manufacturer → Stock Entry Type | **Yes** (nathaniel) | Same fix as Operations Manager → Stock Entry Type. |
| Procurement User → Country | **Yes** (matthew) | **Unmanaged** → replace-trap. |
| Engineering User / InductOne Manager → User | **Cosmetic** | `User` link is a display field (`reserved_by` / `generated_by`); link save validates existence, not read. Not workflow-blocking. |

## Implemented this round (safe, repo-local, zero regression)

Managed-DocType link-read grants added to the fixture generator
(`scripts/update_operational_role_docperms.py`) and to an idempotent patch
(`inductone_tools/patches/v2026_06_29_link_dependency_read_grants.py`,
registered in `patches.txt`):

- InductOne Manager → read `Item`, `BOM`, `Sales Order`, `Supplier`
- InductOne Process Architect → read `Item`, `BOM`, `Sales Order`, `Supplier`
- Procurement User → read `Currency` (live fix for matthew.mcmillan)
- Inventory Operator → read `Price List` (role-correctness; no current holder)

These are **read-only**, additive rows on already-managed DocTypes. Both the
generator and the patch carry a guard that **refuses** to write to an unmanaged
DocType, making the replace-trap impossible by construction.

Fixture: 242 → 252 rows (+10), 252 unique keys, 0 duplicates. `compileall` clean.
Verified post-generation that `Country`, `Stock Entry Type`, and `User` remain
absent from the fixture.

Rationale for the InductOne grants (not currently live): a role should be
self-sufficient for the records its own DocTypes link to, rather than depending on
always being paired with Operations Manager. Adds no access to any current user.

## Open — unmanaged live gaps (decision + candidate validation required)

These cannot be fixed by appending a fixture row (replace-trap) and must be
confirmed in the **candidate desk UI**, not by API smoke. API `insert()` does not
check link read, which is why the prior transaction smoke passed; a human using
the form still needs read to populate the link dropdown.

1. **`Stock Entry Type`** (Operations Manager, Gripper Manufacturer) — likely a
   real GUI blocker: the mandatory `stock_entry_type` dropdown on Stock Entry
   needs read to populate.
2. **`Country`** (Operations Manager, Procurement User) — `country` link on
   Address; confirm whether standard perms already grant broad read before acting.
3. **`User`** (Engineering User, InductOne Manager) — cosmetic display only;
   recommended **accept as-is** (do not grant), to avoid converting a sensitive,
   high-traffic DocType into fixture-managed state.

### Candidate validation steps (run on candidate bench, not production)

```bash
# As an Operations Manager user, confirm the desk blocker for Stock Entry Type:
bench --site inductone-candidate.localhost execute frappe.set_user --args "['<ops_manager_user>']"
# In the desk UI: New Stock Entry -> is the Stock Entry Type dropdown empty?
# As a Procurement user: New Address -> is the Country dropdown empty?
# Open a Part Number Assignment -> does reserved_by show the email (acceptable) or error?
```

### If `Stock Entry Type` / `Country` are confirmed blocking — least-invasive remedy

Do **not** add a bare Custom DocPerm row. Instead **snapshot-manage** only that
one DocType: read its full standard `DocPerm` set on the candidate, write all of
those rows plus the new curated role into the fixture, so no existing role loses
access. This adds at most two stable master DocTypes to fixture management — the
minimum necessary, and complete by construction.

```python
# Candidate: snapshot the standard perm set so nothing is dropped when it becomes managed
import frappe, json
for dt in ["Stock Entry Type", "Country"]:
    perms = frappe.get_all("DocPerm", filters={"parent": dt},
        fields=["role","permlevel","read","write","create","submit","cancel","amend",
                "delete","report","export","import","share","print","email","select"])
    print(dt, json.dumps(perms, indent=1))
```

The snapshot feeds a follow-up generator block + patch (same guard pattern) that
writes the complete set. Validate by GUI execution before committing.

## Candidate resolution — unmanaged trio Desk probe (2026-06-29)

Candidate Desk link-picker validation used `scripts/run_unmanaged_link_desk_probe.py`,
which calls Frappe's Desk link search path as the target users. This deliberately
tests the UI/link-picker permission seam rather than raw Python `insert()`, since
raw insert does not prove link dropdown usability.

| Link target | Persona / role | Result before fix | Resolution |
|---|---|---|---|
| `Stock Entry Type` | `patty.gomez@plusonerobotics.com` / Operations Manager | **Blocked** — Desk search raised `PermissionError` | Fixed |
| `Stock Entry Type` | `nathaniel.pantuso@plusonerobotics.com` / Operations Manager + Gripper Manufacturer | **Blocked** — Desk search raised `PermissionError` | Fixed |
| `Stock Entry Type` | `candidate.inventory.operator@example.invalid` / Inventory Operator | Static audit proved same Stock Entry dependency; no production holder today | Fixed to keep the curated transaction role assignment-safe |
| `Country` | `matthew.mcmillan@plusonerobotics.com` / Procurement User | **Not blocked** — Desk search returned 249 rows via standard `All` read | No grant; remains unmanaged |
| `User` | `shaun.edwards@plusonerobotics.com` / Engineering User | **Not blocked** — Desk search returned rows; field is display/cosmetic | No grant; remains unmanaged |

Only `Stock Entry Type` was snapshot-managed. The generator now writes the full
standard DocPerm set for `System Manager`, `Manufacturing Manager`, `Stock Manager`,
and `Stock User` before adding read-only rows for `Operations Manager`,
`Inventory Operator`, and `Gripper Manufacturer`. Matching patch:
`inductone_tools.patches.v2026_06_29_snapshot_stock_entry_type_permissions`.

Fixture: 252 → 259 rows (+7), 259 unique keys, 0 duplicates.

Regression proof: before snapshot-management, strict candidate users holding only
`System Manager`, `Manufacturing Manager`, `Stock Manager`, or `Stock User` all had
read access to `Stock Entry Type`. After snapshot-management, all four still had
read access, and the three curated transaction roles also had read access. Evidence:
`stock_entry_type_standard_role_read_before_20260629T193654Z.json` and
`stock_entry_type_standard_role_read_after_20260629T193823Z.json`.

Post-fix static link audit: `Stock Entry Type` is no longer flagged. Remaining
static findings are:

- `Country` from `Address.country` for Operations Manager / Procurement User:
  role-isolation artifact; Desk search is not blocked because standard `All` read
  applies, and the DocType remains unmanaged.
- `User` display links from InductOne/Engineering DocTypes: accepted as cosmetic;
  not recommended to snapshot-manage the sensitive/high-traffic `User` DocType.

Candidate assignment decontamination: `scripts/sync_candidate_production_role_assignments.py`
set candidate users to the verified production role map, disabled
`alyza.salinas@plusonerobotics.com` and `quickbooks.integration@plusonerobotics.com`,
and left `hana.macinnis@plusonerobotics.com` unchanged for owner decision. Evidence:
`candidate_production_role_assignment_sync_20260629T194005Z.json`.

Effective permission diff after decontamination:

- Missing candidate users: 0.
- Expected disabled users: 2 (`alyza.salinas`, `quickbooks.integration`).
- Expected external-builder raw `Item`/`BOM` losses: 14.
- Remaining loss rows: 11,927 across 26 users. These remain owner-review signal,
  not automatic grants. The shape is dominated by Bucket A intended power-sprawl
  downgrades from broad profiles/manager roles to focused roles; `hana.macinnis`
  remains explicitly undecided and must be classified by the owner.

Quality workspace finding: `Workspace` `Quality` is public but role-restricted to
retired `Builder`. It links to standard quality records such as Quality Goal,
Quality Procedure, Quality Feedback, Quality Meeting, Non Conformance, Quality
Review, and Quality Action. Recommended owner decision: if this workspace is still
used internally, replace `Builder` with internal roles appropriate to quality
review (`Operations Manager`, `Operations Viewer`, and optionally `Engineering User`
for read visibility). No change has been made.

## Still pending (separate task — needs candidate)

- **Bucket B fix:** sync the regression-diff candidate's user→role assignments to
  the true production state, then re-run
  `scripts/run_effective_permission_regression_diff.py`. The ~792 Bucket B losses
  should collapse toward zero. Until then the full diff is **not** a clean
  sign-off — only the static link audit and execution smokes are trustworthy.
- **Workspace audit follow-up:** `Quality` workspace is still restricted to the
  retired `Builder` role (orphaned). Owner decision needed on its intended roles.

## Reversal

Nothing here is committed or pushed yet.

- **Repo (drop everything):**
  `git restore --staged --worktree scripts/update_operational_role_docperms.py inductone_tools/fixtures/custom_docperm.json inductone_tools/patches.txt && git rm -f inductone_tools/patches/v2026_06_29_link_dependency_read_grants.py`
- **If the patch has already run on a site (surgical undo — managed DocTypes
  only, so standard perms are untouched):**

  ```python
  import frappe
  for role, dts in {
      "InductOne Manager": ["Item","BOM","Sales Order","Supplier"],
      "InductOne Process Architect": ["Item","BOM","Sales Order","Supplier"],
      "Procurement User": ["Currency"],
      "Inventory Operator": ["Price List"],
  }.items():
      for dt in dts:
          frappe.db.delete("Custom DocPerm", {"parent": dt, "role": role, "permlevel": 0})
  frappe.clear_cache()
  frappe.db.commit()
  ```

  Because every target is an already-managed DocType, deleting only these rows
  leaves the rest of each DocType's custom permission set intact — no other role
  is affected. Full fallback remains the Phase 1 production backup restore.
