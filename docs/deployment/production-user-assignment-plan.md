# Production User Assignment Plan

This plan is the approval artifact for assigning production users to the hardened modular role model. It is not a deployment plan and does not authorize production mutation by itself.

Source evidence:

- Candidate sandbox restored from production backup.
- Broad Role Profile query evidence: `C:\hub\frappe-sandbox\validation-evidence\broad_role_profile_query.json`

## Section 1: Confirmed user-to-role assignments

| User | Target roles | Notes |
|---|---|---|
| `michael.king@plusonerobotics.com` | `InductOne Process Architect`, `InductOne Manager`, `Engineering User`, `Operations Manager` | System owner |
| `christina.gt@plusonerobotics.com` | `InductOne Manager`, `Engineering User`, `Operations Manager` |  |
| `jim.haws@plusonerobotics.com` | `InductOne Manager`, `Operations Manager` |  |
| `david.brain@plusonerobotics.com` | `InductOne Manager`, `Engineering User`, `Operations Manager` |  |
| `shaun.edwards@plusonerobotics.com` | `Engineering User` |  |
| `jason.minica@plusonerobotics.com` | `Engineering User` |  |
| `wayne.kirk@plusonerobotics.com` | `Engineering User` |  |
| `david.moreno@plusonerobotics.com` | `Engineering User` |  |
| `motion.builder@plusonerobotics.com` | `InductOne External Builder` | Supplier-scoped to `Motion Controls` |
| `lam@plusonerobotics.com` | `InductOne External Builder` | Supplier-scoped to `LAM` |
| `ian.deliz@plusonerobotics.com` | `System Manager` | System owner decision: should be System Manager; clear `Super` Role Profile and assign deliberate system-admin access. |
| `matt.speer@plusonerobotics.com` | `Finance Viewer` | System owner decision: finance. |
| `matthew.mcmillan@plusonerobotics.com` | `Procurement User` | System owner decision: procurement. |
| `nathaniel.pantuso@plusonerobotics.com` | `Operations Manager`, `Gripper Manufacturer` | System owner decision: operations user and gripper workflows. |
| `patty.gomez@plusonerobotics.com` | `Operations Manager` | System owner decision: operations manager. |

### Additional production users not listed above — system owner to complete before deployment approval

The system owner must review all enabled production users before approving deployment. Any production user not listed above must be explicitly mapped to one or more target roles, assigned a non-broad Role Profile, or intentionally left without ERPNext role changes.

## Section 2: Broad Role Profiles to clear

Candidate was queried for enabled users whose `role_profile_name` is one of `Super`, `System Manager`, or `All`. Every listed user requires the action below before or during deployment.

| User | Current broad Role Profile | Required action |
|---|---|---|
| `alyza.salinas@plusonerobotics.com` | `Super` | System owner decision: delete. Disable/delete user before or during deployment; verify no active user remains with `Super`. |
| `ian.deliz@plusonerobotics.com` | `Super` | System owner decision: should be System Manager. Clear `Super` Role Profile; assign deliberate `System Manager` access instead. |
| `matt.speer@plusonerobotics.com` | `Super` | System owner decision: finance. Clear `Super` Role Profile; assign `Finance Viewer`. |
| `matthew.mcmillan@plusonerobotics.com` | `Super` | System owner decision: procurement. Clear `Super` Role Profile; assign `Procurement User`. |
| `nathaniel.pantuso@plusonerobotics.com` | `Super` | System owner decision: operations user and gripper workflows. Clear `Super` Role Profile; assign `Operations Manager` and `Gripper Manufacturer`. |
| `patty.gomez@plusonerobotics.com` | `Super` | System owner decision: operations manager. Clear `Super` Role Profile; assign `Operations Manager`. |
| `quickbooks.integration@plusonerobotics.com` | `Super` | System owner decision: only used to sync QuickBooks but never completed; can remove. Disable/delete service account before or during deployment unless a current QuickBooks sync owner re-justifies it. Candidate test requirement if permissions are reduced instead of disabling: confirm the account has no InductOne roles, no `Super`, no `System Manager`, and can perform only the explicitly approved QuickBooks sync calls. |

## Section 3: Roles that must be absent post-deployment

The migration patch removes retired/legacy roles from users. Post-deploy verification must confirm no enabled production user holds:

- `Builder`
- `InductOne Process Manager`
- `InductOne Architect`
- `Engineering Signoff Delegate`
- `Part Number Manager`
- `Engineering - Signoff`
- `OPS-INDUCTONE-GATEKEEP`
- `PRODUCT-INDUCTONE-GATEKEEP`

## Approval required before production deployment

This plan must be reviewed and confirmed by the system owner before
the production migration is run.

Approved by: ___________________________  Date: ___________
