"""Bot management endpoints - 32+ routes for bot lifecycle, runs, and configuration."""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import time
from datetime import datetime, timezone, timedelta

import fastapi
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, PlainTextResponse

from app.db import (
    get_bot_runs,
    get_bot_run_by_id,
    get_bot_run_logs,
    get_token_usage,
    get_token_usage_summary,
    complete_bot_run,
    get_bot_analytics,
)
from app.models import (
    BotScheduleUpdate,
    BotConfigUpdate,
    BotEnabledUpdate,
    CustomBotCreate,
    BotStartRequest,
)
from app.user_context import get_user_id
from app.bot_manager import bot_manager
from app.event_bus import event_bus
from app.sse import format_bot_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bots", tags=["bots"])

# ── Bot name validation helper ──

_VALID_BOT_NAME = re.compile(r"^[a-z][a-z0-9_]{1,48}$")

# Simple in-memory rate limiter: bot_name -> last_start_timestamp
_bot_start_timestamps: dict[str, float] = {}
_BOT_START_COOLDOWN_S = 30  # Minimum seconds between manual starts


def _validate_bot_name(name: str, must_exist: bool = True) -> None:
    """Validate bot name format to prevent injection."""
    if not _VALID_BOT_NAME.match(name):
        raise HTTPException(status_code=400, detail=f"Invalid bot name: {name}")
    if must_exist:
        state = bot_manager.get_bot_state(name)
        if not state:
            raise HTTPException(status_code=404, detail=f"Bot '{name}' not found")


# ── Bot health/metrics endpoint ──

@router.get("/health")
async def bots_health(user_id: str = Depends(get_user_id)):
    """Health check for bot system with metrics."""
    states = bot_manager.get_all_states()
    running = sum(1 for s in states if s.get("status") == "running")
    errored = sum(1 for s in states if s.get("status") == "errored")
    try:
        usage = await get_token_usage_summary()
        total_cost = usage.get("total_cost", 0)
        total_runs = usage.get("total_runs", 0)
    except Exception:
        total_cost = 0
        total_runs = 0

    # Detect stale bots (no run in 48+ hours)
    now = datetime.now(timezone.utc)
    stale = []
    for s in states:
        last_run = s.get("last_run_at")
        if last_run:
            try:
                lrt = datetime.fromisoformat(last_run)
                if lrt < now - timedelta(hours=48) and s.get("status") not in ("stopped", "disabled"):
                    stale.append(s.get("name", ""))
            except Exception:
                pass

    status = "healthy"
    if errored > 0:
        status = "degraded"
    if errored > len(states) / 2:
        status = "critical"

    # Include activation system diagnostics
    scheduler_info = bot_manager.get_scheduler_status()

    return {
        "status": status,
        "bots_total": len(states),
        "bots_running": running,
        "bots_errored": errored,
        "bots_stale": stale,
        "sse_subscribers": event_bus.subscriber_count,
        "total_runs": total_runs,
        "total_cost": total_cost,
        "scheduler": scheduler_info,
    }


@router.get("")
async def list_bots(user_id: str = Depends(get_user_id)):
    """List all bots with current state."""
    states = bot_manager.get_all_states()
    return {"bots": states}


@router.get("/token-usage")
async def bots_token_usage(bot: str | None = None, period: str = "daily", user_id: str = Depends(get_user_id)):
    """Get aggregated token usage and costs."""
    if bot:
        records = await get_token_usage(bot_name=bot, period=period)
        return {"usage": records}
    summary = await get_token_usage_summary()
    return summary


@router.get("/events/stream")
async def bots_event_stream(request: fastapi.Request, user_id: str = Depends(get_user_id)):
    """SSE stream for all bot activity with reconnection support."""
    # Support Last-Event-ID for reconnection replay
    last_event_id_str = request.headers.get("Last-Event-ID")
    last_event_id = int(last_event_id_str) if last_event_id_str else None

    async def event_generator():
        # Send initial state snapshot
        states = bot_manager.get_all_states()
        yield format_bot_event({"type": "bots_state", "bots": states})

        # Send token usage summary
        try:
            usage = await get_token_usage_summary()
            yield format_bot_event({"type": "token_usage_update", **usage})
        except Exception:
            pass

        # Stream live events (with replay if reconnecting)
        async for ev in event_bus.subscribe(last_event_id=last_event_id):
            eid = ev.get("event_id", "")
            yield f"id: {eid}\ndata: {json.dumps(ev)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/tools")
async def list_available_tools(user_id: str = Depends(get_user_id)):
    """List all available tools that can be assigned to custom bots."""
    from app.tools import TOOL_REGISTRY
    tools = []
    # Categorize tools
    categories = {
        "resume": ["review_resume", "extract_resume_profile"],
        "jobs": ["search_jobs", "search_jobs_for_resume", "get_saved_jobs", "save_job", "get_job_pipeline",
                 "update_job_stage", "prepare_job_application", "generate_cover_letter"],
        "research": ["web_search", "get_search_history", "get_user_job_interests"],
        "leetcode": ["get_leetcode_progress", "select_leetcode_problems", "log_leetcode_attempt_tool"],
        "integrations": ["send_notification", "call_webhook"],
        "prep": ["generate_prep_materials"],
        "bots": ["manage_bot"],
        "journal": ["add_journal_entry"],
    }
    cat_lookup = {}
    for cat, names in categories.items():
        for n in names:
            cat_lookup[n] = cat

    for name, tool_obj in TOOL_REGISTRY.items():
        desc = ""
        if hasattr(tool_obj, "description"):
            desc = tool_obj.description[:200]
        tools.append({
            "name": name,
            "description": desc,
            "category": cat_lookup.get(name, "other"),
        })
    return {"tools": tools}


@router.get("/trigger-map")
async def bots_trigger_map(user_id: str = Depends(get_user_id)):
    """Return the dependency/trigger map showing which bots can trigger other bots."""
    from app.bot_config import get_bots_config
    bots_config = get_bots_config()
    nodes = []
    edges = []
    for name, cfg in bots_config.bots.items():
        nodes.append({
            "id": name,
            "display_name": cfg.display_name,
            "triggers": list(cfg.trigger_on),
            "schedule": cfg.schedule.type if cfg.schedule else None,
        })
        # Build edges: if this bot triggers on "bot_completed:X", create X -> this edge
        for trigger in cfg.trigger_on:
            if trigger.startswith("bot_completed:"):
                source = trigger.split(":", 1)[1]
                edges.append({"from": source, "to": name, "type": "chain", "label": "on complete"})
            elif trigger == "job_saved":
                # Any bot that uses save_job could trigger this
                for other_name, other_cfg in bots_config.bots.items():
                    if "save_job" in other_cfg.tools and other_name != name:
                        edges.append({"from": other_name, "to": name, "type": "event", "label": "job_saved"})
            elif trigger.startswith("stage_"):
                stage = trigger.replace("stage_", "")
                for other_name, other_cfg in bots_config.bots.items():
                    if "update_job_stage" in other_cfg.tools and other_name != name:
                        edges.append({"from": other_name, "to": name, "type": "event", "label": f"stage → {stage}"})
    return {"nodes": nodes, "edges": edges}


@router.get("/calendar")
async def bots_calendar(days: int = 7, user_id: str = Depends(get_user_id)):
    """Return scheduled bot runs for the next N days as calendar entries."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    states = bot_manager.get_all_states()
    entries = []

    for s in states:
        if s.get("status") in ("stopped", "disabled"):
            continue
        schedule = s.get("config", {}).get("schedule", {})
        if not schedule or not schedule.get("type"):
            continue

        bot_name = s.get("name", "")
        display_name = s.get("display_name", bot_name)
        status = s.get("status", "scheduled")

        if schedule.get("type") == "interval":
            hours = schedule.get("hours") or 0
            mins = schedule.get("minutes") or 0
            if hours > 0:
                interval = timedelta(hours=hours)
            elif mins > 0:
                interval = timedelta(minutes=mins)
            else:
                interval = timedelta(hours=6)  # default

            # Start from last_run + interval, or now if no last run
            last_run = s.get("last_run_at")
            if last_run:
                try:
                    t = datetime.fromisoformat(last_run) + interval
                except Exception:
                    t = now
            else:
                t = now + interval

            # Generate entries until end of range
            count = 0
            while t < end and count < 100:
                if t >= now:
                    entries.append({
                        "bot_name": bot_name,
                        "display_name": display_name,
                        "time": t.isoformat(),
                        "type": "interval",
                        "status": status,
                    })
                    count += 1
                t += interval

        elif schedule.get("type") == "cron":
            hour = schedule.get("hour")
            minute = schedule.get("minute")
            if hour is None:
                hour = 0
            if minute is None:
                minute = 0

            for d in range(days + 1):
                t = (now + timedelta(days=d)).replace(
                    hour=hour, minute=minute, second=0, microsecond=0,
                )
                if now <= t < end:
                    entries.append({
                        "bot_name": bot_name,
                        "display_name": display_name,
                        "time": t.isoformat(),
                        "type": "cron",
                        "status": status,
                    })

    entries.sort(key=lambda e: e["time"])
    return {"entries": entries, "days": days}


@router.get("/templates")
async def list_bot_templates(user_id: str = Depends(get_user_id)):
    """Return pre-built bot templates for easy creation."""
    return {"templates": [
        {
            "id": "daily_reporter",
            "name": "Daily Reporter",
            "description": "Sends a daily summary of your job search progress to Slack or Telegram",
            "icon": "report",
            "tools": ["get_saved_jobs", "get_job_pipeline", "send_notification"],
            "prompt": "You are a Daily Reporter bot. Summarize the user's job search pipeline daily. Include counts by stage, recent changes, and upcoming actions. Send the summary via the configured notification channel.",
            "schedule_type": "cron",
            "schedule_hour": 18,
            "schedule_minute": 0,
            "model": "fast",
            "integrations": ["telegram", "slack", "discord"],
        },
        {
            "id": "application_tracker",
            "name": "Application Tracker",
            "description": "Watches for application status changes and alerts you immediately",
            "icon": "track",
            "tools": ["get_saved_jobs", "get_job_pipeline", "web_search", "send_notification"],
            "prompt": "You are an Application Tracker bot. Check if any job applications have changed status. Research company hiring timelines. Alert the user about stale applications and recommend follow-ups.",
            "schedule_type": "interval",
            "schedule_hours": 4,
            "model": "fast",
            "integrations": ["telegram", "slack", "webhook"],
        },
        {
            "id": "company_watcher",
            "name": "Company Watcher",
            "description": "Monitors target companies for news, layoffs, expansions, and new openings",
            "icon": "watch",
            "tools": ["get_saved_jobs", "web_search", "send_notification"],
            "prompt": "You are a Company Watcher bot. For each company in the user's job pipeline, search for recent news, press releases, and job postings. Flag important changes like layoffs, funding rounds, or new team expansions.",
            "schedule_type": "interval",
            "schedule_hours": 12,
            "model": "default",
            "integrations": ["telegram", "slack"],
        },
        {
            "id": "custom_webhook",
            "name": "Custom Webhook Bot",
            "description": "Runs a custom prompt and sends results to any webhook endpoint",
            "icon": "webhook",
            "tools": ["web_search", "call_webhook", "get_saved_jobs"],
            "prompt": "You are a custom webhook bot. Execute the user's instructions and send results to the configured webhook endpoint.",
            "schedule_type": "interval",
            "schedule_hours": 6,
            "model": "fast",
            "integrations": ["webhook"],
        },
        {
            "id": "interview_reminder",
            "name": "Interview Reminder",
            "description": "Sends prep materials and reminders before interviews via your preferred channel",
            "icon": "interview",
            "tools": ["get_saved_jobs", "get_job_pipeline", "web_search", "extract_resume_profile", "send_notification"],
            "prompt": "You are an Interview Reminder bot. Check for jobs in the 'interview' stage. Research the company, prepare key talking points, and send a prep digest to the user via their preferred notification channel. Include STAR stories from their resume that match the role.",
            "schedule_type": "interval",
            "schedule_hours": 6,
            "model": "default",
            "integrations": ["telegram", "slack", "whatsapp"],
        },
    ]}


@router.get("/{name}")
async def get_bot(name: str, user_id: str = Depends(get_user_id)):
    """Get single bot detail with recent runs."""
    _validate_bot_name(name)
    state = bot_manager.get_bot_state(name)
    runs = await get_bot_runs(name, limit=10, user_id=user_id)
    return {"bot": state, "recent_runs": runs}


@router.post("/{name}/start")
async def start_bot(name: str, body: BotStartRequest | None = None, user_id: str = Depends(get_user_id)):
    """Trigger an immediate bot run with rate limiting and optional context."""
    _validate_bot_name(name)
    now = time.monotonic()
    last = _bot_start_timestamps.get(name, 0)
    if now - last < _BOT_START_COOLDOWN_S:
        remaining = int(_BOT_START_COOLDOWN_S - (now - last))
        raise HTTPException(status_code=429, detail=f"Rate limited. Try again in {remaining}s.")
    _bot_start_timestamps[name] = now
    context = body.context if body else None
    result = await bot_manager.start_bot(name, trigger_type="manual", context=context, user_id=user_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{name}/stop")
async def stop_bot(name: str, user_id: str = Depends(get_user_id)):
    """Stop a running bot and cancel its schedule."""
    _validate_bot_name(name)
    return await bot_manager.stop_bot(name)


@router.post("/{name}/pause")
async def pause_bot(name: str, user_id: str = Depends(get_user_id)):
    """Pause a bot's schedule."""
    _validate_bot_name(name)
    return await bot_manager.pause_bot(name)


@router.post("/{name}/resume")
async def resume_bot(name: str, user_id: str = Depends(get_user_id)):
    """Resume a paused bot's schedule."""
    _validate_bot_name(name)
    return await bot_manager.resume_bot(name)


@router.put("/{name}/schedule")
async def update_bot_schedule(name: str, body: BotScheduleUpdate, user_id: str = Depends(get_user_id)):
    """Update a bot's schedule configuration."""
    _validate_bot_name(name)
    result = await bot_manager.update_schedule(name, {
        "type": body.schedule_type,
        **body.schedule_config,
    })
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.put("/{name}/config")
async def update_bot_config(name: str, body: BotConfigUpdate, user_id: str = Depends(get_user_id)):
    """Update bot parameters."""
    _validate_bot_name(name)
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    result = await bot_manager.update_config(name, update)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.put("/{name}/enabled")
async def set_bot_enabled(name: str, body: BotEnabledUpdate, user_id: str = Depends(get_user_id)):
    """Enable or disable a bot."""
    _validate_bot_name(name)
    return await bot_manager.set_enabled(name, body.enabled)


@router.get("/{name}/analytics")
async def bot_analytics_endpoint(name: str, user_id: str = Depends(get_user_id)):
    """Get aggregated analytics for a bot."""
    _validate_bot_name(name)
    return await get_bot_analytics(name)


@router.get("/{name}/runs")
async def list_bot_runs(
    name: str,
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
    search: str | None = None,
    user_id: str = Depends(get_user_id),
):
    """Get run history for a bot with pagination, status filter, and output search."""
    _validate_bot_name(name)
    if limit > 100:
        limit = 100
    runs = await get_bot_runs(name, limit=min(limit, 500) if search else limit,
                               status_filter=status, search_query=search)
    # Apply offset/limit after search
    paginated = runs[offset:offset + limit] if offset else runs[:limit]
    return {"runs": paginated, "total": len(runs), "limit": limit, "offset": offset}


@router.get("/{name}/runs/{run_id}")
async def get_bot_run(name: str, run_id: str, user_id: str = Depends(get_user_id)):
    """Get run detail with full output."""
    _validate_bot_name(name)
    if not re.match(r"^[a-f0-9]{8,32}$", run_id):
        raise HTTPException(status_code=400, detail="Invalid run ID format")
    run = await get_bot_run_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    logs = await get_bot_run_logs(run_id)
    return {"run": run, "logs": logs}


@router.get("/{name}/runs/{run_id}/logs")
async def get_run_logs(name: str, run_id: str, user_id: str = Depends(get_user_id)):
    """Get log entries for a run."""
    _validate_bot_name(name)
    if not re.match(r"^[a-f0-9]{8,32}$", run_id):
        raise HTTPException(status_code=400, detail="Invalid run ID format")
    logs = await get_bot_run_logs(run_id)
    return {"logs": logs}


@router.get("/{name}/runs/{run_id}/export")
async def export_run(name: str, run_id: str, user_id: str = Depends(get_user_id)):
    """Export run output as plain text for download."""
    _validate_bot_name(name)
    run = await get_bot_run_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return PlainTextResponse(
        content=run.get("output", ""),
        headers={"Content-Disposition": f"attachment; filename={name}_{run_id}.txt"},
    )


@router.get("/{name}/runs/export")
async def export_runs_csv(name: str, limit: int = 100, user_id: str = Depends(get_user_id)):
    """Export run history as CSV."""
    _validate_bot_name(name)
    runs = await get_bot_runs(name, limit=min(limit, 500))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["run_id", "status", "trigger_type", "started_at", "completed_at",
                      "duration_s", "input_tokens", "output_tokens", "cost"])
    for r in runs:
        started = r.get("started_at", "")
        completed = r.get("completed_at", "")
        duration = ""
        if started and completed:
            try:
                s = datetime.fromisoformat(started) if isinstance(started, str) else started
                e = datetime.fromisoformat(completed) if isinstance(completed, str) else completed
                duration = f"{(e - s).total_seconds():.1f}"
            except Exception:
                pass
        writer.writerow([
            r.get("run_id", ""), r.get("status", ""), r.get("trigger_type", ""),
            started, completed, duration,
            r.get("input_tokens", 0), r.get("output_tokens", 0), r.get("cost", 0),
        ])
    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={name}_runs.csv"},
    )


@router.post("/{name}/runs/{run_id}/approve")
async def approve_bot_run(name: str, run_id: str, user_id: str = Depends(get_user_id)):
    """Approve a bot run that's awaiting approval."""
    _validate_bot_name(name)
    run = await get_bot_run_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.get("status") != "awaiting_approval":
        raise HTTPException(status_code=400, detail=f"Run status is '{run.get('status')}', not awaiting_approval")
    await complete_bot_run(
        run_id=run_id, status="approved", output=run.get("output", ""),
        input_tokens=run.get("input_tokens", 0), output_tokens=run.get("output_tokens", 0),
        cost=run.get("cost", 0),
    )
    await event_bus.publish({
        "type": "bot_run_approved",
        "bot_name": name,
        "run_id": run_id,
    })
    return {"status": "approved", "run_id": run_id}


@router.post("/{name}/runs/{run_id}/reject")
async def reject_bot_run(name: str, run_id: str, user_id: str = Depends(get_user_id)):
    """Reject a bot run that's awaiting approval."""
    _validate_bot_name(name)
    run = await get_bot_run_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.get("status") != "awaiting_approval":
        raise HTTPException(status_code=400, detail=f"Run status is '{run.get('status')}', not awaiting_approval")
    await complete_bot_run(
        run_id=run_id, status="rejected", output=run.get("output", ""),
        input_tokens=run.get("input_tokens", 0), output_tokens=run.get("output_tokens", 0),
        cost=run.get("cost", 0),
    )
    await event_bus.publish({
        "type": "bot_run_rejected",
        "bot_name": name,
        "run_id": run_id,
    })
    return {"status": "rejected", "run_id": run_id}


@router.post("/{name}/runs/{run_id}/retry")
async def retry_bot_run(name: str, run_id: str, user_id: str = Depends(get_user_id)):
    """Retry a failed bot run manually."""
    _validate_bot_name(name)
    run = await get_bot_run_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.get("status") not in ("errored", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Can only retry errored or cancelled runs")
    # Start a fresh run for this bot
    result = await bot_manager.start_bot(name, trigger_type="retry", user_id=user_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "retrying", "new_run": result}


@router.post("/start-all")
async def start_all_bots(user_id: str = Depends(get_user_id)):
    """Start all enabled bots."""
    results = await bot_manager.start_all()
    return {"results": results}


@router.post("/stop-all")
async def stop_all_bots(user_id: str = Depends(get_user_id)):
    """Stop all running bots."""
    results = await bot_manager.stop_all()
    return {"results": results}


@router.post("/event/{event_name}")
async def bot_event_trigger(event_name: str, user_id: str = Depends(get_user_id)):
    """Emit an external event that may trigger bots."""
    await bot_manager.handle_event(event_name)
    return {"ok": True, "event": event_name}


@router.post("/webhooks/ingest")
async def webhook_ingest(request: fastapi.Request, user_id: str = Depends(get_user_id)):
    """Accept external webhook payloads and trigger matching bots.

    Supports:
    - GitHub webhooks (job_saved on starred repos, etc.)
    - Calendar webhooks (stage_interview when interview is scheduled)
    - Generic payloads with explicit event_name field

    Authenticate via X-Webhook-Secret header matching WEBHOOK_SECRET env var.
    """
    import os
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if secret:
        provided = request.headers.get("X-Webhook-Secret", "")
        if provided != secret:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Extract event name from payload
    event_name = body.get("event_name") or body.get("event") or body.get("action")
    if not event_name:
        # Try to detect from known webhook formats
        if "pull_request" in body or "repository" in body:
            event_name = f"github_{body.get('action', 'push')}"
        elif "calendar" in str(body).lower() or "event" in body:
            event_name = "calendar_event"
        else:
            event_name = "webhook_received"

    # Sanitize event name
    event_name = re.sub(r"[^a-z0-9_]", "_", event_name.lower().strip())[:50]

    await bot_manager.handle_event(event_name)

    # Also publish to SSE for visibility
    await event_bus.publish({
        "type": "webhook_received",
        "event_name": event_name,
        "source": body.get("source", "external"),
    })

    return {"ok": True, "event": event_name, "triggered": True}


@router.post("/create")
async def create_custom_bot(body: CustomBotCreate, user_id: str = Depends(get_user_id)):
    """Create a new custom bot at runtime."""
    from app.bot_config import BotConfig, BotScheduleConfig
    from app.tools import TOOL_REGISTRY

    # Validate tools exist
    for tool_name in body.tools:
        if tool_name not in TOOL_REGISTRY:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")

    # Build schedule config
    if body.schedule_type == "interval":
        schedule = BotScheduleConfig(type="interval", hours=body.schedule_hours or 6)
    elif body.schedule_type == "cron":
        schedule = BotScheduleConfig(type="cron", hour=body.schedule_hour, minute=body.schedule_minute or 0)
    else:
        raise HTTPException(status_code=400, detail="schedule_type must be 'interval' or 'cron'")

    bot_config = BotConfig(
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        model=body.model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        tools=body.tools,
        prompt=body.prompt,
        schedule=schedule,
        requires_approval=body.requires_approval,
        timeout_minutes=body.timeout_minutes,
        is_custom=True,
        integrations=body.integrations,
    )

    result = await bot_manager.create_custom_bot(bot_config)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/{name}")
async def delete_custom_bot(name: str, user_id: str = Depends(get_user_id)):
    """Delete a custom bot."""
    _validate_bot_name(name)
    result = await bot_manager.delete_custom_bot(name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{name}/duplicate")
async def duplicate_bot(name: str, user_id: str = Depends(get_user_id)):
    """Duplicate an existing bot as a custom bot."""
    _validate_bot_name(name)
    from app.bot_config import get_bots_config, BotConfig, BotScheduleConfig
    import copy
    bots_config = get_bots_config()
    source_cfg = bots_config.bots.get(name)
    if not source_cfg:
        raise HTTPException(status_code=404, detail=f"Bot '{name}' not found")

    # Generate unique name
    copy_num = 1
    while f"{name}_copy{copy_num}" in bots_config.bots:
        copy_num += 1
    new_name = f"{name}_copy{copy_num}"

    new_cfg = BotConfig(
        name=new_name,
        display_name=f"{source_cfg.display_name} (Copy)",
        description=source_cfg.description,
        model=source_cfg.model,
        temperature=source_cfg.temperature,
        max_tokens=source_cfg.max_tokens,
        tools=list(source_cfg.tools),
        schedule=copy.deepcopy(source_cfg.schedule),
        trigger_on=list(source_cfg.trigger_on),
        requires_approval=source_cfg.requires_approval,
        approval_type=source_cfg.approval_type,
        approval_priority=source_cfg.approval_priority,
        timeout_minutes=source_cfg.timeout_minutes,
        max_tool_rounds=source_cfg.max_tool_rounds,
        max_reflections=source_cfg.max_reflections,
        min_tool_calls=source_cfg.min_tool_calls,
        quality_criteria=list(source_cfg.quality_criteria) if source_cfg.quality_criteria else [],
        prompt=source_cfg.prompt,
        is_custom=True,
    )
    result = await bot_manager.create_custom_bot(new_cfg)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "duplicated", "new_name": new_name, **result}


@router.post("/{name}/test-notification")
async def test_bot_notification(name: str, user_id: str = Depends(get_user_id)):
    """Send a test notification through the bot's configured channels."""
    _validate_bot_name(name)
    state = bot_manager.get_bot_state(name)
    if not state:
        raise HTTPException(status_code=404, detail="Bot not found")

    integrations = state.get("integrations", {})
    if not integrations:
        return {"ok": False, "error": "No notification channels configured"}

    from app.tools import send_notification
    results = {}
    for channel, config in integrations.items():
        if not isinstance(config, dict) or not config.get("enabled", True):
            continue
        try:
            result = await send_notification.ainvoke({
                "channel": channel,
                "message": f"🔔 Test notification from bot '{state.get('display_name', name)}'. If you see this, notifications are working!",
            })
            results[channel] = {"ok": True, "result": str(result)[:200]}
        except Exception as e:
            results[channel] = {"ok": False, "error": str(e)[:200]}

    return {"ok": True, "results": results}


@router.put("/{name}/integrations")
async def update_bot_integrations(name: str, request: fastapi.Request, user_id: str = Depends(get_user_id)):
    """Update notification/integration settings for a bot."""
    _validate_bot_name(name)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    integrations = body.get("integrations", {})
    result = await bot_manager.update_config(name, {"integrations": integrations})
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ok": True, "integrations": integrations}
