#!/usr/bin/env python3
"""Fail loudly if two migration files share a version number.

Runs from git hooks after merge/checkout/rebase. Deliberately uses only
the stdlib and never imports nerve — the whole point is to run when
nerve.db is too broken to import.

This collision has shipped three times (v027, v038 on Jul 13, v038+v039
from the ClickHouse merge on Jul 18 — the last one crash-looped the
service 279 times). The runner tracks MAX(version) only, so a duplicate
either kills startup or silently skips a migration forever.
"""

from __future__ import annotations

import pathlib
import re
import sys

MIGRATIONS = pathlib.Path(__file__).resolve().parents[1] / "nerve/db/migrations"


def main() -> int:
    if not MIGRATIONS.is_dir():
        return 0

    seen: dict[int, str] = {}
    dupes: list[str] = []
    for path in sorted(MIGRATIONS.glob("v*.py")):
        m = re.match(r"^v(\d+)_", path.name)
        if not m:
            continue
        version = int(m.group(1))
        if version in seen:
            dupes.append(f"  v{version:03d}: {seen[version]}  <->  {path.name}")
        else:
            seen[version] = path.name

    if dupes:
        highest = max(seen) if seen else 0
        sys.stderr.write(
            "\n\033[1;31m✗ DUPLICATE MIGRATION VERSIONS\033[0m\n"
            + "\n".join(dupes)
            + "\n\nnerve will NOT start until this is fixed.\n"
            f"Renumber the not-yet-applied file ABOVE the DB's current "
            f"version (highest on disk: v{highest:03d}) — numbering it below\n"
            "means the runner skips it forever.\n"
            "Check what's applied:  sqlite> SELECT MAX(version) FROM schema_version;\n\n"
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
