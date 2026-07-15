# inductone_tools/fixture_sync.py
#
# Fixture audit utility with sandbox-only export/push escape hatch.
#
# This file used to provide a production GUI path that exported fixtures,
# committed, and pushed to GitHub. That made production GUI state an implicit
# source of truth. As of 2026-07-15, the normal whitelisted path is audit-only.
# The old export/push path is retained only for explicitly configured sandbox
# benches and refuses to run on production-looking sites.
#
# Requires `github_pat` in site config. Set it once via:
#     bench --site <site> set-config -p github_pat "<token>"
#
# The PAT must have Contents:read-write on the inductone_tools repo.

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import frappe

# ---------------------------------------------------------------------------
# Tunables. Change these if your repo URL / branch / identity / app path change.
# ---------------------------------------------------------------------------
APP_NAME = "inductone_tools"
GITHUB_OWNER = "michael-king-por"
GITHUB_REPO = "inductone_tools"
TARGET_BRANCH = "main"
COMMIT_AUTHOR_NAME = "Michael"
COMMIT_AUTHOR_EMAIL = "michael.king@plusonerobotics.com"


# ---------------------------------------------------------------------------
# Public entrypoint, exposed to the client script.
# ---------------------------------------------------------------------------
@frappe.whitelist()
def audit_fixture_status():
    """Return read-only fixture/git status for the current app checkout."""

    _require_fixture_audit_role()

    bench_path = _bench_path()
    app_path = os.path.join(bench_path, "apps", APP_NAME)

    fixture_dir = Path(app_path) / APP_NAME / "fixtures"
    fixture_counts = {}
    if fixture_dir.exists():
        for fixture_path in sorted(fixture_dir.glob("*.json")):
            try:
                import json

                rows = json.loads(fixture_path.read_text(encoding="utf-8"))
                fixture_counts[fixture_path.name] = len(rows) if isinstance(rows, list) else 1
            except Exception as exc:
                fixture_counts[fixture_path.name] = f"ERROR: {exc}"

    git_status = _git(app_path, ["status", "--short"], check=False).stdout.splitlines()
    branch = _git(app_path, ["branch", "--show-current"], check=False).stdout.strip()
    head = _git(app_path, ["rev-parse", "--short", "HEAD"], check=False).stdout.strip()

    return {
        "ok": True,
        "mode": "audit_only",
        "site": frappe.local.site,
        "message": (
            "Fixture Export Control is audit-only. Production GUI export/push is disabled; "
            "fixture changes must be reviewed, committed, and deployed from the repository."
        ),
        "app_path": app_path,
        "branch": branch,
        "head": head,
        "git_status": git_status,
        "fixture_counts": fixture_counts,
    }


@frappe.whitelist()
def export_and_push_fixtures():
    """Sandbox-only export, commit, and push helper.

    This method refuses to run unless:

    - the current site name looks like a sandbox/candidate/dev site; and
    - site_config explicitly sets ``fixture_sync_mode = "sandbox_push"``.

    Production must never use GUI export/push as a source of truth.
    """

    _require_fixture_audit_role()
    _require_sandbox_push_mode()

    pat = frappe.conf.get("github_pat")
    if not pat:
        frappe.throw(
            "github_pat is not set in site_config.json. "
            "Run: bench --site <site> set-config -p github_pat \"<token>\""
        )

    bench_path = _bench_path()
    app_path = os.path.join(bench_path, "apps", APP_NAME)
    site = frappe.local.site

    steps = []

    try:
        steps.append(_ensure_git_identity(app_path))
        steps.append(_ensure_origin_remote(app_path, pat))
        steps.append(_ensure_branch(app_path))
        steps.append(_run_export_fixtures(bench_path, site))
        commit_step = _stage_and_commit(app_path)
        steps.append(commit_step)

        if commit_step["committed"]:
            steps.append(_integrate_remote(app_path))
            steps.append(_push(app_path))
            ok_message = "Fixtures exported, committed, rebased, and pushed."
        else:
            ok_message = "Fixtures exported. No changes to commit."

        return {
            "ok": True,
            "message": ok_message,
            "steps": [_redact(pat, s) for s in steps],
        }

    except subprocess.CalledProcessError as e:
        return {
            "ok": False,
            "message": f"Step failed: {e.cmd[0] if isinstance(e.cmd, list) else e.cmd}",
            "stdout": _redact_text(pat, e.stdout or ""),
            "stderr": _redact_text(pat, e.stderr or ""),
            "steps": [_redact(pat, s) for s in steps],
        }
    except Exception as e:
        return {
            "ok": False,
            "message": _redact_text(pat, str(e)),
            "steps": [_redact(pat, s) for s in steps],
        }


# ---------------------------------------------------------------------------
# Step implementations. Each returns a dict describing what it did, for
# display in the client.
# ---------------------------------------------------------------------------
def _require_fixture_audit_role():
    roles = set(frappe.get_roles(frappe.session.user))
    if not {"System Manager", "InductOne Process Architect"} & roles:
        frappe.throw("Fixture audit requires System Manager or InductOne Process Architect.")


def _require_sandbox_push_mode():
    site = frappe.local.site or ""
    mode = frappe.conf.get("fixture_sync_mode")
    sandbox_markers = ("candidate", "sandbox", "localhost", "dev", "test")

    if mode != "sandbox_push":
        frappe.throw(
            "Fixture export/push is disabled. Set fixture_sync_mode = sandbox_push "
            "only on a disposable sandbox bench."
        )

    if not any(marker in site.lower() for marker in sandbox_markers):
        frappe.throw(
            f"Refusing fixture export/push for non-sandbox site '{site}'. "
            "Use local repository workflow instead."
        )


def _ensure_git_identity(app_path):
    """Set repo-level git identity if not already configured."""
    name = _git(app_path, ["config", "user.name"], check=False).stdout.strip()
    email = _git(app_path, ["config", "user.email"], check=False).stdout.strip()

    if not name:
        _git(app_path, ["config", "user.name", COMMIT_AUTHOR_NAME])
    if not email:
        _git(app_path, ["config", "user.email", COMMIT_AUTHOR_EMAIL])

    return {
        "step": "git_identity",
        "set_name": not name,
        "set_email": not email,
        "name": COMMIT_AUTHOR_NAME,
        "email": COMMIT_AUTHOR_EMAIL,
    }


def _ensure_origin_remote(app_path, pat):
    """Make sure 'origin' is the GitHub HTTPS URL with PAT embedded."""
    target_url = (
        f"https://x-access-token:{pat}@github.com/{GITHUB_OWNER}/{GITHUB_REPO}.git"
    )

    remotes = _git(app_path, ["remote"], check=False).stdout.split()

    if "origin" in remotes:
        current = _git(
            app_path, ["remote", "get-url", "origin"], check=False
        ).stdout.strip()
        if current != target_url:
            _git(app_path, ["remote", "set-url", "origin", target_url])
            action = "updated"
        else:
            action = "unchanged"
    else:
        _git(app_path, ["remote", "add", "origin", target_url])
        action = "added"

    # Drop the dead 'upstream' remote that bench get-app leaves behind.
    if "upstream" in remotes:
        _git(app_path, ["remote", "remove", "upstream"], check=False)

    return {"step": "origin_remote", "action": action}


def _ensure_branch(app_path):
    """If we're in detached HEAD (the default on a fresh bench), create main."""
    current = _git(
        app_path, ["branch", "--show-current"], check=False
    ).stdout.strip()

    if current == TARGET_BRANCH:
        return {"step": "branch", "action": "already_on_branch", "branch": current}

    # Fetch first so we know if origin/main exists.
    _git(app_path, ["fetch", "origin", TARGET_BRANCH], check=False)

    # Check if local branch already exists (just not checked out).
    branches = _git(app_path, ["branch", "--list", TARGET_BRANCH]).stdout.strip()

    if branches:
        _git(app_path, ["checkout", TARGET_BRANCH])
        action = "checked_out_existing"
    else:
        # Create main from current commit, set to track origin/main if it exists.
        _git(app_path, ["checkout", "-b", TARGET_BRANCH])
        # Try to set upstream; ignore failure if origin/main doesn't exist yet.
        _git(
            app_path,
            ["branch", f"--set-upstream-to=origin/{TARGET_BRANCH}", TARGET_BRANCH],
            check=False,
        )
        action = "created"

    return {"step": "branch", "action": action, "branch": TARGET_BRANCH}


def _run_export_fixtures(bench_path, site):
    """Run `bench --site <site> export-fixtures`."""
    result = subprocess.run(
        ["bench", "--site", site, "export-fixtures"],
        cwd=bench_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return {
        "step": "export_fixtures",
        "stdout_tail": result.stdout.strip().splitlines()[-10:],
    }


def _stage_and_commit(app_path):
    """Stage all changes; commit only if there's something staged."""
    _git(app_path, ["add", "-A"])

    diff = _git(
        app_path, ["diff", "--cached", "--name-only"], check=False
    ).stdout.strip()

    if not diff:
        return {"step": "commit", "committed": False, "files": []}

    files = diff.splitlines()
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    message = f"Export fixtures {timestamp}"

    _git(app_path, ["commit", "-m", message])

    sha = _git(app_path, ["rev-parse", "--short", "HEAD"]).stdout.strip()

    return {
        "step": "commit",
        "committed": True,
        "files": files,
        "message": message,
        "sha": sha,
    }


def _integrate_remote(app_path):
    """Fetch remote main and rebase local commit(s) before pushing."""
    fetch = _git(app_path, ["fetch", "origin", TARGET_BRANCH], check=True)

    remote_ref = f"origin/{TARGET_BRANCH}"
    exists = _git(
        app_path,
        ["rev-parse", "--verify", remote_ref],
        check=False,
    )

    if exists.returncode != 0:
        return {
            "step": "integrate_remote",
            "action": "no_remote_branch",
            "stdout": fetch.stdout.strip(),
            "stderr": fetch.stderr.strip(),
        }

    rebase = _git(app_path, ["rebase", remote_ref], check=True)

    return {
        "step": "integrate_remote",
        "action": "rebase",
        "stdout": rebase.stdout.strip(),
        "stderr": rebase.stderr.strip(),
    }


def _push(app_path):
    """Push to origin/main, setting upstream if needed."""
    result = _git(app_path, ["push", "-u", "origin", TARGET_BRANCH])
    return {
        "step": "push",
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _bench_path():
    """Walk up from the site directory to find the bench root."""
    # frappe.utils.get_bench_path() exists in newer Frappe; fall back if not.
    try:
        from frappe.utils import get_bench_path

        return get_bench_path()
    except ImportError:
        return os.path.abspath(os.path.join(frappe.local.site_path, "..", ".."))


def _git(cwd, args, check=True):
    """Run a git command in cwd, capturing output."""
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def _redact_text(pat, text):
    """Strip the PAT from any string before returning it to the client."""
    if not pat or not text:
        return text
    return text.replace(pat, "***REDACTED***")


def _redact(pat, obj):
    """Recursively redact PAT from a dict/list/str structure."""
    if isinstance(obj, str):
        return _redact_text(pat, obj)
    if isinstance(obj, list):
        return [_redact(pat, x) for x in obj]
    if isinstance(obj, dict):
        return {k: _redact(pat, v) for k, v in obj.items()}
    return obj
