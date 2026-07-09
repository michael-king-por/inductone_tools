# InductOne CSA usability and fixture hardening

Date: 2026-07-09  
Environment validated: candidate sandbox (`inductone-candidate.localhost`)  
Production touched: no  
Push performed: no

This note records the 2026-07-09 follow-up pass that made the InductOne CSA workflow more presentable, more self-explanatory, and more deployable without reintroducing GUI-only state.

## Deployment/source-of-truth boundaries

All changes in this pass were deliberately segmented into the deployment mechanism that owns them:

| Change area | Source of truth | Deployment path | Why it belongs there |
|---|---|---|---|
| Release-readiness server gate | Python code: `inductone_tools/builder_release.py` | App code + `bench migrate` / deploy | This is workflow behavior and must be enforced server-side, not by Desk UI hints. |
| Lifecycle/release validation | Repo scripts under `scripts/` | Run from candidate or production bench as explicit validation tooling | Validation must be repeatable and reviewable; evidence is written outside fixtures. |
| Build form guidance | `Client Script` fixture: `inductone_tools/fixtures/client_script.json` | Filtered fixture sync | Existing build UI logic already lives in the `InductOne Build HTML Controls` Client Script fixture; this keeps user-facing guidance versioned. |
| Owner handbook content | `Wiki Page` fixture: `inductone_tools/fixtures/wiki_page.json` | Filtered fixture sync | Only the explicitly managed owner handbook page is exported; the broader Wiki remains GUI-owned until reviewed. |
| Workflow diagrams | Static app assets under `inductone_tools/public/svg/` | App asset deployment | SVGs are code-reviewed, cacheable assets referenced by the Wiki; they are not stored as opaque Wiki blobs. |
| Wiki information architecture audit | `scripts/run_wiki_information_architecture_audit.py` | Read-only candidate audit | The audit reports unmanaged/stub/diagram-candidate pages without auto-mutating database-owned Wiki content. |

No broad fixture exports were introduced. The Wiki Page fixture remains filtered. The Client Script fixture remains the existing curated fixture. The new SVGs are app-static files, not database fixtures.

## Implemented changes

### 1. Broadened release-readiness gate

`check_builder_release_readiness()` now verifies the governed release inputs before a Build can be released:

- top BOM has approved Engineering Signoff,
- top Item has approved Engineering Signoff,
- Product Bundle records for the top Item have approved Engineering Signoff,
- every selected Configuration Option is both approved and `Released`.

Draft configuration options remain valid for ideation and iteration, but are explicitly not build-usable. The Engineering Signoff approval path is the release path for configuration options.

### 2. Candidate lifecycle smoke now exercises the real option release path

The lifecycle smoke was corrected so a stale state of “current signoff Approved but option still Draft” is not accepted as release-ready. In candidate, the script requests and approves a new signoff for Draft configuration options, allowing the normal `Draft -> Pending -> Approved -> Released` path to run.

Passing evidence:

- `C:\hub\frappe-sandbox\validation-evidence\inductone_csa_lifecycle_smoke_20260709T201934Z.json`

This evidence proves the full candidate CSA path:

Build clone → configured snapshot → hierarchy workbook → Configuration Order → BOM Export Package → release-gate signoffs → serial allocation → release to builder → builder acknowledgement → completion upload → internal review → accept completion → locked As-Built → Instance.

### 3. Negative release-gate matrix

Added `scripts/run_inductone_csa_release_gate_matrix.py` to prove release fails closed for high-risk gaps:

- selected Draft Configuration Option is reported by readiness,
- `release_to_builder_now()` refuses a selected Draft Configuration Option,
- missing top Item signoff is reported,
- missing Product Bundle signoff is reported.

Passing evidence:

- `C:\hub\frappe-sandbox\validation-evidence\inductone_csa_release_gate_matrix_20260709T201606Z.json`

### 4. Build-form usability panel

The fixture-managed `InductOne Build HTML Controls` Client Script now renders:

- a release-readiness checklist,
- direct links to the selected Snapshot, Configuration Order, BOM Export Package, Build Completion, As-Built Record, and Instance,
- clearer next-action cues for internal operators.

Local JavaScript syntax validation passed after extracting the updated script and running `node --check`.

### 5. Versioned SVG operating maps

Added four app-owned SVGs:

- `inductone_tools/public/svg/inductone-csa-master-workflow.svg`
- `inductone_tools/public/svg/configuration-option-status-gate.svg`
- `inductone_tools/public/svg/builder-package-composition.svg`
- `inductone_tools/public/svg/as-built-instance-lineage.svg`

These are referenced by the fixture-managed owner handbook through `/assets/inductone_tools/svg/...`.

### 6. Wiki information architecture audit

Added `scripts/run_wiki_information_architecture_audit.py` as a read-only audit. It enumerates Wiki Pages, compares them to the filtered Wiki fixture allowlist, and flags pages that are likely stubs, long pages with no SVG, long pages with weak heading structure, or pages carrying possible legacy builder language.

Evidence:

- `C:\hub\frappe-sandbox\validation-evidence\wiki_information_architecture_audit_20260709T201432Z.json`

Summary from candidate:

- total Wiki Pages: 38
- fixture-managed pages: 4
- database-managed pages: 34
- stub/redirect-sized pages: 11
- long pages without SVG: 22
- long pages without Markdown headings: 7

This audit did not auto-fix database-managed pages. Those remain owner-review work.

## Validation performed

| Validation | Result |
|---|---|
| `python -m compileall inductone_tools scripts` | PASS |
| Fixture JSON parse | PASS |
| SVG XML parse | PASS |
| Updated Build Client Script `node --check` | PASS |
| Candidate migrate with fixture/SVG/code changes | PASS |
| Candidate lifecycle smoke with strict release gate | PASS |
| Candidate release-gate negative matrix | PASS |
| Candidate Wiki IA audit | PASS / review findings produced |

## Remaining owner-review items

These are not blockers to the code/fixture hardening pass, but they are the next visible polish items:

1. Review the Wiki IA audit and decide which database-managed Wiki pages should be fixture-managed, rewritten, hidden, or left GUI-owned.
2. Decide whether the Builder Portal should receive a dedicated stripped-down landing page beyond the current Desk route controls.
3. Review the new release gate against production source data before deploy. The stricter gate is intentionally safer, but it will block any build whose Item, Product Bundle, BOM, or selected Configuration Option signoffs are incomplete.
4. Package the SVGs and evidence into the final ownership handoff packet.

