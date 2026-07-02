"""Validate sandbox restore freshness before permission validation.

This script is intentionally read-only. It reports the newest backup artifact
present in a site's private backups folder and a simple data high-water mark
from restored database content.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frappe


DEFAULT_EVIDENCE_DIR = Path("/mnt/c/hub/frappe-sandbox/validation-evidence")
HIGH_WATER_DOCTYPES = ("User", "Stock Entry", "Sales Order")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def newest_backup_file(backups_dir: Path) -> dict[str, Any] | None:
    if not backups_dir.exists():
        return None
    files = [path for path in backups_dir.iterdir() if path.is_file()]
    if not files:
        return None
    newest = max(files, key=lambda path: path.stat().st_mtime)
    mtime = datetime.fromtimestamp(newest.stat().st_mtime, tz=timezone.utc)
    return {
        "path": str(newest),
        "filename": newest.name,
        "size_bytes": newest.stat().st_size,
        "mtime_utc": mtime.isoformat(),
        "age_hours": (datetime.now(timezone.utc) - mtime).total_seconds() / 3600,
    }


def get_high_water_marks() -> list[dict[str, Any]]:
    rows = []
    for doctype in HIGH_WATER_DOCTYPES:
        try:
            value = frappe.db.get_value(doctype, {}, "max(modified)")
            rows.append({"doctype": doctype, "max_modified": str(value) if value else None, "error": None})
        except Exception as exc:  # noqa: BLE001 - evidence should capture exact Frappe failures.
            rows.append({"doctype": doctype, "max_modified": None, "error": f"{type(exc).__name__}: {exc}"})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", required=True, help="Bench root path, e.g. /home/.../candidate-bench")
    parser.add_argument("--site", required=True)
    parser.add_argument("--sites-path", help="Defaults to <bench>/sites")
    parser.add_argument("--max-age-hours", type=float, default=48)
    parser.add_argument("--expected-prod-backup-iso")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()

    bench = Path(args.bench).resolve()
    sites_path = Path(args.sites_path).resolve() if args.sites_path else bench / "sites"
    backups_dir = sites_path / args.site / "private" / "backups"
    expected = parse_iso(args.expected_prod_backup_iso)
    newest = newest_backup_file(backups_dir)

    stale_reasons: list[str] = []
    if not newest:
        stale_reasons.append(f"no backup files found in {backups_dir}")
    else:
        newest_mtime = parse_iso(newest["mtime_utc"])
        if newest["age_hours"] > args.max_age_hours:
            stale_reasons.append(
                f"newest backup file age {newest['age_hours']:.2f}h exceeds threshold {args.max_age_hours:.2f}h"
            )
        if expected and newest_mtime and newest_mtime < expected:
            stale_reasons.append(
                f"newest backup mtime {newest_mtime.isoformat()} is older than expected production backup "
                f"{expected.isoformat()}"
            )

    frappe.init(site=args.site, sites_path=str(sites_path))
    frappe.connect()
    try:
        high_water = get_high_water_marks()
    finally:
        frappe.destroy()

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "bench": str(bench),
        "site": args.site,
        "sites_path": str(sites_path),
        "backups_dir": str(backups_dir),
        "max_age_hours": args.max_age_hours,
        "expected_prod_backup_iso": expected.isoformat() if expected else None,
        "newest_backup_file": newest,
        "high_water_marks": high_water,
        "stale": bool(stale_reasons),
        "stale_reasons": stale_reasons,
    }

    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_site = args.site.replace(".", "_").replace(":", "_")
    out = args.evidence_dir / f"backup_freshness_{safe_site}_{stamp}.json"
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    status = "STALE" if payload["stale"] else "FRESH"
    newest_label = newest["filename"] if newest else "none"
    print(f"{status} {args.site}: newest_backup={newest_label} evidence={out}")
    for mark in high_water:
        print(f"HIGH_WATER {args.site} {mark['doctype']}: {mark['max_modified']} {mark['error'] or ''}".rstrip())
    for reason in stale_reasons:
        print(f"STALE_REASON {args.site}: {reason}")
    return 1 if payload["stale"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
