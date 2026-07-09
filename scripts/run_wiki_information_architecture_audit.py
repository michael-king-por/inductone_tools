#!/usr/bin/env python3
"""Read-only Wiki information architecture audit.

This script inventories Wiki Pages and classifies likely cleanup candidates.
It does not mutate the site.  The intent is to keep Wiki cleanup aligned with
fixture governance: fixture-managed pages can be changed through the repo;
non-fixture pages should be reviewed by the owner before being edited or
depublished.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_SITE = "inductone-candidate.localhost"
DEFAULT_SITES_PATH = "/home/michaelplusone/frappe-sandbox/benches/candidate-bench/sites"
DEFAULT_EVIDENCE_DIR = Path("/mnt/c/hub/frappe-sandbox/validation-evidence")
REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_PATH = REPO_ROOT / "inductone_tools" / "hooks.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Wiki Page information architecture.")
    parser.add_argument("--site", default=DEFAULT_SITE)
    parser.add_argument("--sites-path", default=DEFAULT_SITES_PATH)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = args.evidence_dir / f"wiki_information_architecture_audit_{timestamp}.json"

    import frappe

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    try:
        fixture_managed = wiki_fixture_names(args.repo_root / "inductone_tools" / "hooks.py")
        pages = []
        for row in frappe.get_all(
            "Wiki Page",
            fields=["name", "title", "route", "published", "modified", "owner"],
            order_by="route asc",
            limit_page_length=1000,
        ):
            content = frappe.db.get_value("Wiki Page", row.name, "content") or ""
            pages.append(classify_page(row, content, fixture_managed))

        payload = {
            "site": args.site,
            "generated_at_utc": timestamp,
            "fixture_managed_names": sorted(fixture_managed),
            "summary": summarize(pages),
            "pages": pages,
            "recommendations": recommendations(pages),
        }
        evidence_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    finally:
        frappe.destroy()

    print(f"Evidence: {evidence_path}")
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    for rec in payload["recommendations"]:
        print(f"{rec['severity'].upper()}: {rec['title']} — {rec['recommendation']}")
    return 0


def wiki_fixture_names(hooks_path: Path) -> set[str]:
    if not hooks_path.exists():
        return set()
    tree = ast.parse(hooks_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "fixtures" for target in node.targets):
                return extract_wiki_names(ast.literal_eval(node.value))
    return set()


def extract_wiki_names(fixtures: list) -> set[str]:
    names: set[str] = set()
    for entry in fixtures:
        if not isinstance(entry, dict) or entry.get("dt") != "Wiki Page":
            continue
        for flt in entry.get("filters", []):
            if len(flt) == 3 and flt[0] == "name" and flt[1] == "in" and isinstance(flt[2], list):
                names.update(str(name) for name in flt[2])
    return names


def classify_page(row, content: str, fixture_managed: set[str]) -> dict:
    text = strip_html(content)
    headings = re.findall(r"(?m)^#{1,6}\s+", content)
    tables = content.count("<table") + len(re.findall(r"(?m)^\|.+\|$", content))
    images = content.count("<img") + content.count("![")
    svg_refs = content.count(".svg") + content.count("<svg")
    links = content.count("href=") + content.count("](")
    word_count = len(re.findall(r"\b\w+\b", text))

    flags = []
    if row.name in fixture_managed:
        flags.append("fixture_managed")
    else:
        flags.append("database_managed")
    if int(row.published or 0) == 0:
        flags.append("unpublished")
    if len(content.strip()) <= 80:
        flags.append("stub_or_redirect_sized")
    if word_count > 800 and svg_refs == 0:
        flags.append("long_page_no_svg")
    if headings == [] and word_count > 300:
        flags.append("long_page_no_markdown_headings")
    if "Builder" in content and "InductOne External Builder" not in content and "Builder Portal" not in content:
        flags.append("possible_legacy_builder_language")

    return {
        "name": row.name,
        "title": row.title,
        "route": row.route,
        "published": int(row.published or 0),
        "owner": row.owner,
        "modified": str(row.modified),
        "content_chars": len(content),
        "word_count": word_count,
        "heading_count": len(headings),
        "table_count": tables,
        "image_count": images,
        "svg_reference_count": svg_refs,
        "link_count": links,
        "flags": flags,
    }


def strip_html(content: str) -> str:
    content = re.sub(r"<script[\s\S]*?</script>", " ", content, flags=re.I)
    content = re.sub(r"<style[\s\S]*?</style>", " ", content, flags=re.I)
    content = re.sub(r"<[^>]+>", " ", content)
    return content


def summarize(pages: list[dict]) -> dict:
    return {
        "total_pages": len(pages),
        "published_pages": sum(1 for page in pages if page["published"]),
        "fixture_managed_pages": sum(1 for page in pages if "fixture_managed" in page["flags"]),
        "database_managed_pages": sum(1 for page in pages if "database_managed" in page["flags"]),
        "stub_or_redirect_sized": sum(1 for page in pages if "stub_or_redirect_sized" in page["flags"]),
        "long_page_no_svg": sum(1 for page in pages if "long_page_no_svg" in page["flags"]),
        "long_page_no_markdown_headings": sum(1 for page in pages if "long_page_no_markdown_headings" in page["flags"]),
    }


def recommendations(pages: list[dict]) -> list[dict]:
    out = []
    for page in pages:
        if "stub_or_redirect_sized" in page["flags"] and page["published"]:
            out.append({
                "severity": "review",
                "title": page["title"],
                "route": page["route"],
                "recommendation": "Published page is stub-sized. Either complete it, convert it to an intentional redirect, or depublish after owner review.",
            })
        if "long_page_no_svg" in page["flags"]:
            out.append({
                "severity": "improve",
                "title": page["title"],
                "route": page["route"],
                "recommendation": "Long operational page has no SVG/process visual. Consider adding a versioned visual map if the page explains workflow, gates, or artifact lineage.",
            })
    return out


if __name__ == "__main__":
    sys.exit(main())
