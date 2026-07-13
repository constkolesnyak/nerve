"""System-level tool handlers — nerve_restart.

``nerve_restart`` lets a running session restart the whole nerve daemon
and keep going afterwards, consciously aware it just rebooted. It works
by writing a *wakeup* (the same DB-backed re-injection channel used by
``ScheduleWakeup``) whose prompt is a restart-awareness banner plus the
caller's continuation text, clearing its own in-flight marker so the
startup resumer doesn't also enqueue a generic wakeup, then spawning a
detached ``nerve restart``. The process dies mid-turn; after the daemon
comes back the cron sweep fires the wakeup and the SDK session resumes
with full prior context.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime, timezone

from nerve.agent.tools.registry import ToolContext, ToolResult, ToolSpec
from nerve.agent.tools.schemas import NERVE_RESTART_SCHEMA

logger = logging.getLogger(__name__)


def _restart_banner(ts: str, continue_prompt: str) -> str:
    """Build the RESTART NOTICE banner injected on resume (self-restart)."""
    banner = (
        f"⚠️ RESTART NOTICE — the nerve service restarted at {ts}. "
        "Your previous turn in this session was interrupted mid-execution "
        "and you are now resumed with full prior context (SDK transcript "
        "intact). You are consciously aware you just came back from a "
        "restart. Re-read your last few messages to see what you were "
        "doing, then continue."
    )
    cp = (continue_prompt or "").strip()
    if cp:
        banner += f"\n\nContinuation: {cp}"
    return banner


async def nerve_restart_handler(ctx: ToolContext, args: dict) -> ToolResult:
    """Restart the nerve daemon and resume this session afterwards."""
    if ctx.db is None:
        return ToolResult.text("Database not available; cannot restart safely.", is_error=True)

    continue_prompt = (args.get("continue_prompt") or "").strip()
    if not continue_prompt:
        return ToolResult.text(
            "Missing 'continue_prompt' — describe what to keep doing after the restart.",
            is_error=True,
        )
    reason = (args.get("reason") or "").strip()

    # Fork-bomb guard: refuse if a self-restart wakeup is already pending
    # for this session (tool called twice in quick succession).
    try:
        pending = await ctx.db.list_pending_wakeups(ctx.session_id)
        if any(w.get("reason") == "self_restart" for w in pending):
            return ToolResult.text(
                "A self-restart is already in flight for this session — not restarting again.",
                is_error=True,
            )
    except Exception as e:  # non-fatal — proceed
        logger.warning("nerve_restart: pending-wakeup check failed: %s", e)

    now = datetime.now(timezone.utc)
    ts = now.isoformat()
    banner_prompt = _restart_banner(ts, continue_prompt)

    # 1. Persist the resume wakeup. Direct DB write bypasses the 60s
    #    ScheduleWakeup clamp; fire_at=now so the next sweep picks it up.
    try:
        await ctx.db.add_wakeup(
            ctx.session_id,
            prompt=banner_prompt,
            fire_at=ts,
            reason="self_restart",
        )
    except Exception as e:
        logger.error("nerve_restart: failed to persist wakeup: %s", e)
        return ToolResult.text(f"Could not schedule resume; aborting restart: {e}", is_error=True)

    # 2. Clear our own in-flight marker so the startup resumer won't also
    #    enqueue a generic restart wakeup (this richer one wins).
    try:
        await ctx.db.set_turn_in_flight(ctx.session_id, False)
    except Exception as e:
        logger.warning("nerve_restart: failed to clear turn_in_flight: %s", e)

    # 3. Spawn the detached restart (same pattern as the Telegram handler).
    logger.info(
        "nerve_restart: session=%s reason=%s — spawning `nerve restart`",
        ctx.session_id, reason or "(none)",
    )
    try:
        subprocess.Popen(
            [sys.executable, "-m", "nerve", "restart"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.error("nerve_restart: failed to spawn restart: %s", e)
        return ToolResult.text(f"Failed to spawn restart: {e}", is_error=True)

    # This result likely won't reach the model (the process is about to
    # die) — the wakeup carries the continuation context.
    return ToolResult.text(
        "Restart in flight. This session will resume automatically after the "
        "daemon comes back, with a RESTART NOTICE banner and your continuation."
    )


NERVE_RESTART_SPEC = ToolSpec(
    name="nerve_restart",
    description=(
        "Restart the entire nerve daemon and automatically resume THIS session "
        "afterwards, consciously aware you just rebooted. Use when you need a "
        "clean restart mid-task (e.g. after deploying new code, reloading config "
        "that requires a process restart, or recovering from a degraded state) "
        "without losing the thread of what you were doing. Provide 'continue_prompt' "
        "describing what to keep doing — it is re-injected after reboot behind a "
        "restart-awareness banner. The daemon dies within a second of calling this; "
        "the resume fires on the next wakeup sweep (~20s)."
    ),
    input_schema=NERVE_RESTART_SCHEMA,
    handler=nerve_restart_handler,
)


SYSTEM_SPECS = [
    NERVE_RESTART_SPEC,
]
