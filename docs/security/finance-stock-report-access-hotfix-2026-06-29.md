# Finance Business Report Access Hotfix — 2026-06-29

## Trigger

Matt Speer reported that he could no longer access the ERPNext **Stock Balance**
and **Stock Ledger** reports after the permission hardening deployment. He uses
these reports monthly for inventory review. A broader candidate audit showed
the same report-level gap affected other finance/business audit reports.

## Root cause

The production hardening intentionally cleared Matt's broad `Super` Role Profile
and assigned the scoped `Finance Viewer` role.

`Finance Viewer` correctly has read/report/export/print/select access to the
underlying stock and audit DocTypes, including:

- `Item`
- `Stock Reconciliation`
- `Stock Ledger Entry`
- `Bin`
- `Warehouse`
- `Serial No`
- `Stock Entry`
- `Work Order`

However, ERPNext standard Script Reports have a second access gate on the
`Report` record itself. In candidate, before the hotfix, both reports allowed
only:

- `Stock User`
- `Accounts Manager`

That meant Matt could read the underlying stock data but Frappe blocked him at
the report-level permission check before either report could run.

## Why not restore `Stock User` or `Accounts Manager`

Restoring `Stock User` would be too broad for the finance role. In candidate,
`Stock User` grants create/write/submit/cancel/delete/amend on `Stock Entry`.
`Accounts Manager` similarly carries accounting mutation authority on invoice
documents. Both conflict with the hardening decision that Matt should have broad
finance/audit visibility without operational mutation rights.

## Implemented fix

Added migration patch:

```text
inductone_tools.patches.v2026_06_29_finance_stock_report_access
```

The patch idempotently appends `Finance Viewer` to the Report role rows for a
curated set of business/audit reports covering inventory valuation, stock
ledger review, sales/purchase registers, and accounting ledgers. It deliberately
does not grant admin diagnostics, manufacturing planning, or operational action
reports.

The patch also grants read-only access to downstream report dependency DocTypes
that are required for those reports to execute:

- `Batch`
- `Company`
- `Currency`
- `Fiscal Year`
- `Serial and Batch Bundle`
- `Territory`

These are read/report/export/print/select grants only. They do not add create,
write, submit, cancel, delete, or amend authority.

This fixes the missing report gate without granting Matt stock or accounting
write authority.

## Candidate validation

Candidate sandbox:

```text
inductone-candidate.localhost
```

Evidence:

```text
C:\hub\frappe-sandbox\validation-evidence\finance_business_report_access_hotfix_20260629.json
C:\hub\frappe-sandbox\validation-evidence\finance_stock_report_execution_hotfix_20260629.json
```

Result:

- Curated Finance Viewer business/audit report set: `Finance Viewer` present on
  Report role table; candidate Finance Viewer persona permitted.
- Focused hotfix evidence summary: 30/30 curated reports passed.
- Critical execution evidence summary: 8/8 passed, including read access to
  `Serial and Batch Bundle` and successful execution of `Stock Balance` and
  `Stock Ledger` as the candidate Finance Viewer persona.

The full production post-deploy validator was also extended to include these two
report access checks. Running that full validator against candidate produced an
expected unrelated candidate-only failure on `super_profile_absence`, because
this restored candidate database still contains users with the old `Super` Role
Profile. The new report checks themselves passed.

## Production deployment note

This hotfix should be deployed through the normal app update + `bench migrate`
path. The production post-deploy validator should then be run with:

```bash
--finance-report-user "matt.speer@plusonerobotics.com"
```

Expected post-hotfix production validator result is 11/11 passed after the
subsequent transaction-role stock dependency validator extension is included.
