# Current Fixture Manifest

This manifest documents the current fixture state as of local repo commit `9c51500be775ffe669276dad385cfb6cc07bd197`.

The manifest is descriptive, not yet a final approval of every row. It is the starting point for fixture hardening.

## Fixture files

| File | Count | Purpose | Ownership concern |
|---|---:|---|---|
| `client_script.json` | 26 | Client-side ERPNext form/list behavior. | Current `hooks.py` exports all Client Scripts. Narrow to allowlist. |
| `doctype.json` | 31 | Custom DocType schema/configuration. | Spans `Operations - POR` and `InductOne Tools`; document ownership before restructuring. |
| `custom_docperm.json` | 12 | Permission rows for selected custom DocTypes. | Needs alignment with formal permission matrix. |
| `custom_field.json` | 8 | Deploy-critical Custom Fields, including BOM Item electrical metadata and balloon-scoped option fields. | Any addition can overwrite live Custom Field definitions on migrate; run fixture parity checks before deploy. |
| `property_setter.json` | 0 | No property setters currently exported. | Keep intentionally empty unless deploy-critical setters are added. |

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
| `Fixture Export Control Script` | Transitional fixture export UI. Should become audit-only or admin-only. |
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
- `Configured BOM Snapshot Structural Effect-target_balloon`.

The two `target_balloon` rows are required for balloon-scoped configuration options. They are optional Data fields inserted after `target_item`; empty value preserves legacy item-wide behavior.

## Immediate fixture hardening recommendations

1. Replace broad Client Script fixture export with an explicit allowlist.
2. Decide whether non-InductOne generic scripts (`minimal`, `Attachment_display`, `generate_zip`) belong to this app.
3. Decide whether `Fixture Export Control` remains repo-owned or becomes sandbox-only.
4. Generate a machine-readable fixture manifest and compare it against database state after migration.
5. Align `custom_docperm.json` with the permission matrix.

## Review rule

Before changing fixture filters, run a candidate sandbox migration and verify:

- every expected Client Script remains present,
- obsolete Client Scripts do not reappear,
- no operational records are exported,
- UI behavior is unchanged.
