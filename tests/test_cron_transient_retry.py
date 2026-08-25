"""Transient-failure retries: an overload wave must not eat a whole cycle.

The CLI does not raise on an upstream failure it could not retry away — it
returns the text ``API Error: 529 Overloaded …`` as the run's result. Nerve
used to log that as a *success*: on 2026-08-24 three jobs (the weekly
ovd-berlin report among them) were wiped out by a five-minute overload window,
with no alert and no re-run, and the weekly one lost its whole week.

So a failed run whose error looks transient is now re-fired on a backoff
ladder, stays silent while a retry is pending, and survives a restart.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nerve.agent.engine import AgentEngine
from nerve.config import CronMessagesConfig
from nerve.cron.jobs import CronJob
from nerve.cron.service import (
    _TRANSIENT_FAILURE_MARKER,
    _TRANSIENT_RETRY_DELAYS,
    CronService,
    _is_transient_failure,
)

OVERLOADED = (
    "API Error: 529 Overloaded. https://platform.claude.com/docs/en/api/errors."
    " This is a server-side issue, usually temporary — try again in a moment."
)


# --------------------------------------------------------------------------- #
#  Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _make_service() -> CronService:
    config = MagicMock()
    config.cron.messages = CronMessagesConfig()
    config.timezone = "UTC"
    config.agent.cron_model = "test-model"
    config.proxy.enabled = True
    config.proxy.host = "127.0.0.1"
    config.proxy.port = 8317
    config.proxy.api_key = "sk-test"

    engine = AsyncMock()
    engine.run_cron = AsyncMock(return_value="ok")
    engine.run_persistent_cron = AsyncMock(return_value="ok")

    db = AsyncMock()
    db.log_cron_start = AsyncMock(return_value=1)
    db.log_cron_finish = AsyncMock()
    db.set_cron_log_session = AsyncMock()
    db.get_last_cron_run = AsyncMock(return_value=None)

    svc = CronService(config, engine, db)
    svc._notify_run_failure = AsyncMock()
    return svc


def _job(job_id: str = "weekly", enabled: bool = True, **kw) -> CronJob:
    return CronJob(id=job_id, schedule="0 11 * * mon", prompt="p",
                   enabled=enabled, **kw)


def _drain(svc: CronService) -> None:
    """Cancel sleeping re-fire tasks so a test never waits on the ladder."""
    for task in list(svc._transient_retry_tasks):
        task.cancel()
    svc._transient_retry_tasks.clear()


@asynccontextmanager
async def _auth_up():
    """Patch the proxy probe so _auth_available() reports credentials fine."""
    @asynccontextmanager
    async def _client_cm(*a, **k):
        client = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        client.post = AsyncMock(return_value=resp)
        yield client

    mock_client = MagicMock()
    mock_client.side_effect = lambda *a, **k: _client_cm(*a, **k)
    with patch("httpx.AsyncClient", mock_client):
        yield


# --------------------------------------------------------------------------- #
#  Classification                                                               #
# --------------------------------------------------------------------------- #

def test_run_failed_catches_cli_api_error():
    """The 529 text is a failed run, not a successful one with odd output."""
    assert AgentEngine._run_failed(OVERLOADED)
    assert AgentEngine._run_failed("  API Error: 500 Internal server error")
    assert not AgentEngine._run_failed("Report sent, 4 screenings listed.")


def test_is_transient_failure():
    assert _is_transient_failure(OVERLOADED)
    assert _is_transient_failure("API Error: 503 upstream connect error")
    assert _is_transient_failure("Agent error: request timed out")
    assert not _is_transient_failure("Agent error: KeyError('venue')")
    assert not _is_transient_failure("")


# --------------------------------------------------------------------------- #
#  _run_job_inner → retry queued                                                #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_overloaded_run_logs_error_and_queues_retry():
    svc = _make_service()
    svc.engine.run_cron = AsyncMock(return_value=OVERLOADED)
    async with _auth_up():
        await svc._run_job_inner(_job("weekly"))

    args, kwargs = svc.db.log_cron_finish.call_args
    assert args[1] == "error"  # status is positional
    assert kwargs["error"].startswith(_TRANSIENT_FAILURE_MARKER)
    assert svc._transient_attempts == {"weekly": 1}
    assert len(svc._transient_retry_tasks) == 1
    # Silent while a retry is pending — one alert at the end, not per attempt.
    svc._notify_run_failure.assert_not_called()
    _drain(svc)


@pytest.mark.asyncio
async def test_ladder_is_exhausted_then_the_failure_is_reported():
    svc = _make_service()
    svc.engine.run_cron = AsyncMock(return_value=OVERLOADED)
    job = _job("weekly")
    async with _auth_up():
        for _ in _TRANSIENT_RETRY_DELAYS:
            await svc._run_job_inner(job)
        assert svc._transient_attempts["weekly"] == len(_TRANSIENT_RETRY_DELAYS)
        svc._notify_run_failure.assert_not_called()

        # One failure past the ladder: plain error, user finally hears about it.
        await svc._run_job_inner(job)

    args, kwargs = svc.db.log_cron_finish.call_args
    assert args[1] == "error"
    assert not kwargs["error"].startswith(_TRANSIENT_FAILURE_MARKER)
    assert "weekly" not in svc._transient_attempts  # streak reset for next time
    svc._notify_run_failure.assert_awaited_once()
    _drain(svc)


@pytest.mark.asyncio
async def test_non_transient_failure_is_not_retried():
    svc = _make_service()
    svc.engine.run_cron = AsyncMock(return_value="Agent error: KeyError('venue')")
    async with _auth_up():
        await svc._run_job_inner(_job("weekly"))

    assert svc._transient_attempts == {}
    assert svc._transient_retry_tasks == set()
    svc._notify_run_failure.assert_awaited_once()


@pytest.mark.asyncio
async def test_success_clears_the_streak():
    svc = _make_service()
    svc._transient_attempts["weekly"] = 2
    svc.engine.run_cron = AsyncMock(return_value="Report sent.")
    await svc._run_job_inner(_job("weekly"))

    args, _ = svc.db.log_cron_finish.call_args
    assert args[1] == "success"
    assert svc._transient_attempts == {}


# --------------------------------------------------------------------------- #
#  _refire_after                                                                #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_refire_runs_the_current_job_object():
    svc = _make_service()
    live = _job("weekly")
    svc._jobs = [live]
    svc._run_job_wrapper = AsyncMock()
    await svc._refire_after("weekly", 0)
    svc._run_job_wrapper.assert_awaited_once_with(live)


@pytest.mark.asyncio
async def test_refire_skips_job_disabled_or_removed_while_sleeping():
    svc = _make_service()
    svc._jobs = [_job("weekly", enabled=False)]
    svc._transient_attempts["weekly"] = 1
    svc._run_job_wrapper = AsyncMock()
    await svc._refire_after("weekly", 0)
    svc._run_job_wrapper.assert_not_called()
    assert svc._transient_attempts == {}

    svc._jobs = []
    await svc._refire_after("ghost", 0)
    svc._run_job_wrapper.assert_not_called()


# --------------------------------------------------------------------------- #
#  _resume_transient_retries (restart during the backoff sleep)                 #
# --------------------------------------------------------------------------- #

def _finished(minutes_ago: int) -> str:
    ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return ts.isoformat()


@pytest.mark.asyncio
async def test_resume_refires_a_recent_marked_run():
    svc = _make_service()
    svc._jobs = [_job("weekly")]
    svc.db.get_last_cron_run = AsyncMock(return_value={
        "status": "error",
        "error": f"{_TRANSIENT_FAILURE_MARKER} {OVERLOADED}",
        "finished_at": _finished(3),
    })
    await svc._resume_transient_retries()

    assert svc._transient_attempts == {"weekly": 1}
    assert len(svc._transient_retry_tasks) == 1
    _drain(svc)


@pytest.mark.asyncio
async def test_resume_ignores_stale_runs_and_plain_errors():
    svc = _make_service()
    svc._jobs = [_job("stale"), _job("plain"), _job("off", enabled=False)]

    async def _last_run(job_id):
        if job_id == "stale":
            return {
                "status": "error",
                "error": f"{_TRANSIENT_FAILURE_MARKER} {OVERLOADED}",
                "finished_at": _finished(60 * 24),
            }
        return {"status": "error", "error": "boom", "finished_at": _finished(1)}

    svc.db.get_last_cron_run = AsyncMock(side_effect=_last_run)
    await svc._resume_transient_retries()

    assert svc._transient_attempts == {}
    assert svc._transient_retry_tasks == set()


@pytest.mark.asyncio
async def test_stop_cancels_pending_refires():
    svc = _make_service()
    svc.scheduler = MagicMock()
    task = asyncio.create_task(svc._refire_after("weekly", 3600))
    svc._transient_retry_tasks.add(task)
    await svc.stop()
    await asyncio.sleep(0)

    assert task.cancelled() or task.done()
    assert svc._transient_retry_tasks == set()
