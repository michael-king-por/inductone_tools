# InductOne CSA/FCO/ERPNext completion report

Date completed in candidate: 2026-07-15

Branch: `main`

Candidate site: `inductone-candidate.localhost`

This report covers completion of gaps G1-G5 from
`docs/workflows/inductone-as-installed-fco-erpnext-build-2026-07-13.md`.
It is candidate-only evidence. No production writes, pushes, or tags were performed.

## Scope completed on 2026-07-15

| Gap | Result | Evidence |
|---|---|---|
| G1 — Customer-rooted POR Physical Location tree | PASS. `POR Physical Location.location_type` supports `Customer`; Sites are parented under Customer nodes; full paths start with Customer. Candidate Customer roots are `DHL`, `Plus One Robotics`, and `UPS`, derived from existing seeded location-row customer values. | `C:\hub\frappe-sandbox\validation-evidence\fco_customer_tree_view_20260715.png`; `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_validation.json` |
| G2 — Field Change list readability | PASS. `InductOne Field Change` and `InductOne Field Change Request` include read-only `location_label` and `customer`, with `instance`, `location_label`, `customer`, and `status` list-visible. | `C:\hub\frappe-sandbox\validation-evidence\fco_request_list_readability_wide_20260715.png`; `C:\hub\frappe-sandbox\validation-evidence\fco_field_change_list_readability_wide_20260715.png`; `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_validation.json` |
| G3 — Instance backfill sets canonical Cell link | PASS. `create_backfill_instance()` accepts and sets `physical_location` to the Cell record; `deployment_site` is derived from the Cell `full_path` and remains a fallback for pre-location units. | `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_backfill.json`; `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_validation.json` |
| G4 — Backfill execution proof | PASS. Candidate idempotent backfill confirmed 11 seeded Instances, 83 component serial rows, 19 FCO Requests, and 4 spawned Field Changes. | `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_backfill.json` |
| G5 — SUP-FCO-R01 export + JotForm importer | PASS. Validation confirmed the 18-column SUP-FCO-R01 v2.0 register contract and importer read path; importer read 19 rows and found all 19 existing. | `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_validation.json` |

## Build gate table

| # | Gate | Result | Evidence |
|---:|---|---|---|
| 1 | Python compiles, fixtures parse, candidate migrate clean | PASS | `C:\hub\frappe-sandbox\validation-evidence\fco_g1_g5_local_validation_20260715.txt`; candidate migrate log in terminal; `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_validation.json` |
| 2 | POR Physical Location tree integrity | PASS | `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_validation.json` |
| 3 | Seeded Instances linked to Cell physical locations | PASS | `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_validation.json` |
| 4 | Backfilled Field Changes resolve through Instance to Cell | PASS | `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_validation.json` |
| 5 | FCO map represented, with pending/organic exceptions preserved | PASS | `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_validation.json` |
| 6 | As-installed Site query returns installed fleet context | PASS | `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_validation.json` |
| 7 | Assignment correction requires reason and records Version trail | PASS | `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_validation.json` |
| 8 | External builders denied all new FCO DocTypes | PASS | `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_validation.json` |
| 9 | No `ignore_permissions=True` in new whitelisted methods | PASS | `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_validation.json` |
| 10 | Native Tree view renders Customer → Site → Lane → Cell | PASS | `C:\hub\frappe-sandbox\validation-evidence\fco_customer_tree_view_20260715.png`; `C:\hub\frappe-sandbox\validation-evidence\fco_browser_visual_evidence_20260715.json` |
| 11 | Field Change and Request lists show location/customer context | PASS | `C:\hub\frappe-sandbox\validation-evidence\fco_request_list_readability_wide_20260715.png`; `C:\hub\frappe-sandbox\validation-evidence\fco_field_change_list_readability_wide_20260715.png`; `C:\hub\frappe-sandbox\validation-evidence\fco_browser_visual_evidence_20260715.json` |

Note on list screenshots: at the default 1280px Desk width, Frappe hides later list columns in the
responsive grid, though the fields are present in filters and metadata. A wide Desk capture confirms
the actual list columns render as intended: Assigned Instance / Location / Customer / Status / ID.

## Backfill counts

Fresh candidate rerun evidence: `C:\hub\frappe-sandbox\validation-evidence\fco_as_installed_backfill.json`

| Area | Count / status |
|---|---|
| Required customers | `UPS`, `DHL`, `Amazon`, `Plus One Robotics` all present |
| Customer-root location nodes | `DHL`, `Plus One Robotics`, `UPS` |
| Location seed rows | 28 |
| Locations on idempotent rerun | 31 existing, 0 created in the rerun; includes 28 seeded rows + 3 Customer roots |
| Instance seed rows | 11 |
| Seeded Instances on idempotent rerun | 11 existing, 0 created |
| Instances with physical_location set | 11 seeded Instances validated |
| Component serial rows | 83 |
| FCO Requests | 19 represented, 19 existing on rerun |
| Spawned Field Changes | 4 existing: two for `FCO-2025-007`, two for `FCO-2025-010` |
| Pending serials intentionally skipped | `WP-P3-2`, `WP-P3-3` |

Pending / organic exceptions preserved:

- `FCO-2025-013`: map row has no serial; represented as Request context only.
- `FCO-2026-019`: organic / pending-serial Worldport Primary-3 context; Request only until real serials are designated.
- `WP-P3-2` and `WP-P3-3`: documented pending additions, not created as Instances.

## Candidate object and patch proof

- Patch registered and applied in candidate: `inductone_tools.patches.v2026_07_15_customer_rooted_fco_locations`.
- `POR Physical Location` native Tree view expands from Customer roots to Site, Lane, and Cell descendants.
- `InductOne Field Change Request` list shows `Title`, `Status`, `Assigned Instance`, `Location`, `Customer`, and `ID` when grid width permits.
- `InductOne Field Change` list shows `Instance`, `Status`, `Location`, `Customer`, and `ID`.
- `SUP-FCO-R01 Field Change Register` export returns the expected 18-column contract:
  `fco_number`, `date_raised`, `requester`, `intake_ref`, `customer_project`, `serial_or_location`,
  `change_summary`, `triage_outcome`, `reference`, `safety_regulatory`, `disposition`,
  `disposition_date`, `implemented_date`, `as_maintained_updated`, `post_change_test`, `status`,
  `closed_date`, `notes`.

## Files changed for G1-G5

- `inductone_tools/physical_location.py`
- `inductone_tools/field_change.py`
- `inductone_tools/guidance.py`
- `inductone_tools/instance/backfill.py`
- `inductone_tools/fixtures/doctype.json`
- `inductone_tools/patches.txt`
- `inductone_tools/patches/v2026_07_15_customer_rooted_fco_locations.py`
- `scripts/inductone_backfill/run_fco_as_installed_backfill.py`
- `scripts/inductone_backfill/run_fco_as_installed_validation.py`
- `docs/workflows/inductone-as-installed-fco-erpnext-build-2026-07-13.md`
- `docs/workflows/inductone-csa-fco-erpnext-completion-2026-07-13.md`
- `docs/deployment/production-deployment-checklist.md`
- `docs/security/hardening-progress-tracker.md`

CSA/FCO/ERPNEXT INTEGRATION CANDIDATE-READY: YES
