# InductOne CSA Lifecycle Smoke — Candidate Evidence

Date: 2026-07-09  
Environment: candidate sandbox only  
Site: `inductone-candidate.localhost`  
Bench: `/home/michaelplusone/frappe-sandbox/benches/candidate-bench`  
Script: `scripts/run_inductone_csa_lifecycle_smoke.py`  
Passing evidence: `C:\hub\frappe-sandbox\validation-evidence\inductone_csa_lifecycle_smoke_20260709T171616Z.json`

## Purpose

This candidate-only smoke test proves the full InductOne CSA lifecycle can execute through the real server-side methods, not only through isolated permission checks.

The script creates a synthetic Build cloned from restored production build `SAL-ORD-2026-00054-BLD-0225`, then drives the actual workflow:

1. Create synthetic InductOne Build.
2. Generate Configured BOM Snapshot.
3. Populate Snapshot Hierarchy.
4. Generate hierarchy workbook.
5. Create Configuration Order.
6. Generate BOM Export Package.
7. Ensure top-BOM Engineering Signoff.
8. Allocate system serial from the builder tranche.
9. Pass release readiness.
10. Release to builder.
11. Acknowledge release as external builder.
12. Upload a filled builder completion workbook.
13. Mark completion Reviewed.
14. Accept completion.
15. Create locked As-Built Record.
16. Create InductOne Instance.
17. Confirm serial propagation through As-Built and Instance.

## Command

```bash
cd /home/michaelplusone/frappe-sandbox/benches/candidate-bench
env/bin/python /mnt/c/Users/MichaelKing/OneDrive\ -\ Plus\ One\ Robotics/Documents/GitHub/inductone_tools/scripts/run_inductone_csa_lifecycle_smoke.py \
  --site inductone-candidate.localhost \
  --sites-path /home/michaelplusone/frappe-sandbox/benches/candidate-bench/sites \
  --evidence-dir /mnt/c/hub/frappe-sandbox/validation-evidence \
  --confirm-candidate
```

## Passing candidate records

| Record | Value |
|---|---|
| Synthetic Build | `SAL-ORD-2026-00054-BLD-0455` |
| Snapshot | `SAL-ORD-2026-00054-BLD-0455-SNAP-0456` |
| Configuration Order | `SAL-ORD-2026-00054-BLD-0455-CO-457` |
| BOM Export Package | `BOM-1611 027 0020-002-0458` |
| Build Completion | `SAL-ORD-2026-00054-BLD-0455-COMP-459` |
| As-Built Record | `SAL-ORD-2026-00054-BLD-0455-ASBUILT-460` |
| Instance | `IND-3006` |
| System Serial | `IND-3006` |

## Result summary

| Gate | Result | Notes |
|---|---:|---|
| REV E preconditions | PASS | Source build exists; master BOM active/submitted; 26 configurable balloon rows present |
| Synthetic build | PASS | Cloned from `BLD-0225`; builder = Motion Controls |
| Snapshot/hierarchy/workbook | PASS | 1,307 hierarchy rows |
| Configuration Order | PASS | Draft CO created against current snapshot |
| BOM Export Package | PASS | Status `Complete`, output ZIP generated, 1,300 package rows |
| Engineering Signoff | PASS | Top BOM signoff was already approved after earlier candidate smoke setup |
| Serial allocation | PASS | Allocated `IND-3006`; Build and CO both stamped |
| Release readiness | PASS | No missing items; warning only that flat BOM would be generated at release if missing |
| Release to builder | PASS | Build `RELEASED_TO_BUILDER`; CO `Released`; release manifest and serial workbook created |
| Builder acknowledgement | PASS | CO moved to `Awaiting Completion`; acknowledged by `motion.builder@plusonerobotics.com` |
| Completion upload | PASS | Parser read 34 component rows; 34 filled; zero serial warnings |
| Review completion | PASS | Completion moved to `Reviewed`; reviewer stamped |
| Accept completion | PASS | Completion `Accepted`; Build `COMPLETED`; CO `Closed`; As-Built `Locked`; Instance `Ready for Ship` |
| Serial propagation | PASS | As-Built serial rows = 34; Instance component serial rows = 34 |

## Defects found and fixed during this gate

### 1. Retired `flat_bom_status = Pending` value

The CO after-insert hook still wrote `flat_bom_status = "Pending"`, but the DocType Select options are now:

- `Queued`
- `Running`
- `Complete`
- `Failed`

That caused later CO saves during package sync to fail. Fixed in:

- `inductone_tools/inductone_tools/doctype/inductone_configuration_order/inductone_configuration_order.py`

The hook now writes `Queued`.

### 2. Instance did not preserve accepted component serials

The acceptance path copied Build Completion serials to the locked As-Built Record, then created an InductOne Instance with zero `component_serials`. Backfill-created Instances already preserve component serials, so the formal acceptance path now does the same.

Fixed in:

- `inductone_tools/instance/creation.py`

The lifecycle smoke now fails unless `len(instance.component_serials) == len(as_built.serials)`.

## Follow-up hardening

The initial lifecycle smoke validated the happy path. Direct negative hardening for `acknowledge_builder_release()` was closed afterward by:

- `inductone_csa_hardening_gates_20260709T190616Z.json`
- `method_negative_tests_20260709T190708Z.json`

Those gates prove unauthorized non-builder users and wrong-supplier external builders are denied before acknowledgement state mutation.
