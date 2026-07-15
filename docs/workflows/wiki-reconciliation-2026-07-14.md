# Wiki reconciliation — 2026-07-14

Scope: reconcile the exact-name ERPNext `Wiki Page` fixture to the owner-confirmed InductOne CSA controlled set. Candidate-only validation was performed against `inductone-candidate.localhost`; production was not touched.

## Owner-confirmed control decisions encoded

| Decision | Result |
|---|---|
| Controlled set is 15 artifacts: 12 docs + 3 registers (`OPS-SER-R01`, `OPS-CFG-M01`, `SUP-FCO-R01`) | PASS |
| `OPS-CFG-R01`, `OPS-CSA-CCB-01`, `OPS-FCO-R01`, and `WI-OPS-GRP-001` are retired / archived, never active | PASS |
| `OPS-CFG-PNA-01 Part Number Allocation Procedure` added to the governed CSA set | PASS |
| `InductOne Manager` and `InductOne Process Architect` are active roles | PASS |
| `OPS-BLD-F01`, `OPS-FCO-T01`, and `OPS-FCO-T02` are content specifications, not fill-in templates | PASS |
| `OPS-CSA-AUD-01` is commissioning acceptance + quarterly ERPNext records/desk audit + opportunistic field re-verification | PASS |
| `SUP-FCO-R01` operating instance location is known | PASS — `SharePoint › TechnicalOperations › Field Deployment Resources › General › FCO (Field Change Orders) › FCO_Index.xlsx` |

## Per-page reconciliation

| Page | Fixture name | Required update | Result |
|---|---|---|---|
| Part Number Allocation and Assignment | `9n8bvqedso` | Added `OPS-CFG-PNA-01`; lifecycle corrected to `Reserved → In Development → Released`; `Cancelled` / `Superseded` documented as terminal; `Custom` added as fifth number family | PASS |
| Roles and Permissions | `3hnmdg9m5q` | Removed stale deprecation warning for `InductOne Manager` and `InductOne Process Architect`; added policy note that both are active modular roles | PASS |
| InductOne CSA Owner Handbook | `inductone-csa-owner-handbook` | Replaced CI Index language with `OPS-SER-R01`; added `OPS-CFG-PNA-01` and `OPS-CSA-OVW-01`; changed FCO template language to content specifications + `SUP-FCO-R01`; inserted known operating-register location | PASS |
| InductOne CSA Quality System | `inductone-csa-quality-system` | Removed `OPS-CFG-R01` from active configuration model; added PNA row; audit row rewritten to the three-tier model | PASS |
| InductOne CSA Controlled Records Index | `inductone-csa-controlled-records-index` | Removed active `OPS-CFG-R01` and `WI-OPS-GRP-001` rows; added `OPS-CFG-PNA-01`; reclassified F01/T01/T02 as Content Specification; added retired/superseded note; inserted known `SUP-FCO-R01` operating location | PASS |
| Serialization Rules and Part Number Allocation | `3hmiq2lbi9` | Added `OPS-CFG-PNA-01` to part-number conventions and source alignment; documented go-forward and legacy numbering behavior | PASS |
| Deviation Requests | `3hngf036ne` | Inserted known `SUP-FCO-R01` operating-register location | PASS |
| Field Change (FCO) Register | `inductone-field-change-fco-register` | Inserted known `SUP-FCO-R01` operating-register location | PASS |

## Local fixture validation

Command:

```powershell
python scripts/run_wiki_fixture_validation.py
```

Result:

```text
PASS wiki fixture validation (16 pages)
```

Extended term scan:

| Check | Result |
|---|---|
| 16 Wiki Page fixture rows | PASS |
| Hooks exact-name fixture ownership preserved | PASS |
| Stale roles-page deprecation warning gone | PASS |
| `OPS-CFG-PNA-01` present on pages 00/03/04/05/08 | PASS |
| `CI Index` phrase absent | PASS |
| `quarterly physical` phrase absent | PASS |
| `OPS-CFG-R01` appears only in retired/superseded note | PASS |
| `WI-OPS-GRP-001` appears only in archived/retired note | PASS |
| Old `SUP-FCO-R01` “to be designated” operating-location language absent | PASS |
| F01/T01/T02 classified as Content Specification | PASS |

Release-link placeholder note: the fixture currently contains 17 active `Pending released SharePoint link` placeholders after removing retired active rows and adding `OPS-CFG-PNA-01`. The `SUP-FCO-R01` operating-instance path was added separately and does not consume the future released-document placeholder.

## Candidate validation

Candidate app commit at validation: `d8556f6`.

Command:

```bash
cd /home/michaelplusone/frappe-sandbox/benches/candidate-bench
/home/michaelplusone/.venvs/frappe-bench/bin/bench --site inductone-candidate.localhost migrate
```

Result: migrate completed cleanly; Wiki search index rebuilds were queued; `after_migrate` completed.

Candidate DB verification:

| Check | Result |
|---|---|
| 16 fixture-owned Wiki Pages present | PASS |
| 16/16 pages published | PASS |
| 16/16 pages non-empty | PASS |
| `OPS-CFG-PNA-01` present on required pages | PASS |
| Stale roles-page deprecation warning absent | PASS |
| `CI Index`, `quarterly physical`, and old `to be designated` language absent | PASS |
| Active release-link placeholder count after reconciliation | 17 |

## Files changed

| File | Purpose |
|---|---|
| `inductone_tools/fixtures/wiki_page.json` | Exact-name fixture update for the controlled CSA Wiki pages |
| `docs/workflows/wiki-reconciliation-2026-07-14.md` | This reconciliation and validation report |

WIKI RECONCILED: YES
