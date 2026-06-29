# Downstream Loss Sweep — 2026-06-29

## Purpose

Two regressions after the role hardening had the same root cause: curated roles
had the intended top-level permissions, but downstream ERPNext dependencies were
not fully validated by executing real work.

This sweep adds repeatable evidence for:

1. Workspace/page visibility.
2. Static mandatory Link-field dependencies.
3. Effective permission losses from baseline to candidate, grouped by real
   production user.

No production site was touched. Baseline was read-only. Candidate was the only
site mutated.

## Part 1 — Operations workspace visibility fix

Discovery found that the reported "Operations Dashboard" is:

| Type | Name | Title/Label | Previous role restriction |
|---|---|---|---|
| `Workspace` | `Operations` | `Operations` | `Operations Member` |

No matching custom `Dashboard` record was found. The only Dashboard-related page
match was Frappe's standard `dashboard-view` Page.

Implemented fix:

- Added an idempotent patch:
  `inductone_tools.patches.v2026_06_29_operations_workspace_visibility`
- Added a narrow Workspace fixture allowlist for `Operations`.
- Exported `inductone_tools/fixtures/workspace.json`.

The `Operations` workspace is now restricted to:

- `Operations Manager`
- `Operations Viewer`
- `Engineering User`
- `Procurement User`
- `Finance Viewer`
- `InductOne Manager`
- `InductOne Process Architect`

It intentionally excludes `InductOne External Builder`.

Candidate evidence:

```text
C:\hub\frappe-sandbox\validation-evidence\operations_workspace_visibility_20260629T161917Z.json
```

Result:

```text
8/8 passed
```

## Part 2a — Workspace/page visibility audit

Script:

```text
scripts/run_workspace_visibility_audit.py
```

Evidence:

```text
C:\hub\frappe-sandbox\validation-evidence\workspace_visibility_audit_20260629T161943Z.json
```

Summary:

```text
workspaces=26
dashboards=8
orphaned_from_internal_roles=2
```

Flagged records:

| Type | Name | Roles | Notes |
|---|---|---|---|
| Workspace | `Quality` | `Builder` | Needs owner review. `Builder` is retired. Do not auto-fix without confirming whether Quality should be internal-visible or hidden. |
| Workspace | `Builder Portal` | `InductOne External Builder` | Expected external-builder-only page. Listed because it intentionally excludes all internal roles. |

## Part 2b — Static mandatory Link-field dependency audit

Script:

```text
scripts/run_static_link_dependency_audit.py
```

Evidence:

```text
C:\hub\frappe-sandbox\validation-evidence\static_link_dependency_audit_20260629T162008Z.json
```

Summary:

```text
checked_dependencies=118
missing_read_dependencies=28
```

Examples flagged for owner review:

- `Operations Manager`: `Stock Entry.stock_entry_type -> Stock Entry Type`
- `Inventory Operator`: `Stock Entry.stock_entry_type -> Stock Entry Type`
- `Gripper Manufacturer`: `Stock Entry.stock_entry_type -> Stock Entry Type`
- `Procurement User`: `Price List.currency -> Currency`
- `InductOne Manager`: several InductOne workflow links to `BOM`, `Sales Order`, `Item`, `Supplier`, and `User`
- `InductOne Process Architect`: several InductOne workflow links to `BOM`, `Sales Order`, `Item`, `Supplier`, and `User`

This audit is intentionally static and conservative. It does not prove a
runtime failure by itself and does not automatically justify grants.

## Part 2c — Effective permission regression diff

Script:

```text
scripts/run_effective_permission_regression_diff.py
```

Evidence:

```text
C:\hub\frappe-sandbox\validation-evidence\effective_permission_regression_diff_20260629T162316Z.json
```

Candidate was first aligned to the approved post-hardening user assignment
state. Baseline was only read.

Summary:

```text
users_with_unexpected_losses=26
unexpected_loss_count=10135
expected_loss_count=14
missing_candidate_users=2
```

Missing candidate users:

- `alyza.salinas@plusonerobotics.com`
- `quickbooks.integration@plusonerobotics.com`

These are expected because the signed production assignment plan disables them.

Expected losses:

- External builder raw `Item`/`BOM` capability loss for Motion and LAM builders.

Unexpected losses require owner classification. Many are likely intentional
because the baseline included broad/Super/Profile access and candidate has
scoped roles. The full grouped report is in the JSON evidence.

Grouped summary:

| User | Lost capabilities | Distinct DocTypes |
|---|---:|---:|
| `austin.dominguez@plusonerobotics.com` | 11 | 8 |
| `ben.garishodge@plusonerobotics.com` | 2 | 1 |
| `christina.gt@plusonerobotics.com` | 1612 | 441 |
| `david.brain@plusonerobotics.com` | 5 | 4 |
| `david.moreno@plusonerobotics.com` | 83 | 24 |
| `gilbert.bailey@plusonerobotics.com` | 11 | 8 |
| `hana.macinnis@plusonerobotics.com` | 14 | 9 |
| `ian.deliz@plusonerobotics.com` | 676 | 160 |
| `james.nelson@plusonerobotics.com` | 11 | 8 |
| `jason.minica@plusonerobotics.com` | 83 | 24 |
| `jim.haws@plusonerobotics.com` | 4 | 3 |
| `lam@plusonerobotics.com` | 75 | 21 |
| `manuel.carvalho@plusonerobotics.com` | 11 | 8 |
| `manuel.cortez@plusonerobotics.com` | 11 | 8 |
| `mariafernanda.amaya@plusonerobotics.com` | 11 | 8 |
| `marina.lobo@plusonerobotics.com` | 11 | 8 |
| `matt.speer@plusonerobotics.com` | 1696 | 441 |
| `matthew.mcmillan@plusonerobotics.com` | 1720 | 443 |
| `michael.king@plusonerobotics.com` | 550 | 148 |
| `motion.builder@plusonerobotics.com` | 75 | 21 |
| `nathaniel.pantuso@plusonerobotics.com` | 1637 | 441 |
| `patty.gomez@plusonerobotics.com` | 1637 | 441 |
| `ryan.hannon@plusonerobotics.com` | 12 | 9 |
| `shaun.edwards@plusonerobotics.com` | 83 | 24 |
| `wayne.kirk@plusonerobotics.com` | 83 | 24 |
| `zohair.naqvi@plusonerobotics.com` | 11 | 8 |

## Next owner-review gates

1. Classify each 2c user loss group as intended vs regression.
2. Review the 28 static Link dependency findings. Promote only execution-proven
   or clearly required dependencies into role grants.
3. Decide whether the `Quality` Workspace should be made visible to internal
   roles, assigned to a replacement role, or hidden/retired.
