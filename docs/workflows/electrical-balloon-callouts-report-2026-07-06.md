# Electrical Balloon Callouts report

Date: 2026-07-06

## Finding

`Electrical Balloon Callouts` existed only as a non-standard GUI-created Query
Report. It lived under the ERPNext `Manufacturing` module and its role table
contained retired roles:

- `Manufacturing Manager`
- `Manufacturing User`
- `Builder`
- `Operations Member`

After permission hardening, current internal users no longer held those roles.
Candidate execution confirmed the report failed with `PermissionError` for
current users even though the underlying SQL returned data.

Candidate data check:

- `BOM Item.custom_balloon_numbers` field exists.
- 495 BOM Item rows have non-empty balloon numbers.
- 311 rows match the report's submitted + active BOM filter.

## Resolution

The report is now app-owned/versioned by `inductone_tools`:

- `inductone_tools/fixtures/report.json`
- filtered `Report` fixture entry in `inductone_tools/hooks.py`
- idempotent patch
  `inductone_tools.patches.v2026_07_06_balloon_report_access`

The report remains named `Electrical Balloon Callouts` but is assigned to the
`InductOne Tools` module.

Current report roles:

- `System Manager`
- `Operations Manager`
- `Operations Viewer`
- `Inventory Operator`
- `Gripper Manufacturer`
- `Engineering User`
- `Finance Viewer`
- `Procurement User`
- `InductOne Manager`
- `InductOne Process Architect`

`InductOne External Builder` is intentionally not granted access.

## Permission note

Frappe Query Reports also check permission on the report's `ref_doctype`.
Because this report references `BOM`, the `Engineering User` role needs
read/report access to `BOM` to execute the report. The fix adds read-only BOM
permission for `Engineering User` only:

- read
- report
- export
- print
- select

No write/create/submit/cancel/delete access is granted.

`BOM` was already Custom-DocPerm-managed, so this does not trigger the Frappe
"first Custom DocPerm row replaces standard DocPerms" trap.

## Validation evidence

Candidate site: `inductone-candidate.localhost`

Evidence:

- `C:\hub\frappe-sandbox\validation-evidence\balloon_report_validation_20260706T192337Z.json`

Validated:

1. Report role table matches the current role model.
2. Underlying query returns 311 rows.
3. Current internal representative users can execute the report.
4. Motion and LAM external builders receive `PermissionError`.
5. Candidate migrate executed
   `inductone_tools.patches.v2026_07_06_balloon_report_access`.
