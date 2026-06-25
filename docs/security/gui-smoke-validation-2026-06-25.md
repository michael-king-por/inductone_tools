# GUI Smoke Validation — 2026-06-25

Candidate GUI smoke validation passed after the operational role fixture update.

## Result

| Metric | Value |
|---|---|
| Site | `inductone-candidate.localhost` |
| URL | `http://inductone-candidate.localhost:8000` |
| Run timestamp | `2026-06-25T16:32:30Z` |
| Checks executed | 70 |
| Checks passed | 70 |
| Checks failed | 0 |
| Evidence folder | `C:\hub\frappe-sandbox\validation-evidence\gui-smoke-2026-06-25T16-32-30-281Z` |
| JSON result | `C:\hub\frappe-sandbox\validation-evidence\gui-smoke-2026-06-25T16-32-30-281Z\gui-smoke-results.json` |
| Markdown result | `C:\hub\frappe-sandbox\validation-evidence\gui-smoke-2026-06-25T16-32-30-281Z\gui-smoke-results.md` |

## Scope

This was a browser-driven GUI smoke test against the candidate sandbox. It logged in as each representative persona and checked real Desk routes for:

- readable vs denied pages,
- create-button visibility,
- negative access boundaries,
- supplier/builder confinement,
- broad read-only roles,
- operational mutation roles,
- engineering and part-number access,
- procurement pricing path,
- finance read-only audit path.

The test did not create or submit business records. Workflow state transitions and direct whitelisted method calls remain a separate validation gate.

## Personas covered

| Persona | User | Result |
|---|---|---|
| External Builder - Motion Controls | `motion.builder@plusonerobotics.com` | PASS |
| External Builder - LAM | `lam@plusonerobotics.com` | PASS |
| InductOne Manager + Engineering + Operations | `christina.gt@plusonerobotics.com` | PASS |
| InductOne Manager + Operations | `jim.haws@plusonerobotics.com` | PASS |
| Engineering User | `shaun.edwards@plusonerobotics.com` | PASS |
| Operations Viewer | `candidate.operations.viewer@example.invalid` | PASS |
| Inventory Operator | `candidate.inventory.operator@example.invalid` | PASS |
| Gripper Manufacturer | `candidate.gripper.manufacturer@example.invalid` | PASS |
| Finance Viewer | `candidate.finance.viewer@example.invalid` | PASS |
| Procurement User | `candidate.procurement.user@example.invalid` | PASS |

## Important confirmations

- Motion/LAM can reach generated builder-facing records and cannot reach raw Item/BOM/Sales Order/InductOne Build/tranche/signoff/part-number surfaces.
- Christina can create normal InductOne Manager, Engineering, and Operations records, but cannot create InductOne Configuration Options.
- Jim can perform InductOne Manager and Operations Manager GUI actions, but cannot create InductOne Configuration Options.
- Engineering-only user can access Engineering Signoff and Part Number Allocation Requests, but cannot access raw Item/Sales Order surfaces.
- Operations Viewer can read operational and InductOne records but has no create button.
- Inventory Operator can create inventory movement records but cannot create Item/Sales Order/Work Order records.
- Gripper Manufacturer can create Work Orders and Stock Entries but cannot access Sales/Purchase Order creation surfaces.
- Finance Viewer can read sales/purchase/accounting/stock/InductOne records without create buttons.
- Procurement User can create Item Prices and read/edit procurement-facing records without Item or Sales Order create authority.

## Tooling note

The in-app browser connector failed to initialize due to a local plugin asset-path error, so the GUI validation used a temporary Playwright runtime under `C:\hub\.gui-smoke-runtime`. This did not modify repo dependencies. The repo contains the repeatable runner at:

`scripts/run_candidate_gui_smoke.mjs`

## Remaining validation gates

- Direct API / whitelisted method positive and negative tests.
- Deeper workflow transition tests that actually create, submit, release, allocate, upload, reject, and accept records in candidate.
- Wiki/landing page role-language update.
- Production user-assignment and deployment plan.

