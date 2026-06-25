# Role Migration and Validation Gameplan

This is the execution plan for moving from accumulated/sandwiched ERPNext roles to the hardened modular role model.

The plan is intentionally staged. The goal is not merely to make permissions "look right" in fixtures. The goal is to prove that each role can do exactly what the wiki and business process say it should do, and cannot do what it should not do.

## Target outcome

After completion:

1. The repo defines the target roles, role profiles, custom DocPerms, and server-side gates.
2. The live database assigns users to those roles deliberately.
3. Legacy InductOne authority roles no longer grant access.
4. Broad Role Profiles like `Super` no longer hide who can do what.
5. Every documented workflow has a tested responsible role.
6. Every critical state-changing method has a server-side gate.
7. Candidate sandbox evidence exists before production deployment.

## Target roles

| Role | Purpose |
|---|---|
| `InductOne Manager` | Normal InductOne build execution. |
| `InductOne Process Architect` | InductOne system/process ownership. |
| `Operations Viewer` | Broad read-only operational visibility. |
| `Operations Manager` | Normal ERPNext operations management, including Sales Order submission. |
| `Inventory Operator` | Inventory movement workflows. |
| `Gripper Manufacturer` | Serialized gripper work orders/refurbishments. |
| `Engineering User` | Engineering signoff and part-number allocation. |
| `InductOne External Builder` | Supplier-scoped builder portal/handoff access. |
| `Finance Viewer` | Broad read-only finance/audit visibility. |
| `Procurement User` | Procurement-facing vendor/pricing/descriptive item maintenance. |

## Non-target / legacy roles

These may still exist during transition, but must not be the final authority layer:

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
- broad Role Profile `Super`

## Local/candidate sandbox assumptions

Current local sandbox layout:

| Purpose | Value |
|---|---|
| Candidate bench | `/home/michaelplusone/frappe-sandbox/benches/candidate-bench` |
| Candidate site | `inductone-candidate.localhost` |
| Candidate URL | `http://inductone-candidate.localhost:8000` |
| Baseline bench | `/home/michaelplusone/frappe-sandbox/benches/baseline-bench` |
| Baseline site | `inductone-baseline.localhost` |
| Baseline URL | `http://inductone-baseline.localhost:8010` |
| Bench executable | `/home/michaelplusone/.venvs/frappe-bench/bin/bench` |

If these change, update this document before running the plan.

## Phase 0 — preflight safety

Run from PowerShell:

```powershell
Set-Location "C:\Users\MichaelKing\OneDrive - Plus One Robotics\Documents\GitHub\inductone_tools"
git status --short
git diff --stat
```

Expected:

- Local changes are understood.
- Nothing has been pushed.
- Any unrelated user changes are noted before proceeding.

Run fixture/static checks:

```powershell
Set-Location "C:\Users\MichaelKing\OneDrive - Plus One Robotics\Documents\GitHub\inductone_tools"

python - <<'PY'
import json
from pathlib import Path
for p in Path("inductone_tools/fixtures").glob("*.json"):
    json.loads(p.read_text(encoding="utf-8"))
    print("OK", p)
PY

python -m compileall inductone_tools
```

Expected:

- All fixture JSON parses.
- Python compiles.

## Phase 1 — apply local repo to candidate sandbox

Use the existing candidate clone for early structural testing. Before final
go/no-go validation, restore a fresh production database/files backup into the
candidate bench. This is required because users, Role Profiles, User
Permissions, wiki pages, and operational records are database state. A stale
candidate can prove the code runs, but it cannot prove the handoff is safe for
today's production data.

Copy/sync the local app state into candidate bench as appropriate for the local setup. If the app in the bench is a Git checkout of the same repo, pull/copy is not needed. If it is a separate copy, sync it before migrating.

Example WSL check:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc 'cd /home/michaelplusone/frappe-sandbox/benches/candidate-bench/apps/inductone_tools && git status --short'
```

Run migration:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc 'cd /home/michaelplusone/frappe-sandbox/benches/candidate-bench && /home/michaelplusone/.venvs/frappe-bench/bin/bench --site inductone-candidate.localhost migrate'
```

Clear cache/build assets if UI behavior is stale:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc 'cd /home/michaelplusone/frappe-sandbox/benches/candidate-bench && /home/michaelplusone/.venvs/frappe-bench/bin/bench --site inductone-candidate.localhost clear-cache'
wsl.exe -d Ubuntu-22.04 -- bash -lc 'cd /home/michaelplusone/frappe-sandbox/benches/candidate-bench && /home/michaelplusone/.venvs/frappe-bench/bin/bench build'
```

Restart the local candidate bench process if needed.

## Phase 2 — create sandbox-only test passwords

This is allowed only in candidate/local sandbox.

Never use this on production without explicit approval and a planned test window.

Use throwaway passwords:

```powershell
$TestPassword = "InductOne-Sandbox-Test-2026!"
```

Reset candidate passwords:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc 'cd /home/michaelplusone/frappe-sandbox/benches/candidate-bench && /home/michaelplusone/.venvs/frappe-bench/bin/bench --site inductone-candidate.localhost set-admin-password "inductone-local-admin-2026"'
```

For normal users, use a Frappe script so the action is auditable in the sandbox:

```powershell
@'
import frappe

SITE = "inductone-candidate.localhost"
SITES_PATH = "/home/michaelplusone/frappe-sandbox/benches/candidate-bench/sites"
PASSWORD = "InductOne-Sandbox-Test-2026!"

users = [
    "michael.king@plusonerobotics.com",
    "christina.gt@plusonerobotics.com",
    "jim.haws@plusonerobotics.com",
    "david.brain@plusonerobotics.com",
    "shaun.edwards@plusonerobotics.com",
    "jason.minica@plusonerobotics.com",
    "wayne.kirk@plusonerobotics.com",
    "david.moreno@plusonerobotics.com",
    "motion.builder@plusonerobotics.com",
    "lam@plusonerobotics.com",
]

frappe.init(site=SITE, sites_path=SITES_PATH)
frappe.connect()
try:
    for user in users:
        if frappe.db.exists("User", user):
            frappe.get_doc("User", user).new_password = PASSWORD
            frappe.get_doc("User", user).save(ignore_permissions=True)
            print("password reset", user)
    frappe.db.commit()
finally:
    frappe.destroy()
'@ | Set-Content -Encoding UTF8 C:\hub\frappe-sandbox\reset_candidate_test_passwords.py

wsl.exe -d Ubuntu-22.04 -- bash -lc 'cd /home/michaelplusone/frappe-sandbox/benches/candidate-bench && env/bin/python /mnt/c/hub/frappe-sandbox/reset_candidate_test_passwords.py'
```

## Phase 3 — assign target roles in candidate

Candidate user assignment is sandbox-only validation state. Production assignment should be deliberate/manual or applied with a reviewed data patch.

Representative target mapping:

| User | Candidate roles to test |
|---|---|
| `michael.king@plusonerobotics.com` | `InductOne Process Architect`, `InductOne Manager`, `Engineering User`, `Operations Manager` |
| `christina.gt@plusonerobotics.com` | `InductOne Manager`, `Engineering User`, `Operations Manager` if intended |
| `jim.haws@plusonerobotics.com` | `InductOne Manager`, optional `Operations Manager` |
| `david.brain@plusonerobotics.com` | `InductOne Manager`, `Engineering User`, optional `Operations Manager` |
| `shaun.edwards@plusonerobotics.com` | `Engineering User` |
| `jason.minica@plusonerobotics.com` | `Engineering User` |
| `wayne.kirk@plusonerobotics.com` | `Engineering User` |
| `david.moreno@plusonerobotics.com` | `Engineering User` |
| `motion.builder@plusonerobotics.com` | `InductOne External Builder` |
| `lam@plusonerobotics.com` | `InductOne External Builder` |

Before assigning roles, clear broad Role Profiles from test users:

```powershell
@'
import frappe

SITE = "inductone-candidate.localhost"
SITES_PATH = "/home/michaelplusone/frappe-sandbox/benches/candidate-bench/sites"

assignments = {
    "michael.king@plusonerobotics.com": ["InductOne Process Architect", "InductOne Manager", "Engineering User", "Operations Manager"],
    "christina.gt@plusonerobotics.com": ["InductOne Manager", "Engineering User", "Operations Manager"],
    "jim.haws@plusonerobotics.com": ["InductOne Manager", "Operations Manager"],
    "david.brain@plusonerobotics.com": ["InductOne Manager", "Engineering User", "Operations Manager"],
    "shaun.edwards@plusonerobotics.com": ["Engineering User"],
    "jason.minica@plusonerobotics.com": ["Engineering User"],
    "wayne.kirk@plusonerobotics.com": ["Engineering User"],
    "david.moreno@plusonerobotics.com": ["Engineering User"],
    "motion.builder@plusonerobotics.com": ["InductOne External Builder"],
    "lam@plusonerobotics.com": ["InductOne External Builder"],
}

frappe.init(site=SITE, sites_path=SITES_PATH)
frappe.connect()
try:
    for user, roles in assignments.items():
        if not frappe.db.exists("User", user):
            print("missing", user)
            continue

        doc = frappe.get_doc("User", user)
        doc.role_profile_name = ""

        existing = {row.role for row in doc.roles}
        for role in roles:
            if role not in existing:
                doc.append("roles", {"role": role})

        doc.save(ignore_permissions=True)
        print("assigned", user, roles)

    frappe.db.commit()
finally:
    frappe.destroy()
'@ | Set-Content -Encoding UTF8 C:\hub\frappe-sandbox\assign_candidate_target_roles.py

wsl.exe -d Ubuntu-22.04 -- bash -lc 'cd /home/michaelplusone/frappe-sandbox/benches/candidate-bench && env/bin/python /mnt/c/hub/frappe-sandbox/assign_candidate_target_roles.py'
```

The repo now includes a maintained script for this step:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc 'cd /home/michaelplusone/frappe-sandbox/benches/candidate-bench && env/bin/python /mnt/c/Users/MichaelKing/OneDrive\ -\ Plus\ One\ Robotics/Documents/GitHub/inductone_tools/scripts/assign_candidate_target_roles.py --site inductone-candidate.localhost --sites-path /home/michaelplusone/frappe-sandbox/benches/candidate-bench/sites --remove-legacy --strict-target-roles'
```

This command is a dry run unless `--confirm-candidate` is added.

Use `--strict-target-roles` for persona validation so old Role Profile residue
does not create false passes. Do not use strict cleanup as a production user
migration strategy until the final user matrix is approved.

## Phase 4 — automated bench permission audit

Create a permission audit script:

```powershell
@'
import frappe
from frappe.permissions import has_permission

SITE = "inductone-candidate.localhost"
SITES_PATH = "/home/michaelplusone/frappe-sandbox/benches/candidate-bench/sites"

users = [
    "michael.king@plusonerobotics.com",
    "christina.gt@plusonerobotics.com",
    "jim.haws@plusonerobotics.com",
    "david.brain@plusonerobotics.com",
    "shaun.edwards@plusonerobotics.com",
    "motion.builder@plusonerobotics.com",
    "lam@plusonerobotics.com",
]

doctypes = [
    "InductOne Build",
    "InductOne Configuration Option",
    "InductOne Builder Tranche",
    "InductOne Configuration Order",
    "BOM Export Package",
    "Configured BOM Snapshot",
    "InductOne Build Completion",
    "InductOne As-Built Record",
    "InductOne Instance",
    "Engineering Signoff",
    "Part Number Allocation Request",
    "Part Number Assignment",
    "Item",
    "BOM",
    "Sales Order",
    "Delivery Note",
    "Stock Entry",
    "Work Order",
]

ptypes = ["read", "write", "create", "submit", "cancel", "delete"]

frappe.init(site=SITE, sites_path=SITES_PATH)
frappe.connect()
try:
    for user in users:
        print("\\nUSER", user)
        print("roles", sorted(frappe.get_roles(user)))
        for dt in doctypes:
            if not frappe.db.exists("DocType", dt):
                continue
            result = {ptype: bool(has_permission(dt, ptype=ptype, user=user)) for ptype in ptypes}
            print(dt, result)
finally:
    frappe.destroy()
'@ | Set-Content -Encoding UTF8 C:\hub\frappe-sandbox\candidate_permission_audit.py

wsl.exe -d Ubuntu-22.04 -- bash -lc 'cd /home/michaelplusone/frappe-sandbox/benches/candidate-bench && env/bin/python /mnt/c/hub/frappe-sandbox/candidate_permission_audit.py' > C:\hub\frappe-sandbox\candidate_permission_audit.txt
```

Review:

```powershell
notepad C:\hub\frappe-sandbox\candidate_permission_audit.txt
```

Expected red flags:

- External builder has any raw `Item`, `BOM`, `Sales Order` read results.
- `InductOne Manager` can create/edit `InductOne Configuration Option` or `InductOne Builder Tranche`.
- `Engineering User` cannot read/signoff/allocate part numbers.
- `Operations Viewer` has any create/write/submit/cancel.
- `Finance Viewer` has any create/write/submit/cancel.
- `Procurement User` has broader write than intended.

## Phase 5 — API/curl smoke tests

Curl tests prove session/API behavior beyond direct Python permission helpers.

Use a cookie jar per user:

```powershell
$Base = "http://inductone-candidate.localhost:8000"
$Password = "InductOne-Sandbox-Test-2026!"
$CookieDir = "C:\hub\frappe-sandbox\cookies"
New-Item -ItemType Directory -Force -Path $CookieDir | Out-Null
```

Login as a user:

```powershell
curl.exe -s -c "$CookieDir\motion.txt" -b "$CookieDir\motion.txt" `
  -H "Content-Type: application/json" `
  -X POST "$Base/api/method/login" `
  --data "{\"usr\":\"motion.builder@plusonerobotics.com\",\"pwd\":\"$Password\"}"
```

Check logged-in user:

```powershell
curl.exe -s -b "$CookieDir\motion.txt" "$Base/api/method/frappe.auth.get_logged_user"
```

List access checks:

```powershell
curl.exe -s -b "$CookieDir\motion.txt" "$Base/api/method/frappe.desk.reportview.get?doctype=Item&fields=[`\"`tabItem`.`name`\"]&filters=[]&order_by=`tabItem`.`modified`%20desc&start=0&page_length=20"

curl.exe -s -b "$CookieDir\motion.txt" "$Base/api/method/frappe.desk.reportview.get?doctype=BOM&fields=[`\"`tabBOM`.`name`\"]&filters=[]&order_by=`tabBOM`.`modified`%20desc&start=0&page_length=20"

curl.exe -s -b "$CookieDir\motion.txt" "$Base/api/method/frappe.desk.reportview.get?doctype=InductOne%20Configuration%20Order&fields=[`\"`tabInductOne Configuration Order`.`name`\"]&filters=[]&order_by=`tabInductOne Configuration Order`.`modified`%20desc&start=0&page_length=20"
```

Expected for external builder:

- `Item`: zero rows or permission denial.
- `BOM`: permission denial or zero rows.
- `Sales Order`: permission denial.
- Assigned `InductOne Configuration Order`: only supplier-scoped rows.
- Assigned `BOM Export Package`: only supplier-scoped rows.
- Assigned `Configured BOM Snapshot`: only snapshots linked to assigned handoff artifacts.

State-changing endpoint checks:

```powershell
# External builder should not be able to approve signoff.
curl.exe -s -b "$CookieDir\motion.txt" `
  -H "Content-Type: application/json" `
  -X POST "$Base/api/method/inductone_tools.engineering_signoff.approve_signoff" `
  --data "{\"signoff_name\":\"REPLACE_WITH_PENDING_SIGNOFF\",\"notes\":\"negative test\"}"

# External builder should not be able to allocate part numbers.
curl.exe -s -b "$CookieDir\motion.txt" `
  -H "Content-Type: application/json" `
  -X POST "$Base/api/method/inductone_tools.part_numbering.allocate_numbers" `
  --data "{\"allocation_request\":\"REPLACE_WITH_DRAFT_REQUEST\"}"
```

Expected:

- Permission error, not silent success.

## Phase 6 — live GUI smoke tests

Use the candidate URL:

```text
http://inductone-candidate.localhost:8000
```

Sandbox test password:

```text
InductOne-Sandbox-Test-2026!
```

### External Builder — Motion / LAM

Login as:

- `motion.builder@plusonerobotics.com`
- `lam@plusonerobotics.com`

Test:

- Lands on / can access `Builder Portal`.
- Cannot access Operations or Engineering workspace.
- Can list/open only assigned Configuration Orders.
- Can list/open only assigned BOM Export Packages.
- Can download generated builder files.
- Can access assigned Build Completion upload/update path.
- Cannot list/open raw Item.
- Cannot list/open raw BOM.
- Cannot list/open Sales Order.
- Cannot access Builder Tranche.
- Cannot approve signoff.
- Cannot allocate part numbers.
- Cannot release build.
- Cannot accept completion.

### InductOne Manager

Login as:

- `christina.gt@plusonerobotics.com`
- `jim.haws@plusonerobotics.com`
- `david.brain@plusonerobotics.com`

Test:

- Create/open/edit InductOne Build.
- Load Catalog Options.
- Generate Snapshot.
- Generate Configuration Order.
- Generate/open BOM Export Package.
- Prepare Builder Handoff.
- Allocate system serial.
- Release to builder.
- Upload Build Completion.
- Review/reject/accept Build Completion.
- Can read As-Built and Instance after acceptance.
- Cannot create/edit `InductOne Configuration Option`.
- Cannot create/edit `InductOne Builder Tranche`.
- Cannot use Fixture Export Control.

### InductOne Process Architect

Login as:

- `michael.king@plusonerobotics.com`

Test:

- Can edit Configuration Options.
- Can create/edit Builder Tranches.
- Can access Fixture Export Control.
- Can inspect all InductOne records.
- Can perform emergency correction paths.

### Engineering User

Login as one official engineering user:

- `shaun.edwards@plusonerobotics.com`
- `jason.minica@plusonerobotics.com`
- `wayne.kirk@plusonerobotics.com`
- `david.moreno@plusonerobotics.com`

Test:

- Can open Engineering workspace.
- Can read controlled Items/BOMs/Product Bundles/Configuration Options needed for review.
- Can open Pending Engineering Signoff.
- Can approve signoff.
- Can reject signoff with required reason.
- Can supersede where intended.
- Can create/manage Part Number Allocation Request.
- Can click Allocate Numbers.
- Cannot run InductOne build release/completion workflow unless also assigned `InductOne Manager`.

### Operations Viewer

Login as representative read-only internal user.

Test:

- Can view Items, BOMs, Sales Orders, Delivery Notes, Stock Balance, Stock Ledger, InductOne records.
- Cannot create/write/submit/cancel anything.
- Cannot see state-changing InductOne buttons.

### Operations Manager

Login as representative operations manager.

Test:

- Can create/edit Items/BOMs/Product Bundles as intended.
- Can create/submit Sales Orders.
- Can create/submit Delivery Notes.
- Can manage normal stock/production workflows.
- Can view InductOne records.
- Cannot run InductOne-specific actions unless also assigned `InductOne Manager`.
- Cannot approve engineering signoff unless also assigned `Engineering User`.

### Inventory Operator

Login as representative inventory user.

Test:

- Can create/perform intended Stock Entry / receiving workflows.
- Can perform intended Delivery Note / dispatch workflows.
- Can perform stock count / material issue workflows if intended.
- Cannot edit Item/BOM master records.
- Cannot submit Sales Orders unless intentionally assigned.
- Cannot run InductOne actions.

### Gripper Manufacturer

Login as representative gripper user.

Test:

- Can execute serialized gripper Work Orders.
- Can perform refurbishment/repack workflow.
- Can enter required serials/stock movements.
- Cannot perform unrelated Operations Manager workflows.
- Cannot run InductOne actions.

### Finance Viewer

Login as finance representative.

Test:

- Can read Items, BOMs, Sales Orders, Delivery Notes, Purchase docs, Stock Ledger, accounting/audit records, and InductOne history.
- Can export/report where required for audit.
- Cannot create/write/submit/cancel.

### Procurement User

Login as procurement representative.

Test:

- Can edit intended vendor/pricing/descriptive item data.
- Can update Item Price or supplier/vendor references if confirmed.
- Cannot create/release engineering-controlled artifacts unless intentionally assigned.
- Cannot approve signoff.
- Cannot run InductOne actions.

## Phase 7 — evidence capture

Save evidence under:

```text
C:\hub\frappe-sandbox\validation-evidence\
```

Suggested files:

- `candidate_permission_audit.txt`
- `curl_external_builder_motion.txt`
- `curl_engineering_user.txt`
- `curl_operations_viewer.txt`
- screenshots of each GUI persona smoke test
- notes on failures and corrections

Each failure should be classified:

| Failure type | Response |
|---|---|
| Missing intended access | Add/adjust DocPerm/role/profile/method gate after confirming intent. |
| Excess access | Remove role, DocPerm, standard role, Role Profile, or User Permission source. |
| UI button visible but server denies | Usually acceptable but confusing; fix client script if user-facing. |
| UI button hidden but server permits | Fix client script; server is authoritative but UI is wrong. |
| Server permits but should deny | Critical; fix server gate before deployment. |

## Phase 8 — production deployment gate

Do not deploy until:

- Static checks pass.
- `bench migrate` passes in candidate.
- Automated permission audit has no critical failures.
- API/curl negative tests deny correctly.
- GUI smoke tests pass for every persona.
- Wiki pages are updated to match the final model.
- User assignment matrix is approved.
- Rollback plan is ready.

## Rollback plan

If candidate migration causes access breakage:

1. Do not deploy to production.
2. Restore candidate database from backup if needed.
3. Revert local role fixture/patch changes or narrow them.
4. Re-run `bench migrate`.
5. Re-run persona tests.

If production deployment causes access breakage after release:

1. Use System Manager/Administrator access to restore emergency admin access.
2. Reassign temporary standard ERPNext roles only long enough to restore operations.
3. Roll back app commit if the break is fixture/code-driven.
4. Restore database backup only if role state/data migration cannot be safely reversed.

## Final acceptance criteria

The migration is complete only when the following statement is true:

> For every workflow documented in the wiki or repo docs, at least one explicit target role can perform it in candidate, every non-authorized role is blocked, and the implemented server-side gates match the documented role model.
