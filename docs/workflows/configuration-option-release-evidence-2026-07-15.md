# Configuration option release evidence — 2026-07-15

Purpose: produce a read-only, machine-readable evidence package for Engineering Change review when releasing InductOne Configuration Options.

Tool:

- `scripts/run_configuration_option_release_evidence.py`

What it proves for each requested option:

- the option record exists;
- the option is active and `Released`;
- mapping status is `Complete`;
- at least one mapping/effect row exists;
- the expected Engineering Signoff exists, is current, and is approved;
- each mapping row is recorded with its action, target item/BOM, replacement item/BOM, quantity override data, and linked Item/BOM summaries.

Candidate sanity run:

- Evidence file: `C:\hub\frappe-sandbox\validation-evidence\configuration_option_release_evidence_20260715T180435Z.json`
- Result: expected candidate failure. The records exist on candidate, but candidate has not been advanced to the production EC state for the July signoffs/release approvals, so it is not authoritative for this EC package.

Production read-only command:

```bash
cd ~/frappe-bench

SITE="plusonerobotics.v.frappe.cloud"
EVIDENCE_DIR="$PWD/sites/$SITE/private/files/ec-option-release-evidence"

mkdir -p /home/frappe/logs
mkdir -p "$PWD/sites/$SITE/logs"
mkdir -p "$PWD/$SITE/logs"
mkdir -p "$EVIDENCE_DIR"

./env/bin/python apps/inductone_tools/scripts/run_configuration_option_release_evidence.py \
  --site "$SITE" \
  --sites-path "$PWD/sites" \
  --evidence-dir "$EVIDENCE_DIR" \
  --option 5G-ADD --expected-signoff 5G-ADD=SIGN-2026-07-0052 \
  --option JB3-REMOVE --expected-signoff JB3-REMOVE=SIGN-2026-07-0047 \
  --option PUMP-HOSE-25 --expected-signoff PUMP-HOSE-25=SIGN-2026-07-0051 \
  --option PUMP-HOSE-50 --expected-signoff PUMP-HOSE-50=SIGN-2026-07-0050 \
  --option ROB-PEN-ADD --expected-signoff ROB-PEN-ADD=SIGN-2026-07-0048 \
  --option STCK-2-ADD --expected-signoff STCK-2-ADD=SIGN-2026-07-0049
```

Go/no-go:

- `PASS` for all six options means the JSON is suitable to attach to the EC as programmatic release evidence.
- Any `FAIL` is actionable. The failed check tells whether the issue is unreleased status, incomplete mapping, missing signoff, or a missing/unapproved expected signoff.

