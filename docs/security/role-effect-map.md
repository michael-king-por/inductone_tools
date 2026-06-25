# Role Effect Map

This file records where role names have behavior in the repo. It exists because Frappe roles affect more than user assignment: they can gate server methods, client buttons, DocPerm rows, embedded DocType permissions, role profiles, workspace visibility, and user permissions.

Generated/updated during the June 2026 hardening work. Treat this as an audit index, not as proof that every target role is fully validated in a live site.

## Findings summary

- Server-side role gates exist in Python and must be migrated deliberately; these are security boundaries.
- Client Script role checks exist; these control button visibility only and must match server gates, but cannot be the only protection.
- Custom DocPerm fixtures now carry the target InductOne permission model.
- Embedded DocType permissions still exist in `doctype.json`; these can preserve or reintroduce permissions outside `custom_docperm.json`.
- Role Profiles are fixture-managed definitions only; assigning profiles to users remains database-side operational state.
- ERPNext standard roles carry large built-in effects that are not fully visible from this app repo. Operations/Finance/Inventory/Procurement standard access must be tested in the candidate sandbox.

## Role references

| Effect type | Location | Line | Role | Effect / note |
|---|---|---:|---|---|
| client-script | `InductOne Build Completion Script` |  | `Builder` | Client Script gates/buttons reference role |
| client-script | `InductOne Build HTML Controls` |  | `Builder` | Client Script gates/buttons reference role |
| client-script | `InductOne Build Script` |  | `Builder` | Client Script gates/buttons reference role |
| client-script | `Load Catalog Options - Enforce Group-of Exclusivity` |  | `Builder` | Client Script gates/buttons reference role |
| client-script | `Engineering Signoff Actions` |  | `Engineering User` | Client Script gates/buttons reference role |
| client-script | `Engineering Signoff Banner - Configuration Option` |  | `Engineering User` | Client Script gates/buttons reference role |
| client-script | `Engineering Signoff Banner - Item` |  | `Engineering User` | Client Script gates/buttons reference role |
| client-script | `InductOne Configuration Option Review Button` |  | `Engineering User` | Client Script gates/buttons reference role |
| client-script | `Part Number Allocation Request - Allocate Numbers Button` |  | `Engineering User` | Client Script gates/buttons reference role |
| client-script | `Engineering Signoff Actions` |  | `System Manager` | Client Script gates/buttons reference role |
| client-script | `Part Number Allocation Request - Allocate Numbers Button` |  | `System Manager` | Client Script gates/buttons reference role |
| custom-docperm | `BOM Export Package` |  | `Engineering User` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `Configured BOM Snapshot` |  | `Engineering User` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `Engineering Signoff` |  | `Engineering User` | r=1 w=1 c=1 s=0 x=0 d=0 |
| custom-docperm | `InductOne As-Built Record` |  | `Engineering User` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Build` |  | `Engineering User` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Configuration Option` |  | `Engineering User` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Configuration Order` |  | `Engineering User` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Instance` |  | `Engineering User` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `Part Number Allocation Request` |  | `Engineering User` | r=1 w=1 c=1 s=0 x=0 d=0 |
| custom-docperm | `Part Number Assignment` |  | `Engineering User` | r=1 w=1 c=1 s=0 x=0 d=0 |
| custom-docperm | `BOM Export Package` |  | `Finance Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `Configured BOM Snapshot` |  | `Finance Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `Engineering Signoff` |  | `Finance Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `Fixture Export Control` |  | `Finance Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne As-Built Record` |  | `Finance Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Build` |  | `Finance Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Build Completion` |  | `Finance Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Builder Tranche` |  | `Finance Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Configuration Option` |  | `Finance Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Configuration Order` |  | `Finance Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Instance` |  | `Finance Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `Part Number Allocation Request` |  | `Finance Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `Part Number Assignment` |  | `Finance Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `BOM Export Package` |  | `InductOne External Builder` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `Configured BOM Snapshot` |  | `InductOne External Builder` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Build Completion` |  | `InductOne External Builder` | r=1 w=1 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Configuration Order` |  | `InductOne External Builder` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `BOM Export Package` |  | `InductOne Manager` | r=1 w=1 c=1 s=0 x=0 d=0 |
| custom-docperm | `Configured BOM Snapshot` |  | `InductOne Manager` | r=1 w=1 c=1 s=0 x=0 d=0 |
| custom-docperm | `InductOne As-Built Record` |  | `InductOne Manager` | r=1 w=1 c=1 s=0 x=0 d=0 |
| custom-docperm | `InductOne Build` |  | `InductOne Manager` | r=1 w=1 c=1 s=0 x=0 d=0 |
| custom-docperm | `InductOne Build Completion` |  | `InductOne Manager` | r=1 w=1 c=1 s=0 x=0 d=0 |
| custom-docperm | `InductOne Configuration Order` |  | `InductOne Manager` | r=1 w=1 c=1 s=0 x=0 d=0 |
| custom-docperm | `InductOne Instance` |  | `InductOne Manager` | r=1 w=1 c=1 s=0 x=0 d=0 |
| custom-docperm | `BOM Export Package` |  | `InductOne Process Architect` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `Configured BOM Snapshot` |  | `InductOne Process Architect` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `Engineering Signoff` |  | `InductOne Process Architect` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `Fixture Export Control` |  | `InductOne Process Architect` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `InductOne As-Built Record` |  | `InductOne Process Architect` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `InductOne Build` |  | `InductOne Process Architect` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `InductOne Build Completion` |  | `InductOne Process Architect` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `InductOne Builder Tranche` |  | `InductOne Process Architect` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `InductOne Configuration Option` |  | `InductOne Process Architect` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `InductOne Configuration Order` |  | `InductOne Process Architect` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `InductOne Instance` |  | `InductOne Process Architect` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `Part Number Allocation Request` |  | `InductOne Process Architect` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `Part Number Assignment` |  | `InductOne Process Architect` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `BOM Export Package` |  | `Operations Manager` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `Configured BOM Snapshot` |  | `Operations Manager` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne As-Built Record` |  | `Operations Manager` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Build` |  | `Operations Manager` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Build Completion` |  | `Operations Manager` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Configuration Order` |  | `Operations Manager` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Instance` |  | `Operations Manager` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `BOM Export Package` |  | `Operations Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `Configured BOM Snapshot` |  | `Operations Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `Engineering Signoff` |  | `Operations Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `Fixture Export Control` |  | `Operations Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne As-Built Record` |  | `Operations Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Build` |  | `Operations Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Build Completion` |  | `Operations Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Builder Tranche` |  | `Operations Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Configuration Option` |  | `Operations Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Configuration Order` |  | `Operations Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `InductOne Instance` |  | `Operations Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `Part Number Allocation Request` |  | `Operations Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `Part Number Assignment` |  | `Operations Viewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| custom-docperm | `BOM Export Package` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `Configured BOM Snapshot` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `InductOne Build Completion` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `InductOne Configuration Option` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| custom-docperm | `InductOne Configuration Order` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `Engineering Signoff` |  | `Engineering User` | r=1 w=1 c=1 s=0 x=0 d=0 |
| doctype-embedded-perm | `Part Number Allocation Request` |  | `Engineering User` | r=1 w=1 c=1 s=0 x=0 d=0 |
| doctype-embedded-perm | `Part Number Assignment` |  | `Engineering User` | r=1 w=1 c=1 s=0 x=0 d=0 |
| doctype-embedded-perm | `BOM Export Package` |  | `Manufacturing User` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `Part Number Allocation Request` |  | `Part Number Reviewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| doctype-embedded-perm | `Part Number Assignment` |  | `Part Number Reviewer` | r=1 w=0 c=0 s=0 x=0 d=0 |
| doctype-embedded-perm | `BOM Export Package` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `Configured BOM Snapshot` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `Engineering Signoff` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `Fixture Export Control` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `InductOne As-Built Record` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `InductOne Build` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `InductOne Build Completion` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `InductOne Builder Tranche` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `InductOne Configuration Option` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `InductOne Configuration Order` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `InductOne Instance` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `InductOne Options Catalog` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `POR Controlled Document` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `POR Physical Location` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `Part Number Allocation Request` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| doctype-embedded-perm | `Part Number Assignment` |  | `System Manager` | r=1 w=1 c=1 s=0 x=0 d=1 |
| role-profile | `Engineering User` |  | `Engineering User` | profile includes role |
| role-profile | `Finance Viewer` |  | `Finance Viewer` | profile includes role |
| role-profile | `Gripper Manufacturer` |  | `Gripper Manufacturer` | profile includes role |
| role-profile | `InductOne External Builder` |  | `InductOne External Builder` | profile includes role |
| role-profile | `InductOne Manager` |  | `InductOne Manager` | profile includes role |
| role-profile | `InductOne Process Architect` |  | `InductOne Process Architect` | profile includes role |
| role-profile | `Inventory Operator` |  | `Inventory Operator` | profile includes role |
| role-profile | `Operations Manager` |  | `Operations Manager` | profile includes role |
| role-profile | `Operations Viewer` |  | `Operations Viewer` | profile includes role |
| role-profile | `Procurement User` |  | `Procurement User` | profile includes role |
| server/code | `inductone_tools/build_completion.py` | 23 | `Builder` | Called from the Upload Builder Completion dialog on the InductOne Build form. |
| server/code | `inductone_tools/build_completion_accept.py` | 61 | `Builder` | "Open the Build and use 'Allocate Serial' from the Builder Tranche." |
| server/code | `inductone_tools/build_completion_workbook_parser.py` | 133 | `Builder` | "template and filled in the Builder Input sheet." |
| server/code | `inductone_tools/build_completion_workbook_parser.py` | 2 | `Builder` | Parser for the OPS-BLD-F01 Builder Serial Workbook. |
| server/code | `inductone_tools/build_completion_workbook_parser.py` | 32 | `Builder` | "Builder Organization", |
| server/code | `inductone_tools/build_completion_workbook_parser.py` | 33 | `Builder` | "Builder Point of Contact", |
| server/code | `inductone_tools/build_completion_workbook_parser.py` | 34 | `Builder` | "Builder Point of Contact Email", |
| server/code | `inductone_tools/build_completion_workbook_parser.py` | 38 | `Builder` | "Builder Signature (Typed Full Name)", |
| server/code | `inductone_tools/build_completion_workbook_parser.py` | 4 | `Builder` | The workbook has a known structure (Builder Input sheet, column A labels, |
| server/code | `inductone_tools/build_completion_workbook_parser.py` | 77 | `Builder` | if "Builder Input" not in wb.sheetnames: |
| server/code | `inductone_tools/build_completion_workbook_parser.py` | 79 | `Builder` | "Workbook is missing the required 'Builder Input' sheet. " |
| server/code | `inductone_tools/build_completion_workbook_parser.py` | 83 | `Builder` | ws = wb["Builder Input"] |
| server/code | `inductone_tools/builder_release.py` | 324 | `Builder` | _set_if_present(build, ["as_built_status"], "Pending Builder Submission") |
| server/code | `inductone_tools/builder_release.py` | 35 | `Builder` | missing.append("Builder (Supplier) is not set on the build.") |
| server/code | `inductone_tools/builder_release.py` | 405 | `Builder` | title=f"Builder acknowledgement - {build_name}", |
| server/code | `inductone_tools/builder_release.py` | 444 | `Builder` | fname = f"{build.name}_Builder_Serial_Confirmation_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.xlsx" |
| server/code | `inductone_tools/builder_release.py` | 461 | `Builder` | title=f"Builder Serial Capture Workbook - {build.name}", |
| server/code | `inductone_tools/builder_release.py` | 532 | `Builder` | The Configuration Order PDF and Builder Instructions print format |
| server/code | `inductone_tools/builder_release.py` | 572 | `Builder` | f"Builder Workbook:     {workbook_url}", |
| server/code | `inductone_tools/builder_release.py` | 586 | `Builder` | frappe.throw(f"Builder serial workbook template not found at: {template_path}") |
| server/code | `inductone_tools/builder_release.py` | 590 | `Builder` | if "Builder Input" not in wb.sheetnames: |
| server/code | `inductone_tools/builder_release.py` | 591 | `Builder` | frappe.throw("Builder serial workbook template is missing required sheet: Builder Input") |
| server/code | `inductone_tools/builder_release.py` | 593 | `Builder` | ws = wb["Builder Input"] |
| server/code | `inductone_tools/builder_release.py` | 616 | `Builder` | "Builder Organization": builder_org, |
| server/code | `inductone_tools/builder_release.py` | 617 | `Builder` | "Builder Point of Contact": builder_poc, |
| server/code | `inductone_tools/builder_release.py` | 618 | `Builder` | "Builder Point of Contact Email": builder_poc_email, |
| server/code | `inductone_tools/builder_release.py` | 938 | `Builder` | note = f"Builder release manifest for build {build_name}" |
| server/code | `inductone_tools/builder_release.py` | 947 | `Builder` | title=f"Builder Release Manifest - {build_name}", |
| server/code | `inductone_tools/external_builder_permissions.py` | 12 | `Builder` | EXTERNAL_BUILDER_ROLE = "InductOne External Builder" |
| server/code | `inductone_tools/hooks.py` | 111 | `Builder` | "InductOne External Builder", |
| server/code | `inductone_tools/hooks.py` | 135 | `Builder` | "InductOne Builder Tranche", |
| server/code | `inductone_tools/hooks.py` | 57 | `Builder` | "InductOne Builder Tranche": { |
| server/code | `inductone_tools/hooks.py` | 94 | `Builder` | "InductOne External Builder", |
| server/code | `inductone_tools/instance/backfill.py` | 123 | `Builder` | "workbook). Builder release, acceptance, and audit trail " |
| server/code | `inductone_tools/instance/creation.py` | 131 | `Builder` | FROM `tabInductOne Builder Tranche` |
| server/code | `inductone_tools/instance/creation.py` | 56 | `Builder` | "Allocate via the Builder Tranche system before retrying." |
| server/code | `inductone_tools/instance/hooks.py` | 22 | `Builder` | #   At Builder      -> Ready for Ship   (builder-intake unit becomes certified built) |
| server/code | `inductone_tools/instance/hooks.py` | 28 | `Builder` | # NOTE: 'At Builder' is a real status option on the Instance.status field |
| server/code | `inductone_tools/instance/hooks.py` | 30 | `Builder` | # this validator would block every At Builder -> Ready for Ship transition. |
| server/code | `inductone_tools/instance/hooks.py` | 32 | `Builder` | "At Builder": {"Ready for Ship"}, |
| server/code | `inductone_tools/instance/hooks.py` | 40 | `Builder` | # created directly as 'At Builder'; we don't force a starting state. |
| server/code | `inductone_tools/instance/hooks.py` | 67 | `Builder` | "Serials are allocated by InductOne Builder Tranche." |
| server/code | `inductone_tools/instance/hooks.py` | 82 | `Builder` | to be created as 'At Builder', without walking the full lifecycle. The |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 121 | `Builder` | role_profile = "InductOne External Builder" |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 133 | `Builder` | doc.append("roles", {"role": "InductOne External Builder"}) |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 180 | `Builder` | """Stop using the generic Builder role for InductOne supplier access.""" |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 185 | `Builder` | filters={"parenttype": "User", "role": "Builder"}, |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 189 | `Builder` | remove_role(row.parent, "Builder") |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 204 | `Builder` | frappe.db.set_value("User", user, "role_profile_name", "InductOne External Builder") |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 206 | `Builder` | remove_role(user, "Builder") |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 207 | `Builder` | add_role(user, "InductOne External Builder") |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 222 | `Builder` | """Move builder-facing workspaces from the old Builder role to the new role.""" |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 224 | `Builder` | if frappe.db.exists("Workspace", "Builder Portal"): |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 225 | `Builder` | doc = frappe.get_doc("Workspace", "Builder Portal") |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 228 | `Builder` | doc.append("roles", {"role": "InductOne External Builder"}) |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 284 | `Builder` | {"parent": doctype, "role": "Builder", "permlevel": 0}, |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 300 | `Builder` | "InductOne Builder Tranche", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 316 | `Builder` | ensure_custom_docperm(doctype, "InductOne External Builder", **external_read) |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 320 | `Builder` | "InductOne External Builder", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 359 | `Builder` | "InductOne Builder Tranche", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 410 | `Builder` | "InductOne Builder Tranche", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 42 | `Builder` | "InductOne External Builder", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 64 | `Builder` | "InductOne External Builder": set(EXTERNAL_BUILDERS), |
| server/code | `inductone_tools/serial_allocation/tranche.py` | 146 | `Builder` | FROM `tabInductOne Builder Tranche` |
| server/code | `inductone_tools/serial_allocation/tranche.py` | 158 | `Builder` | "Builder {0} has no active InductOne Builder Tranche. " |
| server/code | `inductone_tools/serial_allocation/tranche.py` | 166 | `Builder` | tranche = frappe.get_doc("InductOne Builder Tranche", row["name"]) |
| server/code | `inductone_tools/serial_allocation/tranche.py` | 175 | `Builder` | "Builder {0} has no available serial numbers — all active tranches " |
| server/code | `inductone_tools/serial_allocation/tranche.py` | 2 | `Builder` | Server-side logic for InductOne Builder Tranche, plus the serial allocator. |
| server/code | `inductone_tools/serial_allocation/tranche.py` | 209 | `Builder` | "InductOne Builder Tranche", |
| server/code | `inductone_tools/serial_allocation/tranche.py` | 27 | `Builder` | Validation entry point for InductOne Builder Tranche. |
| server/code | `inductone_tools/serial_allocation/tranche.py` | 30 | `Builder` | doc_events["InductOne Builder Tranche"]["validate"]. |
| server/code | `inductone_tools/serial_allocation/tranche.py` | 4 | `Builder` | InductOne Builder Tranche is a custom DocType. On Frappe Cloud, custom |
| server/code | `inductone_tools/serial_allocation/tranche.py` | 76 | `Builder` | FROM `tabInductOne Builder Tranche` |
| server/code | `inductone_tools/serial_allocation/tranche.py` | 9 | `Builder` | - validate_tranche: doc_events validate hook for InductOne Builder Tranche |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 57 | `Engineering Signoff Delegate` | "Engineering Signoff Delegate", |
| server/code | `inductone_tools/builder_release.py` | 1086 | `Engineering User` | f"Obtain approval from an Engineering User role holder before releasing." |
| server/code | `inductone_tools/builder_release.py` | 158 | `Engineering User` | f"Obtain approval from an Engineering User role holder before releasing." |
| server/code | `inductone_tools/engineering_signoff.py` | 112 | `Engineering User` | Approve a Pending signoff. Restricted to Engineering User role. |
| server/code | `inductone_tools/engineering_signoff.py` | 207 | `Engineering User` | Reject a Pending signoff. Restricted to Engineering User role. |
| server/code | `inductone_tools/engineering_signoff.py` | 264 | `Engineering User` | Restricted to Engineering User role: superseding a released, |
| server/code | `inductone_tools/engineering_signoff.py` | 670 | `Engineering User` | if not {"Engineering User", "InductOne Process Architect", "System Manager"} & set(user_roles): |
| server/code | `inductone_tools/engineering_signoff.py` | 672 | `Engineering User` | _("This action requires the 'Engineering User' role."), |
| server/code | `inductone_tools/hooks.py` | 101 | `Engineering User` | "Engineering User", |
| server/code | `inductone_tools/hooks.py` | 118 | `Engineering User` | "Engineering User", |
| server/code | `inductone_tools/part_numbering.py` | 36 | `Engineering User` | return bool({"Engineering User", "InductOne Process Architect", "System Manager"} & roles) |
| server/code | `inductone_tools/part_numbering.py` | 42 | `Engineering User` | _("Only users with Engineering User or InductOne Process Architect role may allocate part numbers."), |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 382 | `Engineering User` | ensure_custom_docperm("Engineering Signoff", "Engineering User", **signoff) |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 395 | `Engineering User` | ensure_custom_docperm(doctype, "Engineering User", **part_number) |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 426 | `Engineering User` | ensure_custom_docperm(doctype, "Engineering User", **read_only) |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 49 | `Engineering User` | "Engineering User", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 67 | `Engineering User` | "Engineering User": PART_NUMBER_MANAGERS / ENGINEERING_DELEGATES, |
| server/code | `inductone_tools/external_builder_permissions.py` | 19 | `Finance Viewer` | "Finance Viewer", |
| server/code | `inductone_tools/hooks.py` | 102 | `Finance Viewer` | "Finance Viewer", |
| server/code | `inductone_tools/hooks.py` | 119 | `Finance Viewer` | "Finance Viewer", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 414 | `Finance Viewer` | ensure_custom_docperm(doctype, "Finance Viewer", **read_only) |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 50 | `Finance Viewer` | "Finance Viewer", |
| server/code | `inductone_tools/hooks.py` | 100 | `Gripper Manufacturer` | "Gripper Manufacturer", |
| server/code | `inductone_tools/hooks.py` | 117 | `Gripper Manufacturer` | "Gripper Manufacturer", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 48 | `Gripper Manufacturer` | "Gripper Manufacturer", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 56 | `InductOne Architect` | "InductOne Architect", |
| server/code | `inductone_tools/external_builder_permissions.py` | 12 | `InductOne External Builder` | EXTERNAL_BUILDER_ROLE = "InductOne External Builder" |
| server/code | `inductone_tools/hooks.py` | 111 | `InductOne External Builder` | "InductOne External Builder", |
| server/code | `inductone_tools/hooks.py` | 94 | `InductOne External Builder` | "InductOne External Builder", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 121 | `InductOne External Builder` | role_profile = "InductOne External Builder" |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 133 | `InductOne External Builder` | doc.append("roles", {"role": "InductOne External Builder"}) |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 204 | `InductOne External Builder` | frappe.db.set_value("User", user, "role_profile_name", "InductOne External Builder") |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 207 | `InductOne External Builder` | add_role(user, "InductOne External Builder") |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 228 | `InductOne External Builder` | doc.append("roles", {"role": "InductOne External Builder"}) |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 316 | `InductOne External Builder` | ensure_custom_docperm(doctype, "InductOne External Builder", **external_read) |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 320 | `InductOne External Builder` | "InductOne External Builder", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 42 | `InductOne External Builder` | "InductOne External Builder", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 64 | `InductOne External Builder` | "InductOne External Builder": set(EXTERNAL_BUILDERS), |
| server/code | `inductone_tools/hooks.py` | 112 | `InductOne Manager` | "InductOne Manager", |
| server/code | `inductone_tools/hooks.py` | 95 | `InductOne Manager` | "InductOne Manager", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 345 | `InductOne Manager` | ensure_custom_docperm(doctype, "InductOne Manager", **process) |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 43 | `InductOne Manager` | "InductOne Manager", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 65 | `InductOne Manager` | "InductOne Manager": PROCESS_MANAGERS, |
| server/code | `inductone_tools/engineering_signoff.py` | 670 | `InductOne Process Architect` | if not {"Engineering User", "InductOne Process Architect", "System Manager"} & set(user_roles): |
| server/code | `inductone_tools/external_builder_permissions.py` | 16 | `InductOne Process Architect` | "InductOne Process Architect", |
| server/code | `inductone_tools/hooks.py` | 113 | `InductOne Process Architect` | "InductOne Process Architect", |
| server/code | `inductone_tools/hooks.py` | 96 | `InductOne Process Architect` | "InductOne Process Architect", |
| server/code | `inductone_tools/part_numbering.py` | 36 | `InductOne Process Architect` | return bool({"Engineering User", "InductOne Process Architect", "System Manager"} & roles) |
| server/code | `inductone_tools/part_numbering.py` | 42 | `InductOne Process Architect` | _("Only users with Engineering User or InductOne Process Architect role may allocate part numbers."), |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 369 | `InductOne Process Architect` | ensure_custom_docperm(doctype, "InductOne Process Architect", **architect) |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 44 | `InductOne Process Architect` | "InductOne Process Architect", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 66 | `InductOne Process Architect` | "InductOne Process Architect": {"michael.king@plusonerobotics.com"}, |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 55 | `InductOne Process Manager` | "InductOne Process Manager", |
| server/code | `inductone_tools/external_builder_permissions.py` | 18 | `Inventory Operator` | "Inventory Operator", |
| server/code | `inductone_tools/hooks.py` | 116 | `Inventory Operator` | "Inventory Operator", |
| server/code | `inductone_tools/hooks.py` | 99 | `Inventory Operator` | "Inventory Operator", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 47 | `Inventory Operator` | "Inventory Operator", |
| server/code | `inductone_tools/external_builder_permissions.py` | 25 | `Item Manager` | "Item Manager", |
| server/code | `inductone_tools/external_builder_permissions.py` | 22 | `Manufacturing Manager` | "Manufacturing Manager", |
| server/code | `inductone_tools/external_builder_permissions.py` | 21 | `Manufacturing User` | "Manufacturing User", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 205 | `Manufacturing User` | remove_role(user, "Manufacturing User") |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 287 | `Manufacturing User` | for role in LEGACY_INDUCTONE_ROLES / {"Manufacturing User", "Project Manager", "Projects Manager"}: |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 59 | `OPS-INDUCTONE-GATEKEEP` | "OPS-INDUCTONE-GATEKEEP", |
| server/code | `inductone_tools/external_builder_permissions.py` | 17 | `Operations Manager` | "Operations Manager", |
| server/code | `inductone_tools/hooks.py` | 115 | `Operations Manager` | "Operations Manager", |
| server/code | `inductone_tools/hooks.py` | 98 | `Operations Manager` | "Operations Manager", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 427 | `Operations Manager` | ensure_custom_docperm(doctype, "Operations Manager", **read_only) |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 46 | `Operations Manager` | "Operations Manager", |
| server/code | `inductone_tools/hooks.py` | 114 | `Operations Viewer` | "Operations Viewer", |
| server/code | `inductone_tools/hooks.py` | 97 | `Operations Viewer` | "Operations Viewer", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 413 | `Operations Viewer` | ensure_custom_docperm(doctype, "Operations Viewer", **read_only) |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 45 | `Operations Viewer` | "Operations Viewer", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 60 | `PRODUCT-INDUCTONE-GATEKEEP` | "PRODUCT-INDUCTONE-GATEKEEP", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 58 | `Part Number Manager` | "Part Number Manager", |
| server/code | `inductone_tools/external_builder_permissions.py` | 20 | `Procurement User` | "Procurement User", |
| server/code | `inductone_tools/hooks.py` | 103 | `Procurement User` | "Procurement User" |
| server/code | `inductone_tools/hooks.py` | 120 | `Procurement User` | "Procurement User" |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 51 | `Procurement User` | "Procurement User", |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 287 | `Project Manager` | for role in LEGACY_INDUCTONE_ROLES / {"Manufacturing User", "Project Manager", "Projects Manager"}: |
| server/code | `inductone_tools/patches/v2026_06_23_external_builder_permissions.py` | 287 | `Projects Manager` | for role in LEGACY_INDUCTONE_ROLES / {"Manufacturing User", "Project Manager", "Projects Manager"}: |
| server/code | `inductone_tools/external_builder_permissions.py` | 27 | `Purchase Manager` | "Purchase Manager", |
| server/code | `inductone_tools/external_builder_permissions.py` | 26 | `Purchase User` | "Purchase User", |
| server/code | `inductone_tools/external_builder_permissions.py` | 29 | `Sales Manager` | "Sales Manager", |
| server/code | `inductone_tools/external_builder_permissions.py` | 28 | `Sales User` | "Sales User", |
| server/code | `inductone_tools/external_builder_permissions.py` | 24 | `Stock Manager` | "Stock Manager", |
| server/code | `inductone_tools/external_builder_permissions.py` | 23 | `Stock User` | "Stock User", |
| server/code | `inductone_tools/engineering_signoff.py` | 670 | `System Manager` | if not {"Engineering User", "InductOne Process Architect", "System Manager"} & set(user_roles): |
| server/code | `inductone_tools/external_builder_permissions.py` | 15 | `System Manager` | "System Manager", |
| server/code | `inductone_tools/fixture_sync.py` | 39 | `System Manager` | # Permission gate: only System Manager may push code-bearing fixtures. |
| server/code | `inductone_tools/fixture_sync.py` | 40 | `System Manager` | if "System Manager" not in frappe.get_roles(frappe.session.user): |
| server/code | `inductone_tools/fixture_sync.py` | 41 | `System Manager` | frappe.throw("Only System Managers can export and push fixtures.") |
| server/code | `inductone_tools/part_numbering.py` | 36 | `System Manager` | return bool({"Engineering User", "InductOne Process Architect", "System Manager"} & roles) |

## Required follow-up

Before production deployment, compare this file against candidate-sandbox effective permissions for each representative user. Pay special attention to embedded DocType permissions and ERPNext standard roles, because they can carry access that is not obvious from the custom role fixtures.
