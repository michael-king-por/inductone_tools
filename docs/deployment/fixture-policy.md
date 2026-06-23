# Fixture Policy

Fixtures are the bridge between Frappe database-managed configuration and repo-managed deployment. They are useful, but they can also silently move too much state if filters are broad.

The InductOne fixture policy is:

1. Fixture deployable configuration only.
2. Never fixture operational records.
3. Prefer explicit allowlists over broad DocType-wide exports.
4. Review fixture diffs like code.
5. Validate fixture imports in a restored candidate sandbox before production.

## Current fixtures

Current local repo fixture files:

| File | Current count | Notes |
|---|---:|---|
| `client_script.json` | 26 | Contains UI behavior. Should move from broad export to explicit allowlist. |
| `doctype.json` | 31 | Contains custom DocTypes across `Operations - POR` and `InductOne Tools`. |
| `custom_docperm.json` | 12 | Contains permission rows for selected custom DocTypes. |
| `custom_field.json` | 0 | Empty; keep intentional unless future deploy-critical custom fields are added. |
| `property_setter.json` | 0 | Empty; keep intentional unless future deploy-critical property setters are added. |

## Current fixture filters

`hooks.py` currently includes a broad Client Script fixture:

```python
{
    "dt": "Client Script"
}
```

This is the highest-risk fixture filter because it can capture unrelated client scripts and deploy them with InductOne.

## Target fixture filters

Preferred future shape:

```python
fixtures = [
    {
        "dt": "DocType",
        "filters": [["name", "in", [
            "InductOne Build",
            "InductOne Build Completion",
            "... explicit names ..."
        ]]]
    },
    {
        "dt": "Custom DocPerm",
        "filters": [["parent", "in", [
            "InductOne Build",
            "InductOne Build Completion",
            "... explicit names ..."
        ]]]
    },
    {
        "dt": "Client Script",
        "filters": [["name", "in", [
            "InductOne Build Script",
            "InductOne Build Completion Script",
            "... explicit names ..."
        ]]]
    }
]
```

Do not implement the narrowing blindly. First generate the current fixture row list, define the allowlist, export in a candidate sandbox, and verify the diff contains no unintended deletions.

## Fixture ownership categories

### Allowed fixtures

Allowed when explicitly app-owned:

- Custom DocTypes.
- Custom DocPerm.
- Client Scripts.
- Custom Fields.
- Property Setters.
- Workspaces.
- Reports.
- Print Formats.
- Workflows and Workflow States.
- App-specific Roles.

### Discouraged fixtures

Use only with written justification:

- Server Scripts.
- User Permissions.
- Wiki Pages.
- Web Pages.
- Website Settings.
- Letterheads.
- Notification settings.

These can be environment-specific or content-heavy. Decide case-by-case.

### Forbidden fixtures

Never fixture:

- Sales Orders.
- Items, BOMs, Product Bundles, or Suppliers as operational data.
- InductOne Builds.
- Configuration Orders.
- Build Completions.
- As-Built Records.
- Instances.
- Builder Tranche allocation state.
- Uploaded File records.
- Logs.
- Generated export packages.

## Review checklist for fixture diffs

Every fixture diff should answer:

- Is this artifact deployable configuration or operational data?
- Is the artifact app-owned?
- Was the change made intentionally?
- Does the diff remove anything from production behavior?
- Was `bench migrate` run in a restored candidate sandbox?
- Was the relevant workflow smoke-tested?
- Is the change documented?

## Fixture export utility policy

`fixture_sync.py` currently exists as a GUI-triggered export/push path. Long-term, it should be treated as one of:

- audit-only drift reporter,
- sandbox-only export helper,
- emergency reconciliation tool.

It should not remain the normal production deployment path because production GUI state should not be the implicit source of truth for deployable application behavior.

## Fixture audit script

Use the repo fixture audit script before and after fixture changes:

```bash
python scripts/audit_fixtures.py --repo .
```

When running inside a restored Frappe bench environment, compare repo fixture rows with the site database:

```bash
env/bin/python /path/to/inductone_tools/scripts/audit_fixtures.py \
  --repo /path/to/inductone_tools \
  --bench /path/to/frappe-bench \
  --site inductone-candidate.localhost
```

## Proposed fixture manifest

Add a future `fixtures/manifest.md` or `docs/deployment/fixture-manifest.md` with:

| Fixture row | Owner | Reason | Test coverage | Last reviewed |
|---|---|---|---|---|
| InductOne Build Script | Repo | Build UI controls | Build smoke test | TBD |
| InductOne Build Completion Script | Repo | Completion review UI | Completion lifecycle test | TBD |
| InductOne Build Completion | Repo | Schema | Migration smoke | TBD |

The manifest should make fixture ownership explicit enough for handoff.
