# Role Governance Audit

This document is the durable audit trail for the June 2026 role and permission hardening work.

The goal is to replace accumulated, overlapping ERPNext roles with small independent capability roles. A user may hold multiple roles, but each role should mean one thing. No role should secretly grant authority in another domain.

## Confirmed target roles

| Role | Intent | Explicitly not included |
|---|---|---|
| `InductOne Manager` | Run the normal InductOne build process: create builds, select options, generate snapshots/configuration orders/packages, release to builder, allocate system serials, upload/review/reject/accept completions. | Cannot edit the InductOne process architecture, create builder tranches, export fixtures, or create/edit configuration options. |
| `InductOne Process Architect` | Own the InductOne process design and emergency correction path. This is Michael's system-owner role. | Not a general business role for normal operators. |
| `Operations Viewer` | Read-only visibility into ERPNext and InductOne operating records. Intended for people who need broad situational awareness but no mutation rights. | No create/write/submit/cancel/amend. |
| `Operations Manager` | Manage normal ERPNext operational workflows: Items, BOMs, Sales Orders, Delivery Notes, stock, production workflows, and Sales Order submission. | No InductOne authority by default. InductOne access should be read-only unless the user also has an InductOne role. |
| `Inventory Operator` | Execute inventory movement workflows such as receiving, stock entry, delivery note work, stock counts, and material issue handling when assigned. | No Item/BOM master-data ownership unless separately assigned. |
| `Gripper Manufacturer` | Execute serialized gripper work orders and refurbishment workflows. | No general InductOne authority and no broad ERP master-data ownership. |
| `Engineering User` | Perform Engineering Signoff and allocate part numbers. Engineering users can click the allocation button and generate new numbers. | No InductOne build execution authority unless also assigned `InductOne Manager`. |
| `InductOne External Builder` | Supplier/builder scoped access to generated handoff artifacts and completion upload/update path. | No raw Item, BOM, Sales Order, builder tranche, fixture, or unrelated supplier access. |
| `Finance Viewer` | Read-only audit visibility into anything Finance needs: operating records, inventory, sales, purchase, accounting, and InductOne history. | No editing. |
| `Procurement User` | Maintain procurement-facing item/vendor/commercial metadata, such as vendor descriptions, supplier details, and sales/pricing fields that procurement is expected to update. | No InductOne authority and no engineering/process release authority. |

## Confirmed user/workflow decisions

- Project Managers do not need a separate role in the hardened model. Sales Order submission should be opened to `Operations Manager`, and the wiki should be updated away from the old PM draft-only model.
- `Support Operations` is a red herring for this permission model. The current support-relevant person should be treated as `Operations Manager`.
- Finance should be able to read everything needed for audit trail purposes, but should not edit.
- Procurement needs limited edit authority around item/vendor/pricing metadata. This must be validated against actual ERPNext fields and DocTypes before broad deployment.
- Serialized gripper manufacturing/refurbishment should be separated into `Gripper Manufacturer`.
- Inventory movement work should be separated into `Inventory Operator`.
- `Builder` is explicitly retired. No user should hold it going forward.

## Repo implementation state

The repo now carries fixtures for the target custom roles and matching single-role Role Profiles:

- `InductOne External Builder`
- `InductOne Manager`
- `InductOne Process Architect`
- `Operations Viewer`
- `Operations Manager`
- `Inventory Operator`
- `Gripper Manufacturer`
- `Engineering User`
- `Finance Viewer`
- `Procurement User`

Role Profile assignment remains operational/database state. The repo defines the profiles; the database decides who has them.

The InductOne custom DocPerm fixture has been remapped so InductOne authority uses the target roles instead of:

- `InductOne Process Manager`
- `InductOne Architect`
- `Engineering Signoff Delegate`
- `Part Number Manager`
- `Engineering - Signoff`
- `OPS-INDUCTONE-GATEKEEP`
- `PRODUCT-INDUCTONE-GATEKEEP`
- generic `Builder`
- generic `Manufacturing User`
- generic `Project Manager` / `Projects Manager`

## Documented workflow coverage

The restored sandbox wiki and repo docs imply these responsibilities.

| Documented workflow | Target role coverage |
|---|---|
| Create/run InductOne builds | `InductOne Manager` |
| Generate snapshots, configuration orders, and builder packages | `InductOne Manager` |
| Release to builder | `InductOne Manager` |
| Allocate InductOne system serial from active tranche | `InductOne Manager`; tranche governance remains `InductOne Process Architect` |
| Upload/review/reject/accept builder completion | `InductOne Manager`; external builder can use only the controlled builder-facing completion path |
| Create immutable As-Built Record / Instance through acceptance action | `InductOne Manager` through controlled action |
| Create/edit configuration options and option mappings | `InductOne Process Architect` |
| Create/edit builder tranches | `InductOne Process Architect` |
| Export/push fixtures | `InductOne Process Architect` / `System Manager` only |
| Engineering signoff approve/reject/supersede | `Engineering User` |
| Allocate part numbers | `Engineering User` |
| Create/edit Items/BOMs/Product Bundles | `Operations Manager`; exact ERPNext standard permission mapping requires sandbox validation |
| Submit Sales Orders | `Operations Manager` |
| Create Delivery Notes / Stock Entries / inventory movements | `Inventory Operator` or `Operations Manager` |
| Serialized gripper work orders/refurbishments | `Gripper Manufacturer` |
| Broad read-only operational visibility | `Operations Viewer` |
| Broad read-only finance/audit visibility | `Finance Viewer` |
| Procurement item/vendor/pricing metadata maintenance | `Procurement User`; exact DocTypes/fields require sandbox validation |

## ERPNext operational permission implementation

The operational role layer is now encoded in
`scripts/update_operational_role_docperms.py` and materialized into
`inductone_tools/fixtures/custom_docperm.json`.

This is intentionally implemented as code first so the permission model can be
reviewed and regenerated instead of hand-edited in JSON.

| Role | Implemented business surface |
|---|---|
| `Operations Viewer` | Read/report/export/print/select on the operational and audit records used by the business: Items, BOMs, Product Bundles, Sales Orders, Delivery Notes, Stock Entries, Work Orders, Purchase docs, stock ledgers/bins/warehouses, suppliers/customers, Item Prices, accounting/audit records, and InductOne records. No mutation. |
| `Operations Manager` | Create/write/submit/cancel/amend operational master and transaction documents: Items, BOMs, Product Bundles, Sales Orders, Delivery Notes, Stock Entries, Work Orders, Purchase Orders, Purchase Receipts, Material Requests, Pick Lists, Stock Reconciliations, Item Prices, Suppliers/Customers, Warehouses, Serial Nos, UOM/Item Group/Brand. Accounting records remain read-only. InductOne authority remains separate except read visibility. |
| `Inventory Operator` | Create/write/submit/cancel/amend inventory movement documents: Delivery Notes, Stock Entries, Purchase Receipts, Material Requests, Pick Lists, Stock Reconciliations. Read-only on Items, BOMs, Sales/Purchase Orders, Warehouses, Bins, Serial Nos, Stock Ledger Entries, Work Orders, Suppliers, and Customers. |
| `Gripper Manufacturer` | Create/write/submit/cancel/amend Work Orders, Stock Entries, and Pick Lists for serialized gripper/refurbishment execution. Read-only on Items, BOMs, Product Bundles, Warehouses, Bins, Serial Nos, and Stock Ledger Entries. |
| `Finance Viewer` | Read/report/export/print/select on the same broad business and audit surface as Operations Viewer, including accounting/audit records. No mutation. |
| `Procurement User` | Write existing Item level-0 descriptive/vendor fields, Suppliers, Addresses, Contacts, Item Prices, Price Lists, UOMs, Item Groups, and Brands. Can create Item Price records. Can read purchasing documents, BOM/Product Bundle context, stock ledgers, warehouses, and bins. Cannot create Items, submit/cancel transactions, or write Item permlevel-1 valuation/opening-stock-adjacent fields. |

### Field permission decision: Procurement and `Item.standard_rate`

`Item.standard_rate` is permlevel 1 in ERPNext, grouped with fields such as
`opening_stock`, `valuation_rate`, sales UOM, max discount, and customer item
tables. Because Frappe DocPerms grant by permlevel, not by individual field,
`Procurement User` is intentionally granted read-only access to Item permlevel
1. Procurement should maintain updated commercial prices through `Item Price`.

If the business later decides Procurement must edit `Item.standard_rate`
directly, that should be treated as a separate design decision because it also
opens other permlevel-1 Item fields unless the field model is redesigned.

## Validation requirements before production

Do not deploy this role model to production until the candidate sandbox proves:

1. No user still depends on `Super` Role Profile for the new target access model.
2. `InductOne Manager` users can run the whole InductOne build/completion process but cannot create/edit configuration options or builder tranches.
3. `InductOne Process Architect` can create/edit configuration options, builder tranches, fixture controls, and all InductOne records.
4. `Engineering User` can approve/reject/supersede signoffs and allocate part numbers.
5. `Operations Viewer` can read intended records but cannot create/write/submit/cancel.
6. `Operations Manager` can perform normal ERPNext operational workflows, including Sales Order submission, but has no InductOne action authority unless separately assigned.
7. `Inventory Operator` can perform inventory movement workflows without gaining Item/BOM/Sales Order master-data ownership.
8. `Gripper Manufacturer` can perform serialized gripper work order/refurbishment workflows without gaining unrelated production authority.
9. `Finance Viewer` can read required audit trails without write access.
10. `Procurement User` can update intended vendor/pricing/descriptive data without gaining InductOne or engineering release authority.
11. `InductOne External Builder` still passes supplier scoping and raw Item/BOM/Sales Order denial tests.

## Cleanup sequence

1. Restore candidate sandbox from production backup.
2. Apply local repo state.
3. Run `bench migrate`.
4. Remove/clear broad Role Profiles like `Super` from users being tested; assign explicit target roles instead.
5. Run automated role checks for list/read/create/write/submit/cancel on target DocTypes.
6. Run UI smoke tests for representative users.
7. Update wiki pages to match the final model.
8. Only after passing candidate validation, push and deploy.

## Open implementation questions

Resolved in candidate implementation:

- `Procurement User` can write Item level-0 descriptive/vendor data and Item
  Price commercial data, but cannot write Item permlevel-1 fields.
- `Inventory Operator` can submit/cancel inventory movement documents.
- `Gripper Manufacturer` can submit/cancel Work Orders, Stock Entries, and Pick
  Lists.
- `Finance Viewer` uses custom read-only DocPerms for the business/audit record
  surface instead of inheriting broad ERPNext accounting manager roles.

Remaining validation before production:

- GUI smoke-test each representative persona.
- Confirm whether Operations Manager should have any accounting mutation at all;
  the current implementation keeps accounting records read-only.
- Confirm whether Procurement ever needs to create Suppliers or Items; the
  current implementation allows Supplier edits and Item Price creation, but not
  Item creation.

## Candidate validation evidence

The refreshed candidate sandbox was restored from the 2026-06-25 production
backup and migrated with the local repo state. Validation evidence was written
under `C:\hub\frappe-sandbox\validation-evidence`.

Important files:

- `candidate_permission_audit_operational_roles_final.jsonl`
- `candidate_role_assignment_apply_expanded_system_manager_cleanup.txt`
- `candidate_persona_user_creation.txt`

Automated checks passed for:

- Christina no longer retaining `System Manager` in the strict target model.
- Christina losing write authority on InductOne process architecture records
  like `InductOne Configuration Option`.
- Procurement gaining Item Price create/write while not gaining Item create.
- External builders remaining denied raw Item/BOM access.
- Operations Viewer remaining read-only.
- Inventory Operator gaining Stock Entry submit.
- Gripper Manufacturer gaining Work Order submit.
