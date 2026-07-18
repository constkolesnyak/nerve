"""Auth-recovery watchdog: cron jobs re-fire the instant tokens return.

When the proxy runs out of credentials mid-run it returns 503 and the agent
surfaces an error *string* (engine.run does not raise). A weekly cron that dies
this way must not wait a week for its next tick — the watchdog queues it and
re-fires it within one sweep of auth being restored, and rebuilds that queue
from cron logs across a service restart.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nerve.config import CronMessagesConfig
from nerve.cron.jobs import CronJob
from nerve.cron.service import (
    _AUTH_FAILURE_MARKER,
    CronService,
)


# --------------------------------------------------------------------------- #
#  Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _make_service(proxy_enabled: bool = True) -> CronService:
    config = MagicMock()
    # Real catalog, not a MagicMock: alert text is str.format()-ed, and a
    # MagicMock would silently format into another MagicMock instead of a
    # string. Defaults are the shipped English ones, so these assertions stay
    # independent of whatever language an operator configures.
    config.cron.messages = CronMessagesConfig()
    config.timezone = "UTC"
    config.agent.cron_model = "test-model"
    config.proxy.enabled = proxy_enabled
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

    return CronService(config, engine, db)


def _job(job_id: str = "weekly", enabled: bool = True, **kw) -> CronJob:
    return CronJob(id=job_id, schedule="0 11 * * mon", prompt="p",
                   enabled=enabled, **kw)


def _patch_probe(status_code: int | None, *, raises: bool = False):
    """Patch httpx.AsyncClient so _auth_available sees a given proxy response."""
    @asynccontextmanager
    async def _client_cm(*a, **k):
        client = MagicMock()
        if raises:
            client.post = AsyncMock(side_effect=RuntimeError("boom"))
        else:
            resp = MagicMock()
            resp.status_code = status_code
            client.post = AsyncMock(return_value=resp)
        yield client

    mock_client = MagicMock()
    mock_client.side_effect = lambda *a, **k: _client_cm(*a, **k)
    return patch("httpx.AsyncClient", mock_client)


# --------------------------------------------------------------------------- #
#  _auth_available (ground-truth probe)                                         #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_auth_available_true_when_proxy_disabled():
    svc = _make_service(proxy_enabled=False)
    # No probe should be attempted; optimistic True.
    assert await svc._auth_available() is True


@pytest.mark.asyncio
async def test_auth_available_false_on_503():
    svc = _make_service()
    with _patch_probe(503):
        assert await svc._auth_available() is False


@pytest.mark.asyncio
async def test_auth_available_true_on_200():
    svc = _make_service()
    with _patch_probe(200):
        assert await svc._auth_available() is True


@pytest.mark.asyncio
async def test_auth_available_true_on_non_503_error():
    """A 400/401 still proves the credential path is live — not an outage."""
    svc = _make_service()
    with _patch_probe(400):
        assert await svc._auth_available() is True


@pytest.mark.asyncio
async def test_auth_available_false_on_network_error():
    svc = _make_service()
    with _patch_probe(None, raises=True):
        assert await svc._auth_available() is False


# --------------------------------------------------------------------------- #
#  _handle_failed_run                                                           #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_failed_run_with_auth_down_queues_job_and_marks_error():
    svc = _make_service()
    job = _job("weekly")
    with _patch_probe(503):
        await svc._handle_failed_run(job, log_id=1, session_id="s", error_text="Agent error: 503")

    assert "weekly" in svc._auth_retry_jobs
    _, kwargs = svc.db.log_cron_finish.call_args
    assert kwargs["error"].startswith(_AUTH_FAILURE_MARKER)


@pytest.mark.asyncio
async def test_failed_run_with_auth_up_is_plain_error():
    svc = _make_service()
    job = _job("weekly")
    with _patch_probe(200):
        await svc._handle_failed_run(job, log_id=1, session_id="s", error_text="boom")

    assert "weekly" not in svc._auth_retry_jobs
    _, kwargs = svc.db.log_cron_finish.call_args
    assert not kwargs["error"].startswith(_AUTH_FAILURE_MARKER)
    assert kwargs["error"] == "boom"


# --------------------------------------------------------------------------- #
#  _run_job_inner classification                                                #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_run_job_inner_error_sentinel_queues_when_auth_down():
    svc = _make_service()
    svc.engine.run_cron = AsyncMock(return_value="Agent error: 503 auth_unavailable")
    job = _job("weekly")
    with _patch_probe(503):
        await svc._run_job_inner(job)

    assert "weekly" in svc._auth_retry_jobs
    args, kwargs = svc.db.log_cron_finish.call_args
    assert args[1] == "error"  # status is positional
    assert kwargs["error"].startswith(_AUTH_FAILURE_MARKER)


@pytest.mark.asyncio
async def test_run_job_inner_success_logs_success_and_clears_queue():
    svc = _make_service()
    svc._auth_retry_jobs.add("weekly")  # stale from a prior failure
    svc.engine.run_cron = AsyncMock(return_value="Processed 3 emails.")
    job = _job("weekly")
    await svc._run_job_inner(job)

    assert "weekly" not in svc._auth_retry_jobs
    args, _ = svc.db.log_cron_finish.call_args
    assert args[1] == "success"  # status is positional


@pytest.mark.asyncio
async def test_run_job_inner_raised_exception_with_auth_down_queues():
    svc = _make_service()
    svc.engine.run_cron = AsyncMock(side_effect=RuntimeError("kaboom"))
    job = _job("weekly")
    with _patch_probe(503):
        await svc._run_job_inner(job)

    assert "weekly" in svc._auth_retry_jobs
    args, kwargs = svc.db.log_cron_finish.call_args
    assert args[1] == "error"  # status is positional
    assert kwargs["error"].startswith(_AUTH_FAILURE_MARKER)


# --------------------------------------------------------------------------- #
#  _auth_recovery_sweep                                                         #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_sweep_noop_when_queue_empty():
    svc = _make_service()
    # Probe must never be called when nothing is queued.
    with patch("httpx.AsyncClient") as client:
        await svc._auth_recovery_sweep()
        client.assert_not_called()


@pytest.mark.asyncio
async def test_sweep_keeps_queue_when_auth_still_down():
    svc = _make_service()
    svc._jobs = [_job("weekly")]
    svc._auth_retry_jobs.add("weekly")
    svc._run_job_wrapper = AsyncMock()
    with _patch_probe(503):
        await svc._auth_recovery_sweep()

    assert "weekly" in svc._auth_retry_jobs
    svc._run_job_wrapper.assert_not_called()


@pytest.mark.asyncio
async def test_sweep_refires_all_queued_jobs_on_recovery():
    svc = _make_service()
    svc._jobs = [_job("weekly"), _job("daily")]
    svc._auth_retry_jobs.update({"weekly", "daily"})
    fired: list[str] = []

    async def _fake_wrapper(job):
        fired.append(job.id)

    svc._run_job_wrapper = _fake_wrapper
    with _patch_probe(200):
        await svc._auth_recovery_sweep()
        # Let the scheduled re-fire tasks run.
        import asyncio
        await asyncio.sleep(0)

    assert svc._auth_retry_jobs == set()
    assert set(fired) == {"weekly", "daily"}


@pytest.mark.asyncio
async def test_sweep_skips_disabled_or_removed_jobs():
    svc = _make_service()
    svc._jobs = [_job("weekly", enabled=False)]  # disabled now
    svc._auth_retry_jobs.update({"weekly", "ghost"})  # ghost no longer defined
    svc._run_job_wrapper = AsyncMock()
    with _patch_probe(200):
        await svc._auth_recovery_sweep()
        import asyncio
        await asyncio.sleep(0)

    assert svc._auth_retry_jobs == set()
    svc._run_job_wrapper.assert_not_called()


# --------------------------------------------------------------------------- #
#  _reconstruct_auth_retry_jobs                                                 #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_reconstruct_queues_jobs_with_auth_marker():
    svc = _make_service()
    svc._jobs = [_job("weekly"), _job("daily")]

    async def _last_run(job_id):
        if job_id == "weekly":
            return {"status": "error", "error": f"{_AUTH_FAILURE_MARKER} Agent error: 503"}
        return {"status": "success", "error": None}

    svc.db.get_last_cron_run = AsyncMock(side_effect=_last_run)
    await svc._reconstruct_auth_retry_jobs()

    assert svc._auth_retry_jobs == {"weekly"}


@pytest.mark.asyncio
async def test_reconstruct_ignores_plain_errors_and_disabled():
    svc = _make_service()
    svc._jobs = [_job("plainerr"), _job("disabled", enabled=False)]

    async def _last_run(job_id):
        return {"status": "error", "error": "boom (no marker)"}

    svc.db.get_last_cron_run = AsyncMock(side_effect=_last_run)
    await svc._reconstruct_auth_retry_jobs()

    assert svc._auth_retry_jobs == set()


@pytest.mark.asyncio
async def test_reconstruct_marks_down_notified_when_queue_nonempty():
    """Restarting mid-outage must not re-alert 'tokens gone'."""
    svc = _make_service()
    svc._jobs = [_job("weekly")]

    async def _last_run(job_id):
        return {"status": "error", "error": f"{_AUTH_FAILURE_MARKER} 503"}

    svc.db.get_last_cron_run = AsyncMock(side_effect=_last_run)
    await svc._reconstruct_auth_retry_jobs()

    assert svc._auth_retry_jobs == {"weekly"}
    assert svc._auth_down_notified is True


# --------------------------------------------------------------------------- #
#  Telegram / system notifications                                             #
# --------------------------------------------------------------------------- #

def _attach_notify_spy(svc: CronService) -> AsyncMock:
    """Give the engine a notification service whose send is spy-able."""
    notif = MagicMock()
    notif.send_notification = AsyncMock()
    svc.engine.notification_service = notif
    return notif.send_notification


@pytest.mark.asyncio
async def test_auth_down_alert_fires_once_per_outage():
    svc = _make_service()
    send = _attach_notify_spy(svc)
    job_a, job_b = _job("weekly"), _job("daily")

    with _patch_probe(503):
        await svc._handle_failed_run(job_a, 1, "s", "Agent error: 503")
        await svc._handle_failed_run(job_b, 2, "s", "Agent error: 503")

    # Both jobs queued, but only one "tokens gone" alert.
    assert svc._auth_retry_jobs == {"weekly", "daily"}
    assert send.call_count == 1
    _, kwargs = send.call_args
    assert kwargs["priority"] == "urgent"
    assert "cron paused" in kwargs["title"]


@pytest.mark.asyncio
async def test_non_auth_error_alerts_every_time():
    svc = _make_service()
    send = _attach_notify_spy(svc)
    job = _job("weekly")

    with _patch_probe(200):
        await svc._handle_failed_run(job, 1, "s", "boom one")
        await svc._handle_failed_run(job, 2, "s", "boom two")

    # Real bugs alert on every failure — no edge-trigger.
    assert send.call_count == 2
    _, kwargs = send.call_args
    assert kwargs["priority"] == "high"
    assert "failed" in kwargs["title"]
    # Failures declare themselves as errors so 💀 is rendered centrally —
    # the marker is not baked into the title.
    assert kwargs["is_error"] is True
    assert "💀" not in kwargs["title"]


@pytest.mark.asyncio
async def test_empty_completion_does_not_alert():
    """An empty/blank completion is a benign no-op — no user-facing alert.

    The engine returns "" when the model ends a turn with no text. We
    classify that as failed (to discard the cursor buffer) but must not fire
    a run_failed notification with an empty body.
    """
    svc = _make_service()
    send = _attach_notify_spy(svc)
    job = _job("weekly")

    with _patch_probe(200):
        await svc._handle_failed_run(job, 1, "s", "")
        await svc._handle_failed_run(job, 2, "s", "   \n  ")

    assert send.call_count == 0


@pytest.mark.asyncio
async def test_recovery_alert_lists_jobs_and_resets_flag():
    svc = _make_service()
    send = _attach_notify_spy(svc)
    svc._jobs = [_job("weekly"), _job("daily")]
    svc._auth_retry_jobs.update({"weekly", "daily"})
    svc._auth_down_notified = True
    svc._run_job_wrapper = AsyncMock()

    with _patch_probe(200):
        await svc._auth_recovery_sweep()

    assert svc._auth_down_notified is False
    # One "tokens back" alert naming the re-fired jobs.
    recovery_calls = [
        c for c in send.call_args_list
        if "Tokens are back" in c.kwargs.get("title", "")
    ]
    assert len(recovery_calls) == 1
    body = recovery_calls[0].kwargs["body"]
    assert "weekly" in body and "daily" in body


@pytest.mark.asyncio
async def test_recovery_no_alert_when_nothing_fired():
    """If every queued job is now disabled/removed, no recovery alert."""
    svc = _make_service()
    send = _attach_notify_spy(svc)
    svc._jobs = [_job("weekly", enabled=False)]
    svc._auth_retry_jobs.update({"weekly", "ghost"})
    svc._auth_down_notified = True
    svc._run_job_wrapper = AsyncMock()

    with _patch_probe(200):
        await svc._auth_recovery_sweep()

    # Flag still resets, but no "tokens back" message with an empty list.
    assert svc._auth_down_notified is False
    recovery_calls = [
        c for c in send.call_args_list
        if "Tokens are back" in c.kwargs.get("title", "")
    ]
    assert recovery_calls == []


def test_plural_cron_simple_rule():
    """Default rule: singular only at exactly 1 — including 21, where the
    Slavic rule would wrongly pick the singular stem."""
    svc = _make_service()
    got = {n: svc._plural_cron(n) for n in (1, 2, 5, 11, 21, 22)}
    assert got == {1: "job", 2: "jobs", 5: "jobs",
                   11: "jobs", 21: "jobs", 22: "jobs"}


def test_plural_cron_slavic_rule():
    """Opt-in rule for languages with a 1 / 2-4 / 5+ split."""
    svc = _make_service()
    svc.config.cron.messages = CronMessagesConfig.from_dict({
        "plural_rule": "slavic",
        "plural_forms": ["one", "few", "many"],
    })
    got = {n: svc._plural_cron(n) for n in (1, 2, 5, 11, 21, 22)}
    assert got == {1: "one", 2: "few", 5: "many",
                   11: "many", 21: "one", 22: "few"}
