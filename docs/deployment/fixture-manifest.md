# Current Fixture Manifest

This manifest documents the current fixture state as of local repo commit `9c51500be775ffe669276dad385cfb6cc07bd197`.

The manifest is descriptive, not yet a final approval of every row. It is the starting point for fixture hardening.

## Fixture files

| File | Count | Purpose | Ownership concern |
|---|---:|---|---|
| `client_script.json` | 32 | Client-side ERPNext form/list behavior, including the narrow usability guidance scripts. | Current `hooks.py` uses an explicit Client Script name allowlist. Keep it narrow. |
| `custom_html_block.json` | 14 | App-owned Workspace banner and guidance blocks, including owner-approved Operations/Engineering UX blocks. | Filtered by exact block name. Do not bulk-export unrelated Custom HTML Blocks; convert environment-specific URLs to relative/config-driven URLs before fixture ownership. |
| `doctype.json` | 34 | Custom DocType schema/configuration. | Spans `Operations - POR` and `InductOne Tools`; document ownership before restructuring. |
| `custom_docperm.json` | 275 | Permission rows for selected managed DocTypes. | Needs alignment with formal permission matrix and replace-trap review before adding first rows to any standard DocType. |
| `custom_field.json` | 22 | Deploy-critical Custom Fields, including BOM Item metadata/user notes, both balloon-scoped option fields, and app-owned Item/Product Bundle part-numbering metadata. | Any addition can overwrite live Custom Field definitions on migrate; run fixture parity checks before deploy. |
| `inductone_configuration_option.json` | 13 | Reviewed `DEV-*` balloon-scoped option catalog. | Scoped by `option_code like DEV-%`; future operational/non-DEV options must not be swept into version control accidentally. |
| `property_setter.json` | 0 | No property setters currently exported. | Keep intentionally empty unless deploy-critical setters are added. |
| `report.json` | 5 | App-owned Electrical Balloon Callouts, FCO assignment/register reports, Configured Snapshot Diff, and POR finance support report `Delivery Note by PO`. | Keep report role access aligned with curated role model; do not bulk-export generic ERPNext reports. |
| `module_def.json` | 1 | App-owned `Finance - POR` module for POR finance support customization. | Module package must exist in app code before migrate; module ownership does not expand controlled InductOne CSA scope. |
| `print_format.json` | 4 | App-owned options catalog and Configuration Order/builder release print formats. | Print format HTML can overwrite live templates; parity-review before adding records. |
| `number_card.json` | 10 | App-owned Operations/Builder workspace count cards. | Exact-name scoped; do not bulk-export dashboards/cards. |
| `role.json` | 10 | App-owned curated role vocabulary. | Do not fixture user assignments. |
| `role_profile.json` | 10 | App-owned curated role profiles. | Production user-to-role assignment remains database/user-governance work. |
| `wiki_page.json` | 16 | Explicitly allowlisted Wiki pages, including the CSA owner handbook, CSA quality-system map, controlled records index, FCO register, and updated InductOne workflow pages. | Do not bulk-export the Wiki; owner-review pages before fixture-managing them. |
| `workspace.json` | 11 | Explicitly allowlisted Operations, Engineering, Builder Portal, and standard public workspaces whose role rows are managed so external builders see Builder Portal only. | Re-run workspace visibility audit after changes. |
| `module_onboarding.json` | 1 | Builder first-run onboarding sequence. | Filtered to `InductOne External Builder Onboarding`. |
| `onboarding_step.json` | 4 | Builder onboarding steps. | Filtered to the four explicit builder steps. |

Scope note: `inductone_tools` is the POR-wide ERPNext customization layer. The controlled InductOne CSA scope remains the `Operations - POR` module plus the controlled CSA documents; support fixtures such as `Finance - POR` are app-owned deployment configuration, not controlled CSA records.

## Client Script rows

Current local fixture rows:

| Client Script | Target DocType / purpose |
|---|---|
| `minimal` | Needs review; name is not self-documenting. |
| `Attachment_display` | Needs review; attachment display behavior. |
| `generate_zip` | Needs review; generated zip behavior. |
| `InductOne Selection Prevention` | InductOne Configuration Option mapping guard. |
| `Sales Order Build Button` | Sales Order to InductOne Build creation entry point. |
| `Load Catalog Options - Enforce Group-of Exclusivity` | Build option loading/group exclusivity UX. |
| `InductOne Configuration Export Package` | Configuration Order/BOM export package UI. |
| `InductOne As-Built Record Script` | As-Built form behavior. |
| `Options Catalog Print Button` | Options Catalog print/export UX. |
| `InductOne Build Script` | Main InductOne Build form behavior. |
| `InductOne Build Completion Script` | Build Completion review/accept/reject UX. |
| `Fixture Export Control Script` | Audit-only fixture status UI. Production GUI export/push is disabled; sandbox export requires explicit site config. |
| `InductOne List Formatting` | Build list formatting. |
| `InductOne Build HTML Controls` | Build form visual/HTML controls. |
| `InductOne Build Supplier Population` | Build supplier population helper. |
| `Engineering Signoff Actions` | Engineering Signoff UI actions. |
| `BOM Engineering Signoff Banner` | BOM signoff banner. |
| `Product Bundle Engineering Signoff Banner` | Product Bundle signoff banner. |
| `InductOne Instance Script` | Instance form behavior. |
| `Part Number Allocation Request - Allocate Numbers Button` | Part number allocation UI. |
| `Item Part Number Integration` | Item part number behavior. |
| `Product Bundle Part Number Allocation Script` | Product Bundle part number behavior. |
| `InductOne Configuration Option styling` | Configuration Option visual styling. |
| `Engineering Signoff Banner - Item` | Item signoff banner. |
| `Engineering Signoff Banner - Configuration Option` | Configuration Option signoff banner. |
| `InductOne Configuration Option Review Button` | Configuration Option review action. |
| `InductOne Guidance - Configuration Order` | Shared in-form guidance for Configuration Orders. |
| `InductOne Guidance - Build Completion` | Shared in-form guidance for Build Completions. |
| `InductOne Guidance - Operations Build` | Shared in-form guidance for InductOne Builds. |
| `InductOne Guidance - Engineering Signoff` | Shared in-form guidance for Engineering Signoffs. |
| `InductOne Guidance - Configuration Option` | Shared in-form guidance for Configuration Options. |

Notably absent from current local fixtures:

- `InductOne Completion Script`

Only `InductOne Build Completion Script` remains for the Build Completion DocType.

## DocType fixture rows

Current local `doctype.json` rows:

| DocType | Category |
|---|---|
| InductOne Instance | Operational/support object |
| InductOne Builder Tranche | Serial allocation control |
| Configured BOM Snapshot | Configured BOM evidence |
| Configured BOM Snapshot Item | Child table |
| BOM Export Package | Builder package/export object |
| BOM Export Package Item | Child table |
| InductOne Configuration Option | Configuration catalog |
| InductOne Configuration Option Mapping | Child table |
| InductOne Build | Primary build object |
| InductOne Build Option Selection | Child table |
| InductOne Build Execution Log | Child table/log |
| POR Physical Location | POR location support object |
| InductOne Build Completion | Builder completion evidence |
| InductOne Build Completion Serial | Child table |
| InductOne As-Built Record | Locked accepted evidence |
| InductOne As-Built Serial | Child table |
| InductOne Configuration Order Delta Line | Child table |
| InductOne Configuration Order Document Index | Child table |
| InductOne Configuration Order | Operational order |
| Configured BOM Snapshot Structural Effect | Snapshot support object |
| InductOne Configuration Order Selected Option | Child table |
| InductOne Options Catalog | Options catalog print/display object |
| Fixture Export Control | Transitional admin/audit object |
| POR Controlled Document | Controlled-document support |
| Engineering Signoff | Engineering signoff object |
| Part Number Assignment | Part number control |
| Part Number Allocation Request Line | Child table |
| Allocation Result | Child table/result |
| Part Number Allocation Request | Part number request object |
| InductOne Instance Serial | Child table |
| Configured BOM Snapshot Hierarchy | Snapshot hierarchy support |

## Custom Field fixture rows

`custom_field.json` now includes:

- six `BOM Item` electrical/user-note fields;
- `InductOne Configuration Option Mapping-target_balloon`;
- `Configured BOM Snapshot Structural Effect-target_balloon`;
- nine app-owned `Item` part-numbering / engineering metadata fields;
- five app-owned `Product Bundle` part-numbering / engineering metadata fields.

The two `target_balloon` rows are required for balloon-scoped configuration options. They are optional Data fields inserted after `target_item`; empty value preserves legacy item-wide behavior.

`scripts/run_custom_field_fixture_parity_check.py` validates all fixture-managed Custom Fields by default. The expected hardened result is all managed fields as `MATCH`, with 0 `WOULD_CREATE`, 0 `WOULD_OVERWRITE`, and 0 `UNMANAGED_ON_SITE`.

Fields intentionally not fixture-managed remain owner-decision/environment-local until classified in `docs/workflows/gui-fixture-outlier-migration-2026-07-15.md`.

## Report fixture rows

`report.json` is intentionally filtered by exact name in `hooks.py`. The managed rows are:

- `Electrical Balloon Callouts`
- `FCO Assignments Pending Review`
- `SUP-FCO-R01 Field Change Register`
- `Configured Snapshot Diff`
- `Delivery Note by PO`

`Configured Snapshot Diff` is app-owned active and carries only current internal roles. `Delivery Note by PO` is POR-wide finance support under module `Finance - POR`, with curated internal read roles. Legacy `Builder`, `Manufacturing User`, and `Operations Member` role rows are not part of the fixture.

## Print Format fixture rows

`print_format.json` is intentionally filtered by exact name in `hooks.py`. The managed rows are:

- `InductOne Options Catalog`
- `InductOne Options Catalog - Comprehensive`
- `CO-ATTACHED-README`
- `InductOne Configuration Order - Builder Release`

The two Configuration Order formats are builder-release artifacts. They are repo-owned so a restored candidate or production migrate cannot lose the release packet presentation layer.

## Number Card fixture rows

`number_card.json` is intentionally filtered by exact name in `hooks.py`. The managed rows are:

- `Builder - Awaiting Acknowledgement`
- `Builder - Completed`
- `Builder - In Progress`
- `Builder - Submitted`
- `InductOne - Accepted`
- `InductOne - Configuring`
- `InductOne - Needs Review`
- `InductOne — At builder`
- `InductOne — Awaiting ack`
- `InductOne — Ready to release`

These cards support the fixture-managed Builder Portal and Operations workspace dashboards.

## Server Script migration status

The repository does not fixture Server Scripts. The 2026-07-15 GUI outlier migration moved the only active app-owned Server Script behavior into Python code and disables the legacy database scripts via patch `inductone_tools.patches.v2026_07_15_retire_gui_server_scripts`:

- `POR Physical Locations` is replaced by `inductone_tools.physical_location.validate_por_physical_location` wired through `doc_events`.
- `Builder Bom Permissions` is stale because it references the retired generic `Builder` role; raw Item/BOM denial for suppliers is app-owned in `external_builder_permissions.py`.
- `InductOne Configuration Option Validation/Gatekeep` and `POR-Generated-BOM-Snapshot` remain disabled legacy/stub scripts.

## InductOne Configuration Option fixture rows

`inductone_configuration_option.json` is intentionally scoped in `hooks.py`:

```python
{
    "dt": "InductOne Configuration Option",
    "filters": [["option_code", "like", "DEV-%"]]
}
```

The fixture contains exactly the 13 reviewed `DEV-*` options for the balloon-scoped electrical cable feature. Child `InductOne Configuration Option Mapping` rows are exported as part of each parent option document; the child DocType is not exported as a separate record fixture.

The options are exported at `status = "Draft"` so they are reproducible on migrate and can enter the Engineering Signoff flow. They are not loadable on builds until a governed Engineering Signoff approval promotes them to `Released`.

## Wiki Page fixture rows

`wiki_page.json` is intentionally filtered by exact page name in `hooks.py`. It is not a broad Wiki export.

The current fixture includes the InductOne CSA owner handbook, the CSA quality-system page, the controlled records index, and selected InductOne workflow pages that now contain CSA/source-alignment guidance. These pages reference app-owned SVG diagrams from `/assets/inductone_tools/svg/...`; the SVGs themselves live under `inductone_tools/public/svg/` and are deployed as static app assets rather than database content.

Public Wiki rendering is not controlled by the `Wiki Page` record alone. The Wiki app also requires
the page to appear in the owning `Wiki Space.wiki_sidebars` child table. The full Wiki Space/sidebar
is intentionally not fixture-managed here because it contains broader navigation outside this tranche.
Patch `inductone_tools.patches.v2026_07_13_wiki_csa_space_links` appends only these app-owned CSA
entry pages to the existing `plus-one-ops-manual` space:

- `inductone-csa-owner-handbook`
- `inductone-csa-quality-system`
- `inductone-csa-controlled-records-index`

Broader non-InductOne Wiki content is still database-managed until the owner reviews it. Use `scripts/run_wiki_information_architecture_audit.py` to identify stub pages, diagram candidates, and pages that may deserve fixture ownership.

## Static SVG app assets

Current app-owned workflow diagrams:

- `inductone_tools/public/svg/inductone-csa-master-workflow.svg`
- `inductone_tools/public/svg/configuration-option-status-gate.svg`
- `inductone_tools/public/svg/builder-package-composition.svg`
- `inductone_tools/public/svg/as-built-instance-lineage.svg`
- `inductone_tools/public/svg/inductone-csa-quality-system-map.svg`

## Wiki fixture validation

Run `scripts/run_wiki_fixture_validation.py` before deployment. It verifies that `wiki_page.json` parses, page names/routes are unique, the `hooks.py` exact-name filter matches the fixture rows, required CSA Wiki pages and SVG assets exist, SVG references resolve, and legacy role names are absent.

## Custom HTML Block fixture rows

`custom_html_block.json` is intentionally filtered by exact name in `hooks.py`. The managed rows are:

- `Builder Banner`
- `Builder Guidance Panel`
- `Help and contact`
- `Operations Banner`
- `Operations Guidance Panel`
- `Engineering Banner`
- `Engineering Banner Info`
- `Engineering Banner Workflows`
- `Engineering Banner Reference`
- `Engineering Banner Resources`
- `Branded Banner`
- `Roll Callout cards`
- `URL`
- `Whats New Banner`

These blocks back the fixture-managed Workspaces. The Builder Portal panel is dynamic: its script calls `inductone_tools.guidance.get_builder_portal_guidance`, which uses the logged-in user's normal permissions.

The `URL` block was normalized to use a site-relative `/app/query-report/...` link before fixture ownership. Do not fixture hardcoded candidate or production hostnames in Custom HTML Blocks.

## Module Onboarding fixture rows

The builder onboarding fixture is exact-name scoped:

- `InductOne External Builder Onboarding`
- `Receive an InductOne Build`
- `Download the release package`
- `Upload the builder serial workbook`
- `Respond to a rejected Build Completion`

## Immediate fixture hardening recommendations

1. Decide whether non-InductOne generic scripts (`minimal`, `Attachment_display`, `generate_zip`) belong to this app.
2. Keep Custom HTML Block ownership exact-name scoped; any future block with environment-specific URLs must be converted to relative/config-driven links before promotion.
3. Do not fixture-manage Wiki Space/sidebar until every sidebar-referenced Wiki Page is already covered by the exact-name `Wiki Page` fixture, or intentionally removed from the sidebar.
4. Align `custom_docperm.json` with the permission matrix.
5. Review Wiki IA audit findings before adding any more Wiki pages to fixtures.

## Review rule

Before changing fixture filters, run a candidate sandbox migration and verify:

- every expected Client Script remains present,
- obsolete Client Scripts do not reappear,
- no operational records are exported,
- UI behavior is unchanged.
