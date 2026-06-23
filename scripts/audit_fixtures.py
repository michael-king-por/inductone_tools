#!/usr/bin/env python3
"""
Audit fixture ownership and drift for InductOne Tools.

This script can run in two modes:

1. Repo-only mode:

       python scripts/audit_fixtures.py --repo .

   Reports fixture file counts and compares the explicit Client Script
   allowlist in hooks.py with rows in fixtures/client_script.json.

2. Bench comparison mode:

       env/bin/python scripts/audit_fixtures.py \
         --repo /path/to/inductone_tools \
         --bench /path/to/frappe-bench \
         --site inductone-candidate.localhost

   Also compares fixture rows against the restored site's database.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path


FIXTURE_DIR = Path("inductone_tools") / "fixtures"
HOOKS_PATH = Path("inductone_tools") / "hooks.py"


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def fixture_summary(repo: Path) -> dict:
    fixtures = {}
    for path in sorted((repo / FIXTURE_DIR).glob("*.json")):
        data = load_json(path)
        fixtures[path.name] = {
            "type": type(data).__name__,
            "count": len(data) if isinstance(data, list) else None,
            "names": [row.get("name") for row in data if isinstance(row, dict) and row.get("name")],
        }
    return fixtures


def hooks_fixture_config(repo: Path) -> list:
    text = (repo / HOOKS_PATH).read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "fixtures":
                    return ast.literal_eval(node.value)
    raise RuntimeError("Could not find fixtures assignment in hooks.py")


def client_script_allowlist(fixtures_config: list) -> list[str]:
    for entry in fixtures_config:
        if entry.get("dt") != "Client Script":
            continue
        filters = entry.get("filters") or []
        for flt in filters:
            if len(flt) == 3 and flt[0] == "name" and flt[1] == "in":
                return list(flt[2])
    return []


def repo_audit(repo: Path) -> dict:
    summary = fixture_summary(repo)
    config = hooks_fixture_config(repo)
    allowlist = client_script_allowlist(config)
    client_rows = summary.get("client_script.json", {}).get("names", [])

    return {
        "repo": str(repo),
        "fixture_files": {
            name: {"count": value["count"], "type": value["type"]}
            for name, value in summary.items()
        },
        "client_script_fixture_rows": client_rows,
        "client_script_allowlist": allowlist,
        "client_scripts_missing_from_allowlist": sorted(set(client_rows) - set(allowlist)),
        "client_scripts_allowlisted_but_not_fixture_rows": sorted(set(allowlist) - set(client_rows)),
        "broad_client_script_fixture": any(
            entry.get("dt") == "Client Script" and not entry.get("filters")
            for entry in config
        ),
    }


def db_audit(repo: Path, bench: Path, site: str) -> dict:
    import frappe

    os.chdir(bench)
    frappe.init(site=site, sites_path=str(bench / "sites"))
    frappe.connect()

    local = repo_audit(repo)
    allowlist = set(local["client_script_allowlist"])
    fixture_rows = set(local["client_script_fixture_rows"])

    db_client_scripts = {
        row["name"]
        for row in frappe.get_all(
            "Client Script",
            fields=["name"],
            limit_page_length=1000,
        )
    }

    out = {
        "site": site,
        "db_client_script_count": len(db_client_scripts),
        "db_client_scripts_matching_allowlist": sorted(db_client_scripts & allowlist),
        "allowlisted_client_scripts_missing_in_db": sorted(allowlist - db_client_scripts),
        "db_client_scripts_not_in_allowlist": sorted(db_client_scripts - allowlist),
        "fixture_client_scripts_missing_in_db": sorted(fixture_rows - db_client_scripts),
        "db_client_scripts_not_in_fixture": sorted(db_client_scripts - fixture_rows),
    }

    frappe.destroy()
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".", help="Path to the inductone_tools repo.")
    parser.add_argument("--bench", help="Optional path to a Frappe bench for DB comparison.")
    parser.add_argument("--site", help="Optional Frappe site name for DB comparison.")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    out = {"repo_audit": repo_audit(repo)}

    if args.bench or args.site:
        if not args.bench or not args.site:
            raise SystemExit("--bench and --site must be supplied together")
        out["db_audit"] = db_audit(repo, Path(args.bench).resolve(), args.site)

    print(json.dumps(out, indent=2))

    problems = []
    ra = out["repo_audit"]
    if ra["broad_client_script_fixture"]:
        problems.append("Client Script fixture is broad")
    if ra["client_scripts_missing_from_allowlist"]:
        problems.append("fixture Client Script rows missing from allowlist")
    if ra["client_scripts_allowlisted_but_not_fixture_rows"]:
        problems.append("allowlisted Client Scripts missing from fixture rows")
    if "db_audit" in out:
        da = out["db_audit"]
        if da["allowlisted_client_scripts_missing_in_db"]:
            problems.append("allowlisted Client Scripts missing in DB")
        if da["fixture_client_scripts_missing_in_db"]:
            problems.append("fixture Client Scripts missing in DB")

    if problems:
        print(json.dumps({"problems": problems}, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
