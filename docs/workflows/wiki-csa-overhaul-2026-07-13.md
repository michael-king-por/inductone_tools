# Wiki CSA overhaul — 2026-07-13

This tranche expands the ERPNext Wiki from role/workflow help into a governed CSA operating layer.

The goal is not to paste controlled documents into the Wiki verbatim. The Wiki explains how the released CSA system is operated in ERPNext, indexes the controlled source documents, and provides a stable place to add final SharePoint links after the CSA documents are released through Engineering Change.

## Source corpus

Source folder inspected:

`C:\Users\MichaelKing\OneDrive - Plus One Robotics\Documents\PlusOne\Production Engineer\Operations Engineering\ERP_Inventory_Migration\Phase Alternate - InductOne Configuration and Status Accounting\Quality-System`

Extraction evidence:

- `C:\hub\frappe-sandbox\validation-evidence\quality_system_file_list_powershell_20260713.txt`
- `C:\hub\frappe-sandbox\validation-evidence\quality_system_corpus_inventory_shortpath_20260713T151625Z.json`
- `C:\hub\frappe-sandbox\validation-evidence\wiki_csa_overhaul_fixture_manifest_20260713.json`

The source corpus contains 31 files: CSA plans, serialization policies, configuration procedures, deviation/FCO procedures, audit procedure, labeling and builder serialization work instructions, FCO records/templates, option/CI/serial registers, and one retired CCB charter under `_Superseded`.

## Fixture ownership decision

Before this tranche, `wiki_page.json` contained 4 pages. This tranche expands it to 15 exact-name pages.

Public Wiki routes also require a `Wiki Group Item` sidebar row under the owning `Wiki Space`.
The pages themselves are fixture-managed, but the full Wiki Space/sidebar remains database-managed
because it contains broader navigation that is not yet part of this tranche. Patch
`inductone_tools.patches.v2026_07_13_wiki_csa_space_links` appends only the three
CSA entry pages below to the existing `plus-one-ops-manual` Wiki Space, preserving all other
sidebar rows.

New fixture-owned pages:

- `inductone-csa-quality-system` — the controlled-doc-to-ERPNext CSA map.
- `inductone-csa-controlled-records-index` — the source document/register/template index with placeholders for final release links.

Existing pages brought under exact fixture ownership because they now carry CSA/source-alignment content:

- `3hmhgl7qdu` — Configuration Options
- `3hmdga44m5` — InductOne Build Pipeline
- `3hmiq2lbi9` — Serialization Rules and Part Number Allocation
- `3hngf036ne` — Deviation Requests
- `3hmtouafd5` — As-Built Records and Instances
- `82vdqj03n2` — InductOne Snapshot Diff Tool
- `3hmbhanak2` — BOM Export Package
- `eo88s4k9ui` — BOM Export - Engineering Overview
- `3hmeksuks8` — Engineering Signoff

Existing fixture-owned pages retained:

- `9n8bvqedso` — Part Number Allocation and Assignment
- `d0v7dsi9lu` — BOM Generation and Engineering Signoff
- `3hnmdg9m5q` — Roles and Permissions
- `inductone-csa-owner-handbook` — InductOne CSA Owner Handbook

The hook remains an exact-name `Wiki Page` filter. The Wiki is still not bulk-exported.

## Visual assets

The new Wiki content uses repo-owned SVGs rather than opaque embedded images:

- `inductone-csa-master-workflow.svg`
- `configuration-option-status-gate.svg`
- `builder-package-composition.svg`
- `as-built-instance-lineage.svg`
- `inductone-csa-quality-system-map.svg`

`inductone-csa-quality-system-map.svg` was added in this tranche to show the connection between the controlled source layer and the ERPNext execution layer.

## Validation gate

`scripts/run_wiki_fixture_validation.py` validates:

- `wiki_page.json` parses,
- page names and routes are unique,
- `hooks.py` exact-name Wiki filter matches `wiki_page.json`,
- required CSA pages are fixture-managed,
- required SVGs exist,
- SVG references resolve,
- legacy role names are absent,
- fixture pages are published and non-empty.

This should be run before any Wiki fixture deployment.

## Candidate validation

Candidate site: `inductone-candidate.localhost`

Validation evidence:

- Local fixture validator: `C:\hub\frappe-sandbox\validation-evidence\wiki_fixture_validation_20260713.json`
- Candidate fixture-file validator: `C:\hub\frappe-sandbox\validation-evidence\candidate_wiki_fixture_file_validation_20260713.json`
- Candidate database validation: `C:\hub\frappe-sandbox\validation-evidence\candidate_wiki_csa_fixture_db_validation_20260713.json`
- Post-migration IA audit: `C:\hub\frappe-sandbox\validation-evidence\wiki_information_architecture_audit_20260713T153421Z.json`
- Wiki Space link validation: `C:\hub\frappe-sandbox\validation-evidence\candidate_wiki_space_link_validation_20260713.json`

Results:

- `wiki_page.json` parses.
- `hooks.py` exact-name Wiki Page filter matches the 15 fixture rows.
- Candidate migrate applied the fixture.
- Candidate database contains all 15 fixture-managed pages.
- Candidate patch log contains `inductone_tools.patches.v2026_07_13_wiki_csa_space_links`.
- The CSA owner handbook, quality-system page, and controlled-records index are linked to Wiki Space route `plus-one-ops-manual`; `Wiki Page.get_space_route()` succeeds for all three.
- 11 fixture-managed pages now contain CSA/workflow visual references.
- No legacy role terms remain in the fixture-managed Wiki content.
- No referenced SVG asset is missing.
- Broader IA audit improved from 4 fixture-managed pages to 15, and long pages without SVG dropped from 22 to 14.

Remaining IA findings are intentionally not auto-fixed in this tranche. They are mostly generic support, inventory, gripper, release-note, and stub/redirect pages that require owner review before fixture promotion, completion, redirection, or depublishing.

## Release-link follow-up

The new controlled records index intentionally uses `Pending released SharePoint link` placeholders. After the CSA documents are released through Engineering Change and uploaded to their final SharePoint locations, replace each placeholder with the released link and export the updated Wiki fixture in the same repo change.
