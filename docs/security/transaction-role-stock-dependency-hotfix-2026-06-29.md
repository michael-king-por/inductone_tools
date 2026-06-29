# Transaction Role Stock Dependency Hotfix — 2026-06-29

## Trigger

After the Finance Viewer report-access regression was fixed, the same bug class
was found in the transaction roles:

- `Operations Manager`
- `Inventory Operator`
- `Gripper Manufacturer`

The generated `Custom DocPerm` fixture had no role-scoped rows for several
ERPNext stock dependency DocTypes. This is higher risk than the Finance Viewer
case because it fails during transaction submission, especially when an item is
both batch-tracked and serial-tracked.

Production users affected by this role model are:

- `patty.gomez@plusonerobotics.com` — `Operations Manager`
- `nathaniel.pantuso@plusonerobotics.com` — `Operations Manager`, `Gripper Manufacturer`

The system owner confirmed that InductOne/stock workflows use both batch and
serial tracking and that these transaction roles must complete their workflows
end-to-end.

## Root cause

The hardening model intentionally stripped broad ERPNext roles such as `Stock
User`, `Stock Manager`, and broad Role Profiles. That made the curated roles
auditable, but it also meant submit-time dependencies had to be granted
explicitly.

Before this hotfix, `Operations Manager`, `Inventory Operator`, and `Gripper
Manufacturer` had no `Custom DocPerm` rows at all for:

- `Serial and Batch Bundle`
- `Batch`
- `Company`
- `Currency`
- `Fiscal Year`
- `Territory`

In addition, `Inventory Operator` and `Gripper Manufacturer` had only read-only
access to `Serial No`, which was not sufficient for receiving/manufacturing
serialized stock.

## Implemented fix

The role fixture generator now adds a transaction-dependency layer for only the
three transaction roles.

Added migration patch:

```text
inductone_tools.patches.v2026_06_29_transaction_role_stock_dependencies
```

The patch is idempotent and mirrors the generator output.

Granted permissions:

| Role | DocType | Permission profile |
|---|---|---|
| `Operations Manager` | `Serial and Batch Bundle` | `TRANSACTION` — read/write/create/submit/cancel/amend, delete remains 0 |
| `Operations Manager` | `Batch`, `Serial No` | `MAINTAIN` — read/write/create |
| `Operations Manager` | `Company`, `Currency`, `Fiscal Year`, `Territory` | `READ` |
| `Inventory Operator` | `Serial and Batch Bundle` | `TRANSACTION` — read/write/create/submit/cancel/amend, delete remains 0 |
| `Inventory Operator` | `Batch`, `Serial No` | `MAINTAIN` — read/write/create |
| `Inventory Operator` | `Company`, `Currency`, `Fiscal Year`, `Territory` | `READ` |
| `Gripper Manufacturer` | `Serial and Batch Bundle` | `TRANSACTION` — read/write/create/submit/cancel/amend, delete remains 0 |
| `Gripper Manufacturer` | `Batch`, `Serial No` | `MAINTAIN` — read/write/create |
| `Gripper Manufacturer` | `Company`, `Currency`, `Fiscal Year`, `Territory` | `READ` |

No other role was changed.

## Fixture before/after

Before:

- The three transaction roles had no `Custom DocPerm` rows for `Serial and Batch
  Bundle`, `Batch`, `Company`, `Currency`, `Fiscal Year`, or `Territory`.
- `Inventory Operator` and `Gripper Manufacturer` had read-only `Serial No`
  grants.

After:

- `inductone_tools/fixtures/custom_docperm.json` increased from 224 rows to 242
  rows: net `+18`.
- The `+18` rows are the six missing dependency DocTypes for each of the three
  transaction roles.
- Existing `Serial No` rows for `Inventory Operator` and `Gripper Manufacturer`
  were upgraded in place from read-only to maintain.

## Candidate execution validation

Candidate sandbox:

```text
inductone-candidate.localhost
```

Migration:

```text
bench --site inductone-candidate.localhost migrate
```

Result:

```text
Executing inductone_tools.patches.v2026_06_29_transaction_role_stock_dependencies
Success
```

Execution smoke evidence:

```text
C:\hub\frappe-sandbox\validation-evidence\transaction_role_stock_dependency_smoke_20260629T152322Z.json
```

Result:

- `Inventory Operator` submitted a material receipt for a batch+serial tracked
  test item; ERPNext created and submitted `Serial and Batch Bundle`.
- `Operations Manager` submitted a Sales Order and a stock issue for a
  batch+serial tracked test item; ERPNext created and submitted `Serial and
  Batch Bundle`.
- `Gripper Manufacturer` submitted a Work Order and manufacture Stock Entry for
  a serialized/batched finished-good item; ERPNext created and submitted
  `Serial and Batch Bundle`.
- `Procurement User` created and updated `Item Price` and viewed `Purchase
  Order` list access without requiring Purchase Order create/write.

Summary:

```text
5/5 passed
```

Full candidate validator evidence:

```text
C:\hub\frappe-sandbox\validation-evidence\production_post_deploy_validation_20260629T152446Z.json
```

Result:

```text
10/11 passed
```

The only failure was the known stale candidate `Super` Role Profile state. The
new transaction-role stock dependency check passed.

## Permission bits beyond planned profiles

None.

The only test-script correction required was to use ERPNext's Work Order
`make_stock_entry` mapper for the Gripper Manufacturer manufacture smoke. That
resolved a domain `ValidationError` (`For Quantity (Manufactured Qty) is
mandatory`) without adding any permission bit.
