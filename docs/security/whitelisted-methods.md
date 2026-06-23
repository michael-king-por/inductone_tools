# Whitelisted Method Inventory

Whitelisted methods are callable from the browser/client side and, depending on permissions and session context, may also be reachable through API calls. They are therefore part of the security and audit surface.

This inventory is based on static inspection of the local repo. It should be regenerated after adding/removing `@frappe.whitelist()` functions.

## Review rule

Every whitelisted method should be classified as one of:

- Read-only helper.
- User-initiated state-changing action.
- Administrative action.
- Transitional/debug/audit utility.

State-changing methods must enforce role, state, and input gates server-side.

## Current inventory

| Method | Classification | Notes / required gates |
|---|---|---|
| `inductone_tools.bom_export.generate_now` | State-changing action | Generates/updates BOM Export Package artifacts. Review transaction ownership and role gate. |
| `inductone_tools.build_completion.create_completion_from_upload` | State-changing action | Creates Build Completion from uploaded workbook. Enforces CO status and parses before mutation. Needs upload/integration tests. |
| `inductone_tools.build_completion_accept.accept_completion_create_as_built` | Critical state-changing action | Atomic acceptance; must be role-gated and heavily tested. |
| `inductone_tools.builder_release.check_builder_release_readiness` | Read/validation helper | Should be safe read-only readiness check. |
| `inductone_tools.builder_release.generate_builder_release_bundle` | State-changing action | Generates builder release artifacts. Needs role gate and failure-state review. |
| `inductone_tools.builder_release.release_to_builder_now` | Critical state-changing action | Releases operational package/state. Needs explicit role gate and lifecycle tests. |
| `inductone_tools.builder_release.acknowledge_builder_release` | State-changing action | Records acknowledgement. Needs actor/role clarity. |
| `inductone_tools.builder_release.generate_required_serial_capture_artifact` | State-changing action | Generates workbook artifact. Needs package/build precondition tests. |
| `inductone_tools.builder_release.submit_as_built_now` | Legacy or alternate state action | Review whether still part of intended workflow now that Build Completion acceptance exists. |
| `inductone_tools.builder_release.close_build_from_as_built` | Legacy or alternate state action | Review for overlap with atomic acceptance path. |
| `inductone_tools.engineering_signoff.request_signoff` | State-changing action | Creates/updates signoff request. Needs requester role rules. |
| `inductone_tools.engineering_signoff.approve_signoff` | Critical state-changing action | Releases/approves controlled artifact. Must require gatekeeper role. |
| `inductone_tools.engineering_signoff.reject_signoff` | Critical state-changing action | Rejects controlled artifact. Must require gatekeeper role and reason. |
| `inductone_tools.engineering_signoff.supersede_config_option` | Critical state-changing action | Changes option lifecycle. Needs gatekeeper role and audit trail. |
| `inductone_tools.engineering_signoff.get_current_signoff_status` | Read helper | Should remain read-only. |
| `inductone_tools.engineering_signoff.get_current_signoff_record` | Read helper | Should remain read-only. |
| `inductone_tools.fixture_sync.export_and_push_fixtures` | Administrative/transitional utility | Highest governance risk. Restrict to System Manager; preferably remove from normal production use. |
| `inductone_tools.instance.acceptance.accept_completion_create_as_built` | Shim/compatibility action | Verify whether this delegates to canonical acceptance method. Avoid duplicate paths. |
| `inductone_tools.instance.hooks.get_instance_for_as_built` | Read helper | Used by As-Built client script to show linked Instance. |
| `inductone_tools.part_numbering.allocate_numbers` | State-changing action | Allocates part numbers. Needs role gate and idempotency/rollback tests. |
| `inductone_tools.serial_allocation.release.allocate_serial_for_build` | Critical state-changing action | Consumes serial from tranche. Must be role-gated and concurrency-tested. |
| `inductone_tools.serial_allocation.release.preview_serial_for_build` | Read helper | Should not mutate. |
| `inductone_tools.serial_allocation.tranche.preview_next_serial` | Read helper | Should not mutate. |
| `inductone_tools.snapshot.hierarchy.populate_snapshot_hierarchy` | State-changing action | Populates snapshot hierarchy. Needs idempotency and permission review. |
| `inductone_tools.snapshot.hierarchy.generate_hierarchy_workbook` | State-changing/file action | Generates workbook file. Needs attachment/failure tests. |
| `inductone_tools.snapshot.hierarchy.sync_hierarchy_workbook_to_configuration_order` | State-changing action | Syncs generated workbook to CO. Needs state/precondition check. |
| `inductone_tools.snapshot_diff.loader.get_diff` | Read/report helper | Should remain read-only. |
| `inductone_tools.snapshot_diff.loader.download_diff_workbook` | File-generation/report action | Confirm whether it mutates File records; if so classify as state-changing. |
| `inductone_tools.snapshot_diff.loader.get_report_data` | Read/report helper | Should remain read-only. |

## Duplicate/legacy path review

Potential overlap to review:

- `build_completion_accept.accept_completion_create_as_built`
- `instance.acceptance.accept_completion_create_as_built`
- `builder_release.submit_as_built_now`
- `builder_release.close_build_from_as_built`

There should be one canonical acceptance path for the formal Build Completion workflow. Legacy shims can remain only if they delegate safely and cannot bypass side effects.

## Method hardening checklist

For each whitelisted method:

- [ ] Does it mutate records?
- [ ] Does it create files?
- [ ] Does it call `ignore_permissions=True`?
- [ ] Does it call `frappe.db.commit()`?
- [ ] Does it catch broad `Exception`?
- [ ] Does it enforce the caller's role?
- [ ] Does it enforce current status/state?
- [ ] Does it validate all required inputs?
- [ ] Is it idempotent, or does it block duplicate execution?
- [ ] Does it leave an audit timestamp/user?
- [ ] Is there a test or validation script?

## Desired future state

This document should eventually be generated or checked automatically. A CI or local audit script should fail if a new whitelisted method is added without:

- classification,
- permission expectation,
- test coverage plan,
- documentation update.
