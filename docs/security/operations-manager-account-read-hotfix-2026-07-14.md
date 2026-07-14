# Operations Manager Account read/select hotfix — 2026-07-14

## Symptom

Patty Gomez, holding the curated `Operations Manager` role, could create a
Sales Order form but received:

> User don't have permissions to select/read this account.

This happened when saving/selecting Sales Order accounting-linked fields.

## Root cause

`Account` is already managed by repo-owned `Custom DocPerm` fixtures for
read-only audit roles. In Frappe, once any `Custom DocPerm` exists for a DocType,
the standard DocPerm rows for that DocType are replaced by the custom set.

The fixture contained `Account` read/select rows for:

- `Finance Viewer`
- `Operations Viewer`

It did not contain `Account` read/select for `Operations Manager`, even though
`Operations Manager` is intended to create and submit Sales Orders. Sales Order
and Sales Order Item validation can require selecting linked Account records
such as income accounts.

## Fix

Added least-privilege `Account` read/select access for `Operations Manager`.

No accounting mutation authority was added:

- `write = 0`
- `create = 0`
- `delete = 0`
- `submit = 0`
- `cancel = 0`
- `amend = 0`

Implemented in:

- `scripts/update_operational_role_docperms.py`
- `inductone_tools/fixtures/custom_docperm.json`
- `inductone_tools/patches/v2026_07_14_operations_manager_account_read.py`
- `inductone_tools/patches.txt`

The patch is guarded against the Custom DocPerm replace-trap: it only adds the
Operations Manager row if `Account` is already Custom-DocPerm-managed.

## Candidate validation

Evidence:

`C:\hub\frappe-sandbox\validation-evidence\operations_manager_account_sales_order_hotfix_20260714.json`

Validated in candidate:

- Patty has `Operations Manager`.
- `Account / Operations Manager` Custom DocPerm exists with `read=1`,
  `select=1`, `write=0`, `create=0`.
- Effective `Account` read permission for Patty passes.
- Effective `Account` select permission for Patty passes.
- Patty can list Account records for link selection.
- Patty can insert a draft Sales Order in candidate without the Account
  PermissionError. The test rolled back afterward.
