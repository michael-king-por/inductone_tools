# Wiki + guidance integration report — 2026-07-13

Branch: `integration/wiki-guidance-2026-07-13`

This tranche reintegrates the builder-first usability guidance work with the CSA Wiki overhaul and encodes the owner policy decisions of record from 2026-07-13.

## Merge and fixture reconciliation

Merged branch `usability-guidance-tranche` into the integration branch. Conflicts were limited to:

| File | Resolution |
|---|---|
| `docs/deployment/fixture-manifest.md` | Union resolution. Preserved the 15-page CSA Wiki fixture boundary, added onboarding fixtures, and updated `workspace.json` to 11 rows because external-builder workspace isolation now deliberately manages the role rows for standard public workspaces. |
| `inductone_tools/patches.txt` | Union resolution. Preserved `v2026_07_13_release_options_with_approved_signoffs`, `v2026_07_13_wiki_csa_space_links`, and added `v2026_07_13_external_builder_workspace_isolation`. |

No merge conflict occurred in `engineering_signoff.py`; the approved-signoff release semantics from main were preserved.

## Policy encoding

| Policy | Page / artifact | Inserted policy text |
|---|---|---|
| P1 — released-only option visibility | `InductOne CSA Owner Handbook`; `Configuration Options` | “Policy of record: Catalog and print views show Released options by default. Draft and Deprecated options are reachable only through explicit filters for engineering and owner review; Draft options are not usable in released build workflows and are promoted to Released only through the Engineering Signoff gate.” |
| P2 — scratch-build validation snapshots | `InductOne CSA Owner Handbook`; validation scripts | “Validation snapshots are generated on scratch builds only; a real Build's snapshot history is a clean audit trail.” |
| P3 — external-builder sidebar | `Workspace` fixture; `v2026_07_13_external_builder_workspace_isolation` | External builders see `Builder Portal` only. Standard public workspaces are role-restricted to internal roles so supplier accounts are not shown links to pages they cannot use. |
| P4 — two-step acceptance gate | `InductOne CSA Owner Handbook`; `As-Built Records and Instances` | “Reviewed = data check (uploaded workbook parses; serial rows complete and well-formed). Accepted = evidence check (ops verifies serial/label evidence against the returned workbook and confirms configuration match); acceptance creates the locked As-Built Record + InductOne Instance.” No reviewer/acceptor dual-control constraint is introduced. |

## W7 — FCO intake integration

Owner ground-truth correction encoded 2026-07-13:

- The canonical FCO register file is now `Registers/SUP-FCO-R01_FCORegister-v2-0.xlsx`.
- `SUP-FCO-R01_FCORegister-v2-0.xlsx` releases as the controlled schema template.
- The operating FCO register is a separate controlled record instance at the owner-designated location.
- Until the owner designates that location, the controlled records index keeps the explicit placeholder: `Operating instance location: to be designated`.
- The released-link placeholder remains untouched as `Pending released SharePoint link`.

The field-side intake flow is encoded separately from the in-ERPNext Deviation Request workflow:

1. POR Field Change / Deviation intake form (JotForm) is submitted.
2. Operations Engineering triages the intake.
3. One-time post-shipment field change → FCO using `OPS-FCO-T01` or `OPS-FCO-T02`.
4. Pre-delivery departure → deviation under `OPS-CFG-DEV-01`.
5. Repeated cross-site condition or baseline-impacting issue → ECR through the Engineering Change process.
6. Accepted intake is registered in `SUP-FCO-R01`.
7. Disposition is recorded, the approved action is implemented, any required ERPNext as-maintained update is completed, and the item is closed in the register.

W4 gate addition: the controlled records index row for `SUP-FCO-R01` must show the v2-0 filename, must identify the file as a register template rather than the operating register instance, must retain `Operating instance location: to be designated`, and must keep the placeholder released link unchanged until the released SharePoint location exists.

## External-builder workspace visibility

Candidate pre-fix evidence: `C:\hub\frappe-sandbox\validation-evidence\builder_workspace_visibility_before_20260713.json`

| User | Before | After |
|---|---|---|
| `motion.builder@plusonerobotics.com` | `Builder Portal`, `Financial Reports`, `Home`, `Manufacturing`, `Payables`, `Receivables`, `Selling`, `Stock`, `Welcome Workspace` | `Builder Portal` only |
| `lam@plusonerobotics.com` | `Builder Portal`, `Financial Reports`, `Home`, `Manufacturing`, `Payables`, `Receivables`, `Selling`, `Stock`, `Welcome Workspace` | `Builder Portal` only |

Post-fix evidence:

- `C:\hub\frappe-sandbox\validation-evidence\workspace_visibility_audit_20260713T164319Z.json`
- `C:\hub\frappe-sandbox\validation-evidence\gui-smoke-builder-workspace-w6-20260713-rerun\gui-smoke-results.json` — 40/40 browser route checks passed for Motion and LAM with screenshots.

Internal-role regression evidence:

- `C:\hub\frappe-sandbox\validation-evidence\gui-smoke-internal-workspace-w6-20260713-rerun\gui-smoke-results.json` — 16/16 browser checks passed for internal personas.

## Wiki Space rendering fix

Candidate showed 14/15 fixture-managed Wiki pages attached to Wiki Space route `plus-one-ops-manual`; `Deviation Requests` was missing, which can produce `Wiki Page doesn't have a Wiki Space associated with it`.

Patch `v2026_07_13_wiki_csa_space_links` now asserts all 15 fixture-managed Wiki pages into the existing Wiki Space child table without fixture-managing the whole sidebar.

Candidate verification:

- All 15 fixture-managed pages linked to Wiki Space.
- `http://inductone-candidate.localhost:8000/plus-one-ops-manual/deviation-requests` returned HTTP 200.
- `http://inductone-candidate.localhost:8000/plus-one-ops-manual/inductone-csa-owner-handbook` returned HTTP 200.

## Validation results

| Gate | Result | Evidence |
|---|---|---|
| Python compile | PASS | `python -m compileall inductone_tools scripts` |
| Fixture JSON parse | PASS | 14 fixture JSON files parsed; `workspace.json` now has 11 rows; `wiki_page.json` has 15 rows. |
| Wiki fixture validation | PASS | `C:\hub\frappe-sandbox\validation-evidence\wiki_fixture_validation_20260713_w6.json` |
| CSA term/corpus scan | PASS | No `ECB`, `Ethan`, `Landefeld`, `Change Control Board`, superseded register/procedure names, or retired CSA file names remain; the only `OPS-FCO-R01` occurrence is the allowed “OPS-FCO-R01 is retired” canonical note. |
| SVG repair validation | PASS | SVG XML parsed; root `width`/`height` removed from the five responsive Wiki SVGs. |
| Candidate migrate | PASS | Candidate migrated after clearing stale candidate-only Role Profile queue locks. |
| Workspace visibility audit | PASS | `workspace_visibility_audit_20260713T164319Z.json`; `orphaned=0`, `external_builder_leaks=0`. |
| Usability guidance validation | PASS | `usability_guidance_validation_20260713T164319Z.json`; includes P1/P2/P4 policy text, scratch-build policy, builder-only workspace visibility, status-gated Configuration Orders, and builder guidance payload checks. |
| External-builder browser route smoke | PASS | `gui-smoke-builder-workspace-w6-20260713-rerun`; 40/40 checks passed with screenshots. |
| Internal browser route smoke | PASS | `gui-smoke-internal-workspace-w6-20260713-rerun`; 16/16 checks passed with screenshots. |

W7 validation evidence:

- `C:\hub\frappe-sandbox\validation-evidence\wiki_fixture_validation_20260713_w7.json`
- `C:\hub\frappe-sandbox\validation-evidence\usability_guidance_validation_20260713_w7.json`
- `C:\hub\frappe-sandbox\validation-evidence\wiki_w7_candidate_db_assertions_20260713.json`

## Notes

- Candidate-only test passwords were reset for the browser-smoke personas before GUI validation.
- The first candidate migrate after fixture edits hit stale Role Profile document locks from prior fixture import queue actions. These were candidate-only filesystem locks for the 10 curated Role Profile docs; removing those locks allowed migrate to complete cleanly.
- The in-app browser control plugin failed to initialize in this session, so GUI smoke used a temporary local Playwright install under `C:\hub\.tmp-playwright-smoke` with the installed Chrome executable. No repo files were written there.

INTEGRATION DEPLOY-READY: YES
