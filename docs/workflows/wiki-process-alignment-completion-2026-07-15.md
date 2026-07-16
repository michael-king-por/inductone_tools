# Wiki Process Alignment Completion — 2026-07-15

Scope: aligned the exact-name Wiki Page fixture to the ERPNext-defined process model from `docs/workflows/wiki-process-alignment-2026-07-15.md`.

Environment: candidate only (`inductone-candidate.localhost`). No production access, no push.

## Implementation summary

- Edited only `inductone_tools/fixtures/wiki_page.json` page content.
- Kept the exact-name Wiki fixture filter untouched.
- Preserved the released-doc placeholder count present in this repo state: 18 instances of `Pending released SharePoint link`.
- Corrected the four misaligned pages:
  - `configuration-options`
  - `engineering-signoff`
  - `bom-export-engineering-overview`
  - `roles-and-permissions`
- Corrected the six minor-alignment pages:
  - `inductone-build-pipeline`
  - `bom-generation-and-engineering-signoff`
  - `part-number-allocation-and-assignment`
  - `serialization-rules`
  - `as-built-records-and-instances`
  - `deviation-requests`
- Applied the two aligned-page polish notes:
  - `field-change-fco-register`: terminal status wording uses `Locked`.
  - `inductone-csa-quality-system`: part-number authority includes Engineering User, InductOne Process Architect, and System Manager.

## Process corrections encoded

- Configuration Option status model is `Draft / Released / Deprecated`; `Defined-Ops` and `Defined-Product` are removed.
- Configuration Options become build-usable only when Engineering Signoff approval releases them.
- Approver/allocator wording includes Engineering User, InductOne Process Architect, and System Manager.
- Builder-release signoff scope is top BOM, top Item, Product Bundle when present, and selected Configuration Options. It is not described as child-tree recursion or revision matching.
- `Direct BOM` wording is replaced with the implemented `Standard BOM` source mode.
- Fabricated role names were replaced with real roles: Operations Viewer, Operations Manager, InductOne External Builder, Inventory Operator, Gripper Manufacturer, Finance Viewer, and Procurement User.
- Deviation/FCO language now distinguishes procedural deviation handling from the ERPNext Field Change Request ledger and generated SUP-FCO-R01 export.

## Validation results

| Gate | Result | Evidence |
|---|---:|---|
| Local Wiki fixture validator | PASS | `python scripts/run_wiki_fixture_validation.py` → `PASS wiki fixture validation (16 pages)` |
| Candidate migrate | PASS | `bench --site inductone-candidate.localhost migrate` completed with after-migrate hooks and no error |
| Candidate exact fixture page count | PASS | 16 fixture-owned pages found |
| Candidate published/non-empty pages | PASS | 16 / 16 |
| Stale-term scan | PASS | 0 stale-term hits |
| Process Architect authority scan | PASS | Present on engineering-signoff, bom-generation, and part-number pages |
| Placeholder preservation | PASS | 18 placeholders preserved |

Candidate DB evidence:

`C:\hub\frappe-sandbox\validation-evidence\wiki_process_alignment_candidate_20260716T140651Z.json`

## Per-page results

| Route slug | Title | Result | Notes |
|---|---|---:|---|
| `part-number-allocation-and-assignment` | Part Number Allocation and Assignment | PASS | published=1, content_len=10792 |
| `bom-generation-and-engineering-signoff` | BOM Generation and Engineering Signoff | PASS | published=1, content_len=13647 |
| `roles-and-permissions` | Roles and Permissions | PASS | published=1, content_len=7545 |
| `inductone-csa-owner-handbook` | InductOne CSA Owner Handbook | PASS | published=1, content_len=9342 |
| `inductone-csa-quality-system` | InductOne CSA Quality System | PASS | published=1, content_len=5315 |
| `inductone-csa-controlled-records-index` | InductOne CSA Controlled Records Index | PASS | published=1, content_len=6806 |
| `configuration-options` | Configuration Options | PASS | published=1, content_len=13542 |
| `inductone-build-pipeline` | InductOne Build Pipeline | PASS | published=1, content_len=19964 |
| `serialization-rules` | Serialization Rules and Part Number Allocation | PASS | published=1, content_len=12545 |
| `deviation-requests` | Deviation Requests | PASS | published=1, content_len=6079 |
| `as-built-records-and-instances` | As-Built Records and Instances | PASS | published=1, content_len=18640 |
| `inductone-snapshot-diff-tool` | InductOne Snapshot Diff Tool | PASS | published=1, content_len=10990 |
| `bom-export-package` | BOM Export Package | PASS | published=1, content_len=12345 |
| `bom-export-engineering-overview` | BOM Export - Engineering Overview | PASS | published=1, content_len=16472 |
| `engineering-signoff` | Engineering Signoff | PASS | published=1, content_len=9200 |
| `field-change-fco-register` | Field Change (FCO) Register | PASS | published=1, content_len=2876 |

## Term-scan results

Fail terms checked case-insensitively:

- `Defined-Ops`
- `Defined-Product`
- `Direct BOM`
- signoff `Revoke`
- edit-`invalidat` claims
- `Operations — Read Only`
- `Operations — InductOne Operator`
- `Sales — PM`
- old `Builder` role-name patterns
- `in-ERPNext Deviation Request workflow`
- `in-ERPNext deviation workflow`
- `Deviation Request workflow`

Result: PASS — no fixture-owned candidate Wiki Page contains the stale terms/patterns.

Explicit follow-up check: `Deviation Request workflow` phrase hits = 0.

Required authority term checked:

- `InductOne Process Architect`

Result: PASS — present on the engineering-signoff, bom-generation, and part-number allocation pages.

WIKI PROCESS-ALIGNED: YES
