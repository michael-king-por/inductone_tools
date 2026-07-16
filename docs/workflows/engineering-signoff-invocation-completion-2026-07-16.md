# Engineering Signoff invocation wiring — completion note

Date: 2026-07-16  
Branch: `integration/wiki-guidance-2026-07-13`  
Environment validated: candidate only, `inductone-candidate.localhost`

## Owner decision recorded

The material-change trigger based on a separate controlled-drawing Attach field was removed from the working tree and candidate.

Reason: the BOM Export Package and builder-release flow already treat native Item/BOM file attachments as the file-of-record. A separate drawing field would fork file control and point Engineering Signoff at the wrong evidence source. Any future material-change automation must be handled as a file-control redesign, not as a bolt-on field.

## Final implemented scope

| Area | Final state | Evidence |
|---|---|---|
| Request buttons | PASS — Item, BOM, and Product Bundle have gated `Request Engineering Signoff` buttons via `client_script.json`. | `engineering_signoff_invocation_validation_20260716T110226Z.json` |
| Status banners | PASS — normalized status banner behavior retained on Item, BOM, and Product Bundle. | `engineering_signoff_invocation_validation_20260716T110226Z.json` |
| Manual Engineering Signoff fallback | PASS — `target_doctype` is selectable, `target_docname` is an editable Dynamic Link, and manual insert normalizes through the same current-record supersede path. | `engineering_signoff_invocation_validation_20260716T110226Z.json` |
| On-insert signoff creation | PASS — new Item, BOM, and Product Bundle records create current Pending Engineering Signoff records. | `engineering_signoff_invocation_validation_20260716T110226Z.json` |
| Material-change auto-trigger | REMOVED — no Item/BOM/Product Bundle `on_update` hook remains for drawing changes. | `engineering_signoff_invocation_revert_grep_20260716.txt` |
| Rejected custom drawing field | REMOVED — candidate has no Custom Field records and no DB columns for the rejected field on Item, BOM, or Product Bundle. | `engineering_signoff_invocation_revert_column_cleanup_20260716.json` |
| Native attachment file-of-record regression | PASS — BOM export attachment collection still uses native Item/BOM `File` records. | `engineering_signoff_invocation_validation_20260716T110226Z.json` |
| Builder-release gate regression | PASS — builder-release readiness gate still executes successfully. | `engineering_signoff_invocation_validation_20260716T110226Z.json` |
| Permission-bypass grep | PASS — no new whitelisted permission-bypass paths introduced by this tranche. | `engineering_signoff_invocation_validation_20260716T110226Z.json` |

## Candidate validation evidence

- Candidate migrate clean after revert and stale candidate lock cleanup: `C:\hub\frappe-sandbox\validation-evidence\engineering_signoff_invocation_revert_candidate_migrate_clean_20260716.txt`
- Candidate Role Profile stale-lock cleanup evidence: `C:\hub\frappe-sandbox\validation-evidence\engineering_signoff_invocation_revert_role_profile_lock_cleanup_20260716.json`
- Candidate rejected-field cleanup evidence: `C:\hub\frappe-sandbox\validation-evidence\engineering_signoff_invocation_revert_column_cleanup_20260716.json`
- Candidate rejected field remains absent after clean migrate: `C:\hub\frappe-sandbox\validation-evidence\engineering_signoff_invocation_revert_field_absent_after_migrate_20260716.json`
- Candidate invocation validation evidence: `C:\hub\frappe-sandbox\validation-evidence\engineering_signoff_invocation_validation_20260716T110226Z.json`
- Candidate validation console: `C:\hub\frappe-sandbox\validation-evidence\engineering_signoff_invocation_revert_validation_console_final_20260716.txt`
- App-tree grep clean for the removed trigger/field names: `C:\hub\frappe-sandbox\validation-evidence\engineering_signoff_invocation_revert_grep_20260716.txt`
- Local compileall: `C:\hub\frappe-sandbox\validation-evidence\engineering_signoff_invocation_revert_compileall_20260716.txt`
- Local fixture parse: `C:\hub\frappe-sandbox\validation-evidence\engineering_signoff_invocation_revert_fixture_parse_20260716.txt`

## Files intentionally changed by the final tranche

- `inductone_tools/engineering_signoff.py`
- `inductone_tools/hooks.py`
- `inductone_tools/fixtures/client_script.json`
- `inductone_tools/fixtures/doctype.json`
- `scripts/run_engineering_signoff_invocation_validation.py`
- `docs/workflows/engineering-signoff-invocation-completion-2026-07-16.md`

`inductone_tools/fixtures/custom_field.json` is intentionally not changed by this tranche after the revert.

SIGNOFF INVOCATION (MANUAL + ON-INSERT) WIRED: YES; material-change auto-trigger removed pending file-control redesign
