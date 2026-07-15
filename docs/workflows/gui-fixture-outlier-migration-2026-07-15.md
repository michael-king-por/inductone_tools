# GUI / Fixture Outlier Migration — 2026-07-15

This note records the candidate-tested migration tranche that moves high-risk GUI/database configuration into repo-owned code or narrow fixtures without touching operational records.

## Discovery

Discovery evidence:

- `C:\hub\frappe-sandbox\validation-evidence\fixture_outlier_discovery_20260715T032524Z.json`

The discovery scan found database-owned configuration still outside the repo fixture model:

| Area | Initial count | Decision |
|---|---:|---|
| Server Script | 4 | Migrate/retire now. Server Scripts are executable behavior and should not remain the source of truth. |
| Custom Field | 41 | Migrate confirmed app-owned deployable fields only; leave environment-local/business-policy fields for owner decision. |
| Print Format | 4 | Add the two Configuration Order / builder-release formats to the existing print-format fixture. |
| Report | 15 | Fixture-own app-owned active reports by exact name; list deprecated/stock/environment-local reports for owner sign-off. |
| Number Card | 10 | Add exact-name fixture ownership for app-owned Builder/Operations workspace cards. |
| Workspace | 12 | Existing filtered workspace fixture remains authoritative; Quality remains hidden/patch-managed. |
| Custom HTML Block | 14 | Existing filtered block fixture remains authoritative; owner-approved app UX blocks are promoted by exact name only. |

## Implemented changes

### POR Physical Location validation moved to app code

The active GUI Server Script `POR Physical Locations` is replaced by:

- `inductone_tools/physical_location.py`
- `doc_events["POR Physical Location"]["before_validate"]`

The migrated hook preserves the deployed script behavior:

- validates Site → Lane → Cell → Robot hierarchy;
- synchronizes type-specific code fields;
- computes `full_path`;
- enforces parent/customer consistency;
- preserves the old script's conditional robot-number behavior if a future schema adds `robot_number`.

Candidate evidence:

- `C:\hub\frappe-sandbox\validation-evidence\por_physical_location_app_hook_validation_20260715T033528Z.json`

Result: PASS. Scratch records were inserted inside a transaction and rolled back. Post-migration evidence confirms no scratch records remain.

### Legacy GUI Server Scripts retired

Patch:

- `inductone_tools.patches.v2026_07_15_retire_gui_server_scripts`

The patch disables these named scripts:

- `Builder Bom Permissions`;
- `POR Physical Locations`;
- `InductOne Configuration Option Validation/Gatekeep`;
- `POR-Generated-BOM-Snapshot`.

Rationale:

- `Builder Bom Permissions` references retired role `Builder`; raw Item/BOM denial is now app-owned in `external_builder_permissions.py`.
- `POR Physical Locations` is replaced by the Python hook above.
- The remaining two scripts were already disabled legacy/stub scripts; the patch keeps restored candidates self-cleaning.

Candidate evidence:

- `C:\hub\frappe-sandbox\validation-evidence\fixture_outlier_post_migration_20260715T033643Z.json`

Result: all four scripts are present but disabled.

### Missing `target_balloon` Custom Field fixture closed

Added fixture ownership for:

- `InductOne Configuration Option Mapping-target_balloon`

This closes the mismatch where repo documentation and validation expected both `target_balloon` fields to be fixture-managed, but the option-mapping field was still database-only.

Initial `custom_field.json` count changed:

- before: 7
- after: 8

Candidate parity evidence:

- `C:\hub\frappe-sandbox\validation-evidence\custom_field_fixture_parity_20260715T033340Z.json`

Result: 8 MATCH, 0 WOULD_CREATE, 0 WOULD_OVERWRITE, 0 UNMANAGED_ON_SITE for fixture-managed Custom Fields.

### Broader app-owned Custom Fields promoted

The deferred broader Custom Field tranche was re-opened and classified. Only app-owned deployable fields with code/fixture/workflow references were promoted.

Promoted fields:

| DocType | Field | Classification | Reason |
|---|---|---|---|
| `Item` | `custom_item_code_display` | app-owned deployable | Used by app-owned Part Number / Item UX. |
| `Item` | `custom_por_tab` | app-owned deployable | Layout anchor for app-owned POR Item metadata. |
| `Item` | `custom_part_number_control` | app-owned deployable | Used by app-owned part-numbering flow. |
| `Item` | `custom_part_number_assignment` | app-owned deployable | Used by app-owned part-numbering flow. |
| `Item` | `custom_controlled_number_family` | app-owned deployable | Used by app-owned part-numbering flow. |
| `Item` | `custom_gitlab_ec_url` | app-owned deployable | Used by Engineering Change / signoff metadata. |
| `Item` | `custom_gitlab_reference` | app-owned deployable | Used by Engineering Change / signoff metadata. |
| `Item` | `custom_part_number_release_status` | app-owned deployable | Used by app-owned part-numbering flow. |
| `Item` | `custom_source` | app-owned deployable | Used by configured BOM / flat BOM metadata. |
| `Product Bundle` | `custom_part_number_control` | app-owned deployable | Used by app-owned part-numbering flow. |
| `Product Bundle` | `custom_part_number_control_section` | app-owned deployable | Layout anchor for app-owned fields. |
| `Product Bundle` | `custom_part_number_assignment` | app-owned deployable | Used by app-owned part-numbering flow. |
| `Product Bundle` | `custom_gitlab_ec_url` | app-owned deployable | Used by Engineering Change / signoff metadata. |
| `Product Bundle` | `custom_gitlab_reference` | app-owned deployable | Used by Engineering Change / signoff metadata. |

`custom_field.json` final count:

- before this tranche: 8
- after this tranche: 22

Candidate parity evidence:

- `C:\hub\frappe-sandbox\validation-evidence\custom_field_fixture_parity_20260715T040235Z.json`

Result: 22 MATCH, 0 WOULD_CREATE, 0 WOULD_OVERWRITE, 0 UNMANAGED_ON_SITE for all fixture-managed Custom Fields.

Environment-local / owner-decision fields intentionally not promoted:

| DocType | Field(s) | Proposed classification | Owner decision required |
|---|---|---|---|
| `Item` | `custom_alternate_part_number`, `custom_engineering_note`, `custom_finish`, `custom_material`, `custom_optional_component`, `custom_related_mechanical_item`, `custom_revision`, `custom_section_break_vf2z8`, `custom_type` | Environment-local / engineering metadata until confirmed otherwise | Decide whether these are controlled POR app schema or site-local descriptive metadata. |
| `Sales Order` | `custom_approvalauthorization`, `custom_approval_from`, `custom_approved`, `custom_salesforce_opportunity_link`, `exempt_from_sales_tax` | Environment-local / commercial process | Decide whether these belong to InductOne Tools or remain site-local ERP/commercial configuration. |
| `BOM` | `custom_item_group`, `custom_item_group_secret`, `custom_item_name`, `custom_production_item_name` | Environment-local / reporting convenience | Decide whether these are deploy-critical app schema or local report/display helpers. |
| `InductOne Configuration Option` | `workflow_state` | Existing Frappe workflow residue | Leave unmanaged unless a future workflow implementation requires fixture ownership. |

### App-owned Report fixture extended

The report tranche classified the candidate database reports and promoted only app-owned active outliers.

Promoted:

| Report | Classification | Action |
|---|---|---|
| `Configured Snapshot Diff` | app-owned active | Added to exact-name `Report` fixture; roles normalized to current internal roles; retired `Builder` / `Manufacturing User` / `Operations Member` roles removed. |
| `Delivery Note by PO` | POR-wide finance report | Added to exact-name `Report` fixture under new module `Finance - POR`; roles normalized to `Finance Viewer`, `Operations Viewer`, `Operations Manager`, and `System Manager`. |

Already fixture-owned app reports retained:

- `Electrical Balloon Callouts`
- `FCO Assignments Pending Review`
- `SUP-FCO-R01 Field Change Register`

`report.json` count changed:

- before: 3
- after initial report tranche: 4
- after owner decision D2: 5

New module fixture:

- `Finance - POR` added to `modules.txt`;
- `inductone_tools/finance___por/__init__.py` added so `bench migrate` can import the module;
- `module_def.json` added with exact-name fixture ownership for `Finance - POR`.

Candidate evidence:

- classification source: `C:\hub\frappe-sandbox\validation-evidence\gui_fixture_outlier_classification_source_20260715T035358Z.json`
- fixture promotion export: `C:\hub\frappe-sandbox\validation-evidence\gui_fixture_outlier_promotion_export_20260715T035542Z.json`
- candidate report parity: `C:\hub\frappe-sandbox\validation-evidence\gui_fixture_outlier_post_migration_check_20260715T040329Z.json`

Result: all 5 fixture-managed reports match candidate after migrate. `Configured Snapshot Diff` and `Delivery Note by PO` have only current curated roles and no external-builder/raw-builder access.

Reports not promoted without owner sign-off:

| Report | Proposed classification | Reason / owner decision |
|---|---|---|
| `Flat BOM-Exploded` | deprecated / legacy InductOne report | Uses retired role vocabulary; owner should confirm retirement before deletion or fixture archival. |
| `InductOne v2.0 LH BOM Report` | deprecated / legacy InductOne report | Old BOM-report surface; likely superseded by current builder package / callout / snapshot tools. |
| `InductOne v2.0 LH BOM Report - 1611 027 0010-001` | deprecated / legacy InductOne report | Specific legacy variant; owner should confirm retirement. |
| `InductOne v2.0 RH BOM Report` | deprecated / legacy InductOne report | Old BOM-report surface; owner should confirm retirement. |
| `InductOne Configuration Options Report` | deprecated or owner-facing report | Uses old role vocabulary; likely superseded by options catalog/signoff views, but needs owner sign-off. |
| `Testing` | deprecated / local experiment | Name and roles indicate non-production report; owner should confirm deletion or archival. |
| `Gripper Creation Date` | environment-local / Gripper reporting | Not enough evidence to fixture as app-owned. |
| `Gripper Travels` | environment-local / Gripper reporting | Not enough evidence to fixture as app-owned. |

Stock/ERPNext reports remain database/app-standard and are intentionally not fixture-owned by InductOne Tools.

Scope note: `inductone_tools` is now treated as the POR-wide ERPNext customization layer. The controlled InductOne CSA scope remains the `Operations - POR` module plus the controlled CSA documents; POR-wide support fixtures such as `Finance - POR` reports are app-owned deployment configuration but not themselves part of the controlled CSA document set.

### Owner decision D1 — Custom HTML Blocks promoted

Owner ruling: promote `Branded Banner`, `Roll Callout cards`, `URL`, and `Whats New Banner` to fixture ownership by exact name because they are app UX for Operations/Engineering workspaces and Engineering Signoff/banner flows.

Implemented:

- added all four blocks to `custom_html_block.json`;
- added all four names to the exact-name `Custom HTML Block` fixture filter in `hooks.py`;
- scanned code/workspace references before promotion;
- normalized the `URL` block's hardcoded production URL to a site-relative `/app/query-report/...` URL before freezing it into a prod-bound fixture.

Reference / URL evidence:

- `C:\hub\frappe-sandbox\validation-evidence\custom_html_block_reference_scan_20260715.json`
- `C:\hub\frappe-sandbox\validation-evidence\gui_fixture_owner_decisions_post_migration_check_20260715.json`

Result: the four blocks exist after candidate migrate and none contains `plusonerobotics.v.frappe.cloud`, `inductone-candidate`, or `localhost:8000`.

### Owner decision D3 — environment-local Custom Fields classified

Owner ruling: promote environment-local Custom Fields only if app code references the fieldname.

Code scan evidence:

- `C:\hub\frappe-sandbox\validation-evidence\custom_field_owner_decision_code_reference_scan_20260715.json`

Decision:

| DocType | Field(s) | Code-reference result | Action |
|---|---|---|---|
| `Item` | `custom_alternate_part_number`, `custom_engineering_note`, `custom_finish`, `custom_material`, `custom_optional_component`, `custom_related_mechanical_item`, `custom_revision`, `custom_section_break_vf2z8`, `custom_type` | No app-code references | Leave DB-local; owner can keep/retire later. |
| `Sales Order` | `custom_approvalauthorization`, `custom_approval_from`, `custom_approved`, `custom_salesforce_opportunity_link`, `exempt_from_sales_tax` | No app-code references | Leave DB-local commercial/site configuration. |
| `BOM` | `custom_item_group`, `custom_item_group_secret`, `custom_item_name`, `custom_production_item_name` | No app-code references | Leave DB-local reporting/display helpers. |
| `InductOne Configuration Option` | `workflow_state` | Referenced only by legacy cleanup patch `v2026_07_08_configuration_option_status_model_cleanup` | Leave DB-local workflow residue; not active app schema. |

Validation:

- `C:\hub\frappe-sandbox\validation-evidence\custom_field_fixture_parity_20260715T151347Z.json`

Result: 22 MATCH, 0 WOULD_CREATE, 0 WOULD_OVERWRITE, 0 UNMANAGED_ON_SITE for all fixture-managed Custom Fields.

### Builder release print formats fixture-owned

Added exact-name fixture ownership for:

- `CO-ATTACHED-README`;
- `InductOne Configuration Order - Builder Release`.

`print_format.json` count changed:

- before: 2
- after: 4

Candidate evidence:

- `C:\hub\frappe-sandbox\validation-evidence\gui_fixture_outlier_candidate_validation_20260715T033339Z.json`
- `C:\hub\frappe-sandbox\validation-evidence\fixture_outlier_post_migration_20260715T033643Z.json`

Result: all four managed Print Formats exist after candidate migrate.

### Operations / Builder Number Cards fixture-owned

Added `number_card.json` with exact-name ownership for 10 app-owned dashboard cards.

Candidate evidence:

- `C:\hub\frappe-sandbox\validation-evidence\gui_fixture_outlier_candidate_validation_20260715T033339Z.json`
- `C:\hub\frappe-sandbox\validation-evidence\fixture_outlier_post_migration_20260715T033643Z.json`

Result: all 10 managed Number Cards exist after candidate migrate.

### Fixture Export Control converted to audit-only / sandbox-only

`inductone_tools/fixture_sync.py` is no longer a production source-of-truth path.

Implemented behavior:

- `audit_fixture_status()` is the normal whitelisted method and is available only to `System Manager` / `InductOne Process Architect`.
- `export_and_push_fixtures()` remains only as an explicit sandbox escape hatch.
- Export/push requires both:
  - `site_config` value `fixture_sync_mode = "sandbox_push"`;
  - a sandbox-like site name (`candidate`, `sandbox`, `localhost`, `dev`, or `test`).
- Without that explicit sandbox mode, the method throws before export/push.
- The `Fixture Export Control Script` now shows an `Audit Fixture Status` button and no longer calls `export_and_push_fixtures`.

Candidate evidence:

- `C:\hub\frappe-sandbox\validation-evidence\gui_fixture_outlier_post_migration_check_20260715T040329Z.json`

Result: audit succeeds; export/push is blocked by default with `ValidationError`.

## Candidate migration evidence

Candidate bench:

- `/home/michaelplusone/frappe-sandbox/benches/candidate-bench`
- site `inductone-candidate.localhost`

`bench --site inductone-candidate.localhost migrate` completed successfully and executed:

- `inductone_tools.patches.v2026_07_15_retire_gui_server_scripts`
- current fixture sync, including `Custom HTML Block`, `Report`, and `Module Def` updates from owner decisions D1/D2.

Validation:

- local compile: `python -m compileall inductone_tools scripts` → PASS;
- fixture parse: 17 JSON fixtures parse → PASS;
- Wiki fixture validation: `C:\hub\frappe-sandbox\validation-evidence\wiki_fixture_validation_gui_outlier_20260715T040245Z.json` → PASS;
- custom-field parity: `C:\hub\frappe-sandbox\validation-evidence\custom_field_fixture_parity_20260715T040235Z.json` → PASS;
- post-migration outlier check: `C:\hub\frappe-sandbox\validation-evidence\gui_fixture_outlier_post_migration_check_20260715T040329Z.json` → PASS.

Owner-decision validation:

- local compile + fixture parse: `C:\hub\frappe-sandbox\validation-evidence\gui_fixture_owner_decisions_local_compile_20260715.txt` → PASS;
- candidate migrate: `C:\hub\frappe-sandbox\validation-evidence\gui_fixture_owner_decisions_candidate_migrate_20260715.txt` → PASS;
- custom-field parity after owner decisions: `C:\hub\frappe-sandbox\validation-evidence\custom_field_fixture_parity_20260715T151347Z.json` → PASS;
- Wiki fixture validation after owner decisions: `C:\hub\frappe-sandbox\validation-evidence\wiki_fixture_validation_owner_decisions_20260715.json` → PASS;
- focused owner-decision post-migration check: `C:\hub\frappe-sandbox\validation-evidence\gui_fixture_owner_decisions_post_migration_check_20260715.json` → D1/D2/D3 PASS, D4 BLOCKED by coverage guard.

## Data-loss posture

This tranche does not fixture or mutate operational records:

- no Items;
- no BOMs;
- no Sales Orders;
- no InductOne Builds;
- no Configuration Orders;
- no Instances;
- no Field Change records;
- no Files.

Candidate POR Physical Location smoke records were rolled back. Evidence shows `scratch_records_remaining: []`.

## Owner-decision closeout

### Resolved items

| Decision | Outcome |
|---|---|
| D1 — Custom HTML Blocks | Resolved. `Branded Banner`, `Roll Callout cards`, `URL`, and `Whats New Banner` promoted by exact name. The `URL` block's absolute production URL was converted to a site-relative URL before fixture ownership. |
| D2 — Finance report `Delivery Note by PO` | Resolved. Promoted under new module `Finance - POR`, with `Module Def` fixture ownership and normalized roles. |
| D3 — environment-local Custom Fields | Resolved. App-code-reference scan found no active schema references requiring promotion; the fields remain DB-local and are listed above for future keep/retire review. |

### D4 — Wiki Space / sidebar blocked by coverage guard

Owner ruling was to promote the Wiki Space/sidebar only if every sidebar-referenced Wiki Page is already covered by the exact-name `Wiki Page` fixture. That coverage condition is not met.

Evidence:

- `C:\hub\frappe-sandbox\validation-evidence\wiki_space_sidebar_coverage_20260715.json`
- `C:\hub\frappe-sandbox\validation-evidence\gui_fixture_owner_decisions_post_migration_check_20260715.json`

Current coverage:

- fixture-managed Wiki Pages: 16;
- sidebar-referenced pages: 29;
- missing from exact-name fixture: 14.

Unmanaged sidebar-referenced pages blocking Wiki Space/sidebar fixture ownership:

| Sidebar idx | Parent label | Wiki Page | Title | Route |
|---:|---|---|---|---|
| 1 | Operations | `7nimh0h5dp` | Home | `plus-one-ops-manual/home` |
| 2 | Operations | `3hmbicd3dj` | Manufacturing Overview | `plus-one-ops-manual/manufacturing-overview` |
| 3 | Operations | `3hmf57baak` | BOM Structure and Search | `plus-one-ops-manual/bom-structure-and-search` |
| 12 | Engineering | `8ap3ou4ue5` | Engineering Overview | `plus-one-ops-manual/engineering-overview` |
| 14 | Inventory Management | `3hm09ttju2` | Inventory Overview | `plus-one-ops-manual/inventory-overview` |
| 15 | Inventory Management | `3hnu4bl7ha` | Stock Entry and Receiving | `plus-one-ops-manual/stock-entry-reconciliation` |
| 16 | Inventory Management | `av6d2fi262` | Removing Stock Due to Material Issues | `plus-one-ops-manual/removing-stock-from-inventory-due-to-material-issues` |
| 17 | Inventory Management | `4f5l6kl6qn` | Create a new Item (Non-Assembly) | `plus-one-ops-manual/create-a-new-item-non-assembly` |
| 18 | Inventory Management | `3hm142vrat` | Product Bundles | `plus-one-ops-manual/product-bundles-and-variants` |
| 20 | Inventory Management | `b6e81vnjp6` | Creating a Delivery Note ERP Next | `plus-one-ops-manual/creating-a-delivery-note-erp-next` |
| 21 | Inventory Management | `6i5cr3e84u` | Serialized Gripper Work Order Execution | `plus-one-ops-manual/creating-a-build-order` |
| 22 | Inventory Management | `0ff9pdeqru` | Serialized Gripper Refurbishment (Repack) Workflow | `plus-one-ops-manual/create-a-new-item-assembly` |
| 23 | Project Management | `1m8gis8g6h` | Sales Order Generation | `plus-one-ops-manual/project-management/sales-order-generation` |
| 25 | Administration & Governance | `3ho3qa4brn` | ERPNext Release Notes | `plus-one-ops-manual/erpnext-release-notes` |

Action taken: no `Wiki Space` fixture was added, and the additive Wiki Space link patch remains the safe current mechanism. To unblock D4 later, either add these 14 pages to the exact-name `Wiki Page` fixture after owner content review, or remove them from the sidebar before fixture-owning the space.

Final status:

`GUI/FIXTURE OUTLIER MIGRATION: BLOCKED — Wiki Space/sidebar fixture ownership blocked by 14 sidebar-referenced pages not covered by exact-name Wiki Page fixture`
