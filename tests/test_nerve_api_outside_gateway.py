"""The agent's self-introspection must not look like an outage off-gateway.

`nerve cron <job>` builds its own engine and CronService in a plain CLI
process — no gateway, so `init_deps()` never ran and `_cron_service` is unset.
Every `nerve_api` call there used to come back as "Route dependencies not
initialized. Call init_deps() first.", and `/api/cron/jobs` answered with an
empty job list. On 2026-08-25 a manually fired healthcheck read exactly that
and reported a half-dead platform while the daemon was running 17 jobs fine.

So: the tool wires the deps itself from its own context, and the job listing
says 503 like every other route in that file instead of lying with `[]`.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def _clean_route_deps():
    """Route deps are a module global — never leak one test's into another."""
    from nerve.gateway.routes import _deps as deps_mod

    saved = deps_mod._deps
    deps_mod._deps = None
    yield deps_mod
    deps_mod._deps = saved


@pytest.fixture(autouse=True)
def _no_cron_service():
    """Pin the gateway's cron-service global to unset — the case under test.

    It is module state other tests also write, so assert it rather than
    inherit whatever ran before (a stray mock made this file pass alone and
    fail in the full suite).
    """
    from nerve.gateway import server as server_mod

    saved = server_mod._cron_service
    server_mod._cron_service = None
    yield
    server_mod._cron_service = saved


def _ctx(**kw):
    from nerve.agent.tools.registry import ToolContext

    kw.setdefault("session_id", "cron:nerve-healthcheck")
    return ToolContext(**kw)


class TestEnsureRouteDeps:
    def test_initializes_from_the_tool_context(self, _clean_route_deps):
        from nerve.agent.tools.handlers.mcp_admin import _ensure_route_deps

        engine, db = SimpleNamespace(name="engine"), SimpleNamespace(name="db")
        assert _ensure_route_deps(_ctx(engine=engine, db=db)) is None

        deps = _clean_route_deps.get_deps()
        assert deps.engine is engine
        assert deps.db is db

    def test_carries_the_notification_service_when_present(self, _clean_route_deps):
        from nerve.agent.tools.handlers.mcp_admin import _ensure_route_deps

        service = SimpleNamespace(name="notifications")
        _ensure_route_deps(_ctx(
            engine=SimpleNamespace(), db=SimpleNamespace(),
            notification_service=service,
        ))

        assert _clean_route_deps.get_deps().notification_service is service

    def test_leaves_an_initialized_container_alone(self, _clean_route_deps):
        from nerve.agent.tools.handlers.mcp_admin import _ensure_route_deps

        gateway_engine = SimpleNamespace(name="gateway")
        _clean_route_deps.init_deps(engine=gateway_engine, db=None)

        assert _ensure_route_deps(_ctx(engine=SimpleNamespace(), db=None)) is None
        assert _clean_route_deps.get_deps().engine is gateway_engine

    def test_reports_when_it_cannot_wire_anything(self, _clean_route_deps):
        from nerve.agent.tools.handlers.mcp_admin import _ensure_route_deps

        error = _ensure_route_deps(_ctx(engine=None, db=None))

        assert error and "nerve_api is unavailable" in error
        assert _clean_route_deps._deps is None


@pytest.mark.asyncio
async def test_nerve_api_handler_answers_without_a_gateway(_clean_route_deps):
    """End to end: the tool reaches a real route in a gateway-less process."""
    import nerve.config as cfg_mod
    from nerve.agent.tools.handlers.mcp_admin import nerve_api_handler
    from nerve.config import NerveConfig

    cfg = NerveConfig()
    cfg.auth.jwt_secret = ""  # require_auth becomes a no-op
    cfg_mod._config = cfg
    try:
        result = await nerve_api_handler(
            _ctx(engine=SimpleNamespace(), db=SimpleNamespace(), config=cfg),
            {"endpoint": "cron/jobs"},
        )
    finally:
        cfg_mod._config = None

    text = result.content if isinstance(result.content, str) else str(result.content)
    # No scheduler in this process, so 503 — but an honest 503, not the
    # "Route dependencies not initialized" wall it used to hit.
    assert "Route dependencies not initialized" not in text
    assert "503" in text


class TestListCronJobsWithoutService:
    def test_says_503_instead_of_an_empty_list(self, _clean_route_deps):
        import nerve.config as cfg_mod
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from nerve.config import NerveConfig
        from nerve.gateway.routes.cron import router

        cfg = NerveConfig()
        cfg.auth.jwt_secret = ""
        cfg_mod._config = cfg
        _clean_route_deps.init_deps(engine=SimpleNamespace(), db=None)
        try:
            app = FastAPI()
            app.include_router(router)
            resp = TestClient(app, raise_server_exceptions=False).get(
                "/api/cron/jobs",
            )
        finally:
            cfg_mod._config = None

        assert resp.status_code == 503
        assert "not available" in resp.json()["detail"]
