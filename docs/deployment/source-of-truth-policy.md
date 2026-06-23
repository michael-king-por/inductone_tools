# Source-of-Truth Policy

This policy defines where each class of InductOne artifact is allowed to live. It exists to remove the two-path deployment ambiguity between GUI-maintained configuration and repo-maintained app code.

The policy goal is not "everything in Git." The goal is that every artifact has exactly one authoritative owner.

## Principle

If an artifact changes how the application behaves after deployment, it should be repo-owned unless there is a deliberate reason for it to remain database-owned.

If an artifact records what happened operationally, it must remain database-owned and should never be fixture-managed.

## Ownership table

| Artifact | Source of truth | Why |
|---|---|---|
| Python code | Repo | Code must be reviewed, versioned, and deployed consistently. |
| `hooks.py` | Repo | Hooks define server behavior and must not drift in production. |
| App metadata | Repo | Deployment expects stable app identity/version. |
| Custom DocTypes | Repo fixtures initially | These define schema and forms. Long-term, consider standard app DocTypes where appropriate. |
| Custom Fields | Repo fixtures only when deploy-critical | Empty fixture currently observed; keep intentional. |
| Property Setters | Repo fixtures only when deploy-critical | Empty fixture currently observed; keep intentional. |
| Client Scripts | Repo fixtures or static app JS | They change operator UI behavior. Must be explicit allowlist, not broad export. |
| Server Scripts | Prefer repo Python | Server Scripts are harder to review/test. Use only when intentionally DB-owned. |
| Custom DocPerm | Repo fixtures | Permissions must be auditable. |
| Roles | Repo fixtures if app-specific | App-specific roles should not be tribal GUI state. |
| User Permissions | Usually database-owned | Often environment/user specific. Fixture only with explicit approval. |
| Workspaces / landing pages | Case-by-case | Repo-owned if required for deployment; DB-owned if operational content. |
| Wiki pages | Case-by-case | Repo-owned only if treated as controlled product docs. Otherwise backup/database-owned. |
| Builds | Database | Operational records. Never fixture. |
| Configuration Orders | Database | Operational records. Never fixture. |
| Build Completions | Database | Operational records. Never fixture. |
| As-Built Records | Database | Historical evidence. Never fixture. |
| Instances | Database | Operational/support records. Never fixture. |
| Builder Tranches | Database, with controlled permissions | Operational serial allocation state. Never fixture unless seeding a non-production environment. |
| Uploaded files | File storage/backups | Runtime artifacts. Never fixture. |
| Generated packages/workbooks | Runtime files/backups | Generated evidence/artifacts. Never fixture. |
| Error logs/execution logs | Runtime database/logs | Operational telemetry. Never fixture. |

## Current transitional state

Current system state includes:

- Repo-owned Python business logic.
- Repo fixtures for DocTypes, Client Scripts, and Custom DocPerm.
- A GUI-triggered fixture export utility.
- Production database as the source of operational records.

This is transitional. The intended end state is:

- Repo is authoritative for app code and deployable configuration.
- Database is authoritative for operational records.
- GUI changes to deployable configuration are made in a sandbox, exported, reviewed, and committed.
- Production GUI is not used as the normal source of deployable configuration.

## Allowed GUI changes

Production GUI changes are allowed for:

- Operational records.
- Runtime data correction with appropriate authorization.
- Emergency configuration repair, followed by immediate repo reconciliation.

Production GUI changes are not the preferred path for:

- Client Scripts.
- Custom DocType schema.
- Custom DocPerm.
- Workflows.
- Roles.
- App-owned Workspaces.
- Any change that would need to survive deployment to another site.

## Reconciliation rule

If production GUI state is changed for a deployable artifact:

1. Record why the change was made.
2. Export the affected artifact from production or a production clone.
3. Compare against repo state.
4. Commit the intentional diff.
5. Validate in a candidate sandbox.
6. Deploy through the normal app update process.

The GUI export utility should support this reconciliation path. It should not define the normal release path.

## Handoff requirement

A future owner should be able to answer:

- Where do I change this artifact?
- How do I test it?
- How does it reach production?
- How do I know production did not drift?

If the answer is "look in the GUI and hope," the artifact is not yet handoff-ready.
