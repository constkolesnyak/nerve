"""Tests for the migration runner — discovery, ordering, idempotency."""

from __future__ import annotations

import pytest

from nerve.db import Database
from nerve.db.migrations.runner import (
    FORK_BAND_START,
    _check_no_duplicate_versions,
    discover_migrations,
    get_applied_versions,
)


# ---------------------------------------------------------------------------
# Duplicate-version guard
# ---------------------------------------------------------------------------


class TestNoDuplicateVersions:
    def test_unique_versions_ok(self):
        _check_no_duplicate_versions([(1, "v001_a"), (2, "v002_b"), (3, "v003_c")])

    def test_duplicate_raises(self):
        # Historical names, kept verbatim: the bug that broke usage tracking
        # was two v027 files coexisting, one silently winning while the other
        # was skipped forever. session_last_rotated has since moved to the
        # fork band (v900), which is why collisions like this cannot recur.
        with pytest.raises(RuntimeError, match="Duplicate migration version 27"):
            _check_no_duplicate_versions(
                [(27, "v027_cache_ttl_split"), (27, "v027_session_last_rotated")]
            )

    def test_duplicate_at_zero(self):
        with pytest.raises(RuntimeError, match="Duplicate migration version 0"):
            _check_no_duplicate_versions([(0, "v000_x"), (0, "v000_y")])

    def test_current_migrations_have_no_duplicates(self):
        # Regression check on the real on-disk set — if anyone adds a
        # collision later, this lights up before it ships.
        discovered = discover_migrations()
        versions = [v for v, _ in discovered]
        assert len(versions) == len(set(versions)), (
            f"Duplicate versions in nerve/db/migrations/: {discovered}"
        )

    def test_fork_migrations_live_in_the_band(self):
        # Fork-local migrations must never sit among upstream numbers, or the
        # next upstream sync collides again.
        fork = [n for v, n in discover_migrations() if v >= FORK_BAND_START]
        assert fork, "expected at least one fork-band migration"
        upstream = [v for v, _ in discover_migrations() if v < FORK_BAND_START]
        assert max(upstream) < FORK_BAND_START

    def test_discovered_list_is_sorted(self):
        discovered = discover_migrations()
        versions = [v for v, _ in discovered]
        assert versions == sorted(versions)


# ---------------------------------------------------------------------------
# v030 cache TTL split — idempotent re-application
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestV030Idempotent:
    async def test_running_v030_twice_is_noop(self, db: Database):
        # Fresh DB fixture has already rolled forward to head, which
        # includes v030. Running it again must not raise "duplicate column"
        # — DBs hand-patched between the buggy ship and this fix will hit
        # this exact case when the runner picks v030 up under its new number.
        from nerve.db.migrations import v027_cache_ttl_split

        await v027_cache_ttl_split.up(db.db)  # second run, should be a no-op

        async with db.db.execute("PRAGMA table_info(session_usage)") as cur:
            cols = {row[1] async for row in cur}
        assert "cache_creation_5m_input_tokens" in cols
        assert "cache_creation_1h_input_tokens" in cols


# ---------------------------------------------------------------------------
# Ledger semantics — what counts as "already applied"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAppliedVersionLedger:
    """``get_applied_versions`` replaced a MAX(version) high-water mark.

    The band only works because skipping is now per-version, but historical
    DBs were written by the MAX-only runner and can be sparse — so upstream
    numbers below the high-water mark must still count as applied.
    """

    @staticmethod
    async def _ledger(rows):
        import aiosqlite

        async with aiosqlite.connect(":memory:") as db:
            await db.execute(
                "CREATE TABLE schema_version (version INTEGER PRIMARY KEY)"
            )
            await db.executemany(
                "INSERT INTO schema_version VALUES (?)", [(v,) for v in rows]
            )
            await db.commit()
            return await get_applied_versions(db)

    async def test_legacy_max_only_ledger_implies_everything_below(self):
        # A DB written by the old runner may hold a single row.
        applied = await self._ledger([39])
        assert {1, 17, 39} <= applied

    async def test_sparse_ledger_does_not_rerun_the_gap(self):
        # This DB really was missing v026 while v027..v041 were recorded.
        applied = await self._ledger([1, 2, 39])
        assert 26 in applied

    async def test_band_row_never_implies_upstream_ran(self):
        # The dangerous direction: a v900 row must NOT mark upstream applied,
        # which is exactly what MAX(version) would have done.
        applied = await self._ledger([900])
        assert 1 not in applied
        assert 39 not in applied
        assert applied == {900}

    async def test_band_rows_are_explicit(self):
        applied = await self._ledger([39])
        assert FORK_BAND_START not in applied

    async def test_missing_table_reads_as_nothing_applied(self):
        import aiosqlite

        async with aiosqlite.connect(":memory:") as db:
            assert await get_applied_versions(db) == set()
