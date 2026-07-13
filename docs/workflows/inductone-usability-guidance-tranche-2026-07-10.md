# InductOne usability and in-app guidance tranche

Date: 2026-07-10  
Environment target: candidate sandbox before production consideration  
Production touched: no  
Push performed by Codex: no

This tranche adds a repo-managed usability layer on top of the hardened InductOne workflow. The purpose is not decoration. The purpose is to make the expected next action visible inside ERPNext, especially for external builders who should not need tribal knowledge or access to internal workspaces.

## Source-of-truth segmentation

| Surface | Source of truth | Deployment path | Notes |
|---|---|---|---|
| Shared guidance content | `inductone_tools/guidance.py` | App code | Read-only, permission-aware guidance payloads. No new `ignore_permissions=True` path was introduced. |
| Shared POR rendering | `inductone_tools/public/js/guidance.js` | App static asset via `app_include_js` | One POR-branded renderer for status banners, next-action panels, checklist rows, and Builder Portal task cards. |
| Builder Portal content | `inductone_tools/fixtures/workspace.json` + `inductone_tools/fixtures/custom_html_block.json` | Filtered Workspace and Custom HTML Block fixtures | Builder Portal remains external-builder-only, exposes only Configuration Orders and Build Completions, and renders its core guidance statically so the page remains useful even if Workspace custom-block scripts do not execute. |
| Builder onboarding | `inductone_tools/fixtures/module_onboarding.json` + `inductone_tools/fixtures/onboarding_step.json` | Filtered onboarding fixtures | First-run learning path for receiving a Build, downloading the package, uploading the workbook, and handling rejection. |
| In-form guidance | `inductone_tools/fixtures/client_script.json` | Filtered Client Script fixture | Five narrow scripts call the shared renderer for Configuration Orders, Build Completions, Builds, Engineering Signoffs, and Configuration Options. |
| Guidance-style upload messages | `inductone_tools/build_completion.py` | App code | Builder-facing upload and lifecycle blocks now explain what happened and the next action. |
| Validation | `scripts/run_usability_guidance_validation.py` | Candidate validation script | Produces JSON evidence in the standard validation evidence folder. |

No broad fixture filters were introduced. Every new fixture type uses an exact-name allowlist in `hooks.py`.

## Builder-facing behavior

The Builder Portal now has four persistent pieces of guidance:

1. What you need to do, rendered as a persistent static panel inside the Builder Portal Workspace.
2. Download your build package, pointing to the assigned Configuration Order document index.
3. Upload completion workbook, pointing to the Build Completion workflow.
4. If a build is rejected, read Review Notes and upload a corrected workbook while preserving the rejected record as audit history.

The read-only builder guidance API still returns supplier-scoped tasks for validation and future enhancement, but the visible Workspace guidance does not depend on dynamic Custom HTML Block script execution. Browser validation on 2026-07-10 confirmed Frappe renders Workspace Custom HTML Blocks inside Shadow DOM, so the durable production design is: static guidance first, dynamic enhancement second.

The portal deliberately does not link builders to Engineering, Operations, raw BOMs, raw Items, BOM Export Package pages, or Configured BOM Snapshot pages. Their build files are delivered through the Configuration Order document index and release manifest.

External-builder record visibility is both supplier-scoped and release-state-scoped:

- visible Configuration Orders: `Released`, `Awaiting Completion`, `Closed`, and the future/alias status `Completed`;
- hidden Configuration Orders: `Draft`, `Cancelled`, and any other internal test or pre-release state;
- direct URL access follows the same rule, so a copied Draft Configuration Order link is denied for external builders.

## Operations and Engineering behavior

Operations and Engineering receive lighter orientation using the same shared pattern:

- InductOne Build shows build workflow status, next action, and prerequisites.
- InductOne Configuration Order shows release/completion status guidance.
- Engineering Signoff shows decision status and target checks.
- InductOne Configuration Option shows Draft, Released, and Deprecated guidance.

Draft Configuration Options remain valid ideation records. They are intentionally not build-usable. The Engineering Signoff approval gate performs release.

## Controlled vocabulary

The shared guidance module publishes these canonical terms:

- Build
- Build Completion
- Configuration Order
- release package
- builder serial workbook
- document index
- Engineering Signoff
- Configuration Option
- As-Built Record
- InductOne Instance

New user-facing copy in this tranche avoids em dashes and pairs color with text or icons.

## Wiki alignment owed

Wiki content is explicitly out of scope for this tranche and remains a required follow-up. Before any bulk Wiki update, run an audit-and-classify pass:

- keep and update,
- obsolete and hide,
- convert to fixture,
- leave database-owned.

The InductOne CSA lifecycle must be incorporated into the Wiki properly during that follow-up. The owner handbook and SVGs are a start, not a complete Wiki information architecture pass.

## Candidate validation

Run:

```bash
cd /home/michaelplusone/frappe-sandbox/benches/candidate-bench
env/bin/python apps/inductone_tools/scripts/run_usability_guidance_validation.py \
  --site inductone-candidate.localhost \
  --sites-path /home/michaelplusone/frappe-sandbox/benches/candidate-bench/sites \
  --repo-root apps/inductone_tools \
  --evidence-dir /mnt/c/hub/frappe-sandbox/validation-evidence
```

Expected result: `GATE: PASS`.

Latest candidate evidence:

- `C:\hub\frappe-sandbox\validation-evidence\usability_guidance_validation_20260710T195741Z.json`
- `C:\hub\frappe-sandbox\validation-evidence\builder_portal_render_validation_20260710T195741Z.json`
