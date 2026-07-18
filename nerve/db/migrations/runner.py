"""Migration runner — discovers and applies numbered migration files."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)


# Fork-local migrations live in a reserved band above every upstream number.
# Upstream owns 1..899; anything the fork adds starts here. That way a sync
# from upstream never has to renumber a migration to make room, which is what
# produced the v027, v038 and v038+v039 collisions (the last one crash-looped
# the service 279 times on 2026-07-18).
FORK_BAND_START = 900


def _check_no_duplicate_versions(items: list[tuple[int, str]]) -> None:
    """Raise ``RuntimeError`` if two entries share the same version.

    The runner tracks ``MAX(version)`` only, so a duplicate would let
    one file silently win and the other be skipped forever — the kind
    of bug that costs hours to track down. It has bitten three times:
    cache_ttl_split shipped as v027 and collided with
    session_last_rotated, breaking usage tracking on every DB where the
    other v027 was applied first; then twice more on upstream syncs in
    July 2026. Fork-local migrations now live in the reserved band at
    :data:`FORK_BAND_START` so upstream numbers are never contested.
    """
    seen: dict[int, str] = {}
    for version, name in items:
        if version in seen:
            raise RuntimeError(
                f"Duplicate migration version {version}: "
                f"{seen[version]!r} and {name!r}. Renumber one of them."
            )
        seen[version] = name


def discover_migrations() -> list[tuple[int, str]]:
    """Scan the migrations package for vNNN_*.py files.

    Returns sorted list of (version, module_name) tuples. Raises if
    two files share the same version number.
    """
    migrations_dir = Path(__file__).parent
    results: list[tuple[int, str]] = []
    for info in pkgutil.iter_modules([str(migrations_dir)]):
        name = info.name
        if name.startswith("v") and "_" in name:
            try:
                version = int(name.split("_", 1)[0][1:])
                results.append((version, name))
            except ValueError:
                continue
    results.sort(key=lambda x: x[0])
    _check_no_duplicate_versions(results)
    return results


async def get_current_version(db: aiosqlite.Connection) -> int:
    """Read the highest recorded schema version (reporting only)."""
    try:
        async with db.execute("SELECT MAX(version) FROM schema_version") as cursor:
            row = await cursor.fetchone()
            return row[0] if row and row[0] else 0
    except Exception:
        return 0


async def get_applied_versions(db: aiosqlite.Connection) -> set[int]:
    """Versions already applied, per the ``schema_version`` ledger.

    The table has always stored one row per migration, but the runner used
    to compare against ``MAX(version)`` alone. That is why a reserved band
    was impossible: once a v900 row landed, every upstream migration below
    it would look applied and be skipped forever.

    Ledgers written by the old code can be sparse (this DB was missing
    v026), so every version at or below the highest recorded *upstream*
    version is still treated as applied — precisely what the old
    ``MAX`` comparison meant, so no historical DB re-runs anything.

    Band rows (>= :data:`FORK_BAND_START`) get no such benefit of the
    doubt: they count only when recorded explicitly, so a high band number
    can never imply that upstream migrations ran.
    """
    try:
        async with db.execute("SELECT version FROM schema_version") as cursor:
            applied = {
                int(row[0]) for row in await cursor.fetchall()
                if row and row[0] is not None
            }
    except Exception:
        return set()

    upstream = {v for v in applied if v < FORK_BAND_START}
    if upstream:
        applied |= set(range(1, max(upstream) + 1))
    return applied


async def run_migrations(db: aiosqlite.Connection) -> int:
    """Apply all pending migrations in order.

    Returns the final schema version after applying migrations.
    """
    already = await get_applied_versions(db)
    migrations = discover_migrations()

    applied = 0
    for version, module_name in migrations:
        if version in already:
            continue

        full_module = f"nerve.db.migrations.{module_name}"
        mod = importlib.import_module(full_module)

        if not hasattr(mod, "up"):
            logger.warning("Migration %s has no up() function, skipping", module_name)
            continue

        logger.info("Applying migration V%d (%s)...", version, module_name)
        try:
            await mod.up(db)
            await db.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (version,),
            )
            await db.commit()
            already.add(version)
            applied += 1
            logger.info("Migration V%d applied successfully", version)
        except Exception:
            logger.exception("Migration V%d failed", version)
            raise

    final_version = await get_current_version(db)
    if applied > 0:
        logger.info(
            "Database migrated to schema version %d (%d migrations applied)",
            final_version, applied,
        )
    return final_version
