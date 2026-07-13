#!/usr/bin/env python3
"""Validate repo-managed Wiki Page fixtures.

This is intentionally local/read-only. It checks the safety properties that matter
for Wiki fixture ownership:

- wiki_page.json parses and has unique page names/routes
- hooks.py's exact-name Wiki Page filter matches the fixture names
- required CSA pages and SVG assets are present
- legacy role names do not reappear in managed content
- fixture pages are published and non-empty
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path


LEGACY_TERMS = [
    "Engineering - Signoff",
    "Engineering — Signoff",
    "InductOne Process Manager",
    "Part Number Manager",
    "Engineering Signoff Delegate",
    "InductOne Architect",
    "OPS-INDUCTONE-GATEKEEP",
    "PRODUCT-INDUCTONE-GATEKEEP",
]

REQUIRED_PAGES = {
    "inductone-csa-owner-handbook",
    "inductone-csa-quality-system",
    "inductone-csa-controlled-records-index",
    "3hmhgl7qdu",  # Configuration Options
    "3hmdga44m5",  # InductOne Build Pipeline
    "3hmiq2lbi9",  # Serialization Rules
    "3hngf036ne",  # Deviation Requests
    "3hmtouafd5",  # As-Built Records and Instances
    "82vdqj03n2",  # Snapshot Diff
    "3hmbhanak2",  # BOM Export Package
    "3hmeksuks8",  # Engineering Signoff
}

REQUIRED_ASSETS = {
    "inductone-csa-master-workflow.svg",
    "configuration-option-status-gate.svg",
    "builder-package-composition.svg",
    "as-built-instance-lineage.svg",
    "inductone-csa-quality-system-map.svg",
}


def parse_hooks_wiki_names(hooks_path: Path) -> list[str]:
    """Extract the exact Wiki Page name filter from hooks.py.

    The hooks file is Python, but importing it outside Frappe can have side effects.
    Use AST and only evaluate literal fixture structures.
    """

    tree = ast.parse(hooks_path.read_text(encoding="utf-8"))
    fixtures_node = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "fixtures":
                    fixtures_node = node.value
                    break
    if fixtures_node is None:
        raise AssertionError("hooks.py does not define fixtures")

    fixtures = ast.literal_eval(fixtures_node)
    wiki_entries = [entry for entry in fixtures if entry.get("dt") == "Wiki Page"]
    if len(wiki_entries) != 1:
        raise AssertionError(f"Expected exactly one Wiki Page fixture entry, found {len(wiki_entries)}")

    filters = wiki_entries[0].get("filters") or []
    for row in filters:
        if len(row) == 3 and row[0] == "name" and row[1] == "in":
            return list(row[2])
    raise AssertionError("Wiki Page fixture entry does not use an exact name/in filter")


def validate(repo_root: Path) -> dict:
    fixture_path = repo_root / "inductone_tools" / "fixtures" / "wiki_page.json"
    hooks_path = repo_root / "inductone_tools" / "hooks.py"
    svg_dir = repo_root / "inductone_tools" / "public" / "svg"

    pages = json.loads(fixture_path.read_text(encoding="utf-8"))
    names = [page.get("name") for page in pages]
    routes = [page.get("route") for page in pages]
    hook_names = parse_hooks_wiki_names(hooks_path)

    failures: list[str] = []
    if len(names) != len(set(names)):
        failures.append("Duplicate Wiki Page names exist in fixture")
    if len(routes) != len(set(routes)):
        failures.append("Duplicate Wiki Page routes exist in fixture")
    if set(names) != set(hook_names):
        failures.append(
            "hooks.py Wiki Page exact-name filter does not match wiki_page.json "
            f"(fixture_only={sorted(set(names)-set(hook_names))}, hook_only={sorted(set(hook_names)-set(names))})"
        )
    missing_required = sorted(REQUIRED_PAGES - set(names))
    if missing_required:
        failures.append(f"Required CSA Wiki pages missing from fixture: {missing_required}")

    missing_assets = sorted(asset for asset in REQUIRED_ASSETS if not (svg_dir / asset).exists())
    if missing_assets:
        failures.append(f"Required SVG assets missing: {missing_assets}")

    legacy_hits = []
    unresolved_asset_refs = []
    for page in pages:
        name = page.get("name")
        content = page.get("content") or ""
        if not page.get("published"):
            failures.append(f"{name}: page is not published")
        if len(content.strip()) < 100:
            failures.append(f"{name}: content is unexpectedly short")
        for term in LEGACY_TERMS:
            if term in content:
                legacy_hits.append({"page": name, "term": term})
        for match in re.finditer(r"/assets/inductone_tools/svg/([^\"')\s<>]+)", content):
            asset_name = match.group(1)
            if not (svg_dir / asset_name).exists():
                unresolved_asset_refs.append({"page": name, "asset": asset_name})

    if legacy_hits:
        failures.append(f"Legacy role references remain: {legacy_hits}")
    if unresolved_asset_refs:
        failures.append(f"Unresolved SVG asset references: {unresolved_asset_refs}")

    return {
        "fixture_path": str(fixture_path),
        "hooks_path": str(hooks_path),
        "page_count": len(pages),
        "hook_filter_count": len(hook_names),
        "page_names": names,
        "required_pages_present": sorted(REQUIRED_PAGES),
        "required_assets_present": sorted(REQUIRED_ASSETS),
        "legacy_hits": legacy_hits,
        "unresolved_asset_refs": unresolved_asset_refs,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Path to the inductone_tools repo root")
    parser.add_argument("--evidence", help="Optional JSON evidence output path")
    args = parser.parse_args()

    payload = validate(Path(args.repo_root).resolve())
    if args.evidence:
        evidence_path = Path(args.evidence)
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    for failure in payload["failures"]:
        print("FAIL", failure)
    if payload["status"] == "PASS":
        print(f"PASS wiki fixture validation ({payload['page_count']} pages)")
    else:
        print(f"FAIL wiki fixture validation ({len(payload['failures'])} failures)")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
