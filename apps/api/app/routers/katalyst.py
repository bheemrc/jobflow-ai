"""Katalyst (goal-driven multi-agent orchestration) endpoints."""

from __future__ import annotations

import asyncio
import json
import logging

import fastapi
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.user_context import get_user_id, current_user_id
from app.event_bus import event_bus
from app.sse import format_bot_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/katalyst", tags=["katalyst"])


@router.post("/reactions")
async def spawn_katalyst_reaction(request: Request, user_id: str = Depends(get_user_id)):
    """Spawn a new Katalyst reaction from a user goal."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    goal = body.get("goal", "").strip()
    if not goal:
        raise HTTPException(status_code=400, detail="Goal is required")

    from app.katalyst.orchestrator import spawn_reaction
    reaction = await spawn_reaction(goal=goal, user_id=user_id)
    return reaction


@router.get("/reactions")
async def list_katalyst_reactions(
    status: str | None = Query(None),
    user_id: str = Depends(get_user_id),
):
    """List all Katalyst reactions for the current user."""
    from app.katalyst import db as kat_db
    reactions = await kat_db.list_reactions(user_id=user_id, status=status)
    return {"reactions": reactions}


@router.get("/reactions/{reaction_id}")
async def get_katalyst_reaction(reaction_id: int, user_id: str = Depends(get_user_id)):
    """Get a single Katalyst reaction with workstreams, artifacts, blockers."""
    from app.katalyst import db as kat_db
    reaction = await kat_db.get_reaction(reaction_id, user_id)
    if not reaction:
        raise HTTPException(status_code=404, detail="Reaction not found")

    workstreams, artifacts, blockers = await asyncio.gather(
        kat_db.get_workstreams(reaction_id, user_id),
        kat_db.get_artifacts(reaction_id, user_id),
        kat_db.get_blockers(reaction_id, user_id),
    )
    reaction["workstreams"] = workstreams
    reaction["artifacts"] = artifacts
    reaction["blockers"] = blockers
    return reaction


@router.put("/reactions/{reaction_id}/status")
async def update_katalyst_reaction_status(
    reaction_id: int,
    request: Request,
    user_id: str = Depends(get_user_id),
):
    """Pause, resume, or abandon a Katalyst reaction."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    new_status = body.get("status", "").strip()
    valid = {"active", "paused", "abandoned", "completed"}
    if new_status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")

    from app.katalyst import db as kat_db
    if new_status == "completed":
        from app.katalyst.orchestrator import complete_reaction
        reaction = await complete_reaction(reaction_id, user_id)
    else:
        reaction = await kat_db.update_reaction(reaction_id, user_id, status=new_status)

    if not reaction:
        raise HTTPException(status_code=404, detail="Reaction not found")
    return reaction


@router.get("/reactions/{reaction_id}/feed")
async def get_katalyst_feed(
    reaction_id: int,
    limit: int = 50,
    user_id: str = Depends(get_user_id),
):
    """Get the event feed for a Katalyst reaction."""
    from app.katalyst import db as kat_db
    reaction = await kat_db.get_reaction(reaction_id, user_id)
    if not reaction:
        raise HTTPException(status_code=404, detail="Reaction not found")
    events = await kat_db.get_events(reaction_id, user_id, limit)
    return {"reaction_id": reaction_id, "events": events}


@router.get("/reactions/{reaction_id}/workstreams")
async def get_katalyst_workstreams(reaction_id: int, user_id: str = Depends(get_user_id)):
    """Get workstreams for a Katalyst reaction."""
    from app.katalyst import db as kat_db
    workstreams = await kat_db.get_workstreams(reaction_id, user_id)
    return {"reaction_id": reaction_id, "workstreams": workstreams}


@router.get("/reactions/{reaction_id}/artifacts")
async def get_katalyst_artifacts(reaction_id: int, user_id: str = Depends(get_user_id)):
    """Get artifacts for a Katalyst reaction."""
    from app.katalyst import db as kat_db
    artifacts = await kat_db.get_artifacts(reaction_id, user_id)
    return {"reaction_id": reaction_id, "artifacts": artifacts}


@router.get("/artifacts/{artifact_id}")
async def get_katalyst_artifact(artifact_id: int, user_id: str = Depends(get_user_id)):
    """Get a single artifact with version history."""
    from app.katalyst import db as kat_db
    artifact = await kat_db.get_artifact(artifact_id, user_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    versions = await kat_db.get_artifact_versions(artifact_id, user_id)
    artifact["versions"] = versions
    return artifact


@router.get("/reactions/{reaction_id}/blockers")
async def get_katalyst_blockers(
    reaction_id: int,
    all: bool = False,
    user_id: str = Depends(get_user_id),
):
    """Get blockers for a Katalyst reaction."""
    from app.katalyst import db as kat_db
    blockers = await kat_db.get_blockers(reaction_id, user_id, unresolved_only=not all)
    return {"reaction_id": reaction_id, "blockers": blockers}


@router.post("/blockers/{blocker_id}/resolve")
async def resolve_katalyst_blocker(
    blocker_id: int,
    request: Request,
    user_id: str = Depends(get_user_id),
):
    """Resolve a Katalyst blocker with user decision."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    resolution = body.get("resolution", "").strip()
    if not resolution:
        raise HTTPException(status_code=400, detail="Resolution text is required")

    from app.katalyst import db as kat_db
    blocker = await kat_db.resolve_blocker(
        blocker_id=blocker_id,
        resolution=resolution,
        resolved_by="user",
        user_id=user_id,
    )
    if not blocker:
        raise HTTPException(status_code=404, detail="Blocker not found")

    # Log the resolution event
    await kat_db.create_event(
        reaction_id=blocker["reaction_id"],
        event_type="blocker_resolved",
        agent="user",
        message=f"Blocker resolved: {resolution[:100]}",
        data={"blocker_id": blocker_id, "resolution": resolution},
        user_id=user_id,
    )

    await event_bus.publish({
        "type": "katalyst_blocker_resolved",
        "reaction_id": blocker["reaction_id"],
        "blocker_id": blocker_id,
    })

    return blocker


@router.post("/reactions/{reaction_id}/execute")
async def execute_katalyst_reaction(reaction_id: int, user_id: str = Depends(get_user_id)):
    """Manually trigger full execution of all workstreams (background, returns immediately)."""
    from app.katalyst import db as kat_db

    reaction = await kat_db.get_reaction(reaction_id, user_id)
    if not reaction:
        raise HTTPException(status_code=404, detail="Reaction not found")
    if reaction["status"] != "active":
        raise HTTPException(status_code=400, detail="Reaction is not active")

    # Run in background so the request returns immediately
    asyncio.create_task(_run_full_execution(reaction_id, user_id))
    return {"ok": True, "reaction_id": reaction_id, "status": "execution_started"}


async def _run_full_execution(reaction_id: int, user_id: str) -> None:
    """Background task: run each workstream through all remaining stages."""
    from app.katalyst import db as kat_db
    from app.katalyst.work_executor import execute_workstream_step

    max_steps_per_ws = 5
    try:
        workstreams = await kat_db.get_workstreams(reaction_id, user_id)
        for ws in workstreams:
            if ws.get("status") == "completed":
                continue
            current_ws = ws
            for _ in range(max_steps_per_ws):
                if current_ws.get("status") == "completed":
                    break
                try:
                    result = await execute_workstream_step(
                        current_ws, current_ws.get("agent", ""), user_id
                    )
                    if not result:
                        break
                    current_ws = result
                except Exception as e:
                    logger.warning("Execution failed for workstream %d: %s", current_ws["id"], e)
                    break
        logger.info("Full execution complete for reaction %d", reaction_id)
    except Exception as e:
        logger.error("Full execution failed for reaction %d: %s", reaction_id, e)


@router.get("/reactions/{reaction_id}/stream")
async def katalyst_reaction_stream(
    reaction_id: int,
    request: Request,
    user_id: str = Depends(get_user_id),
):
    """SSE stream for real-time Katalyst reaction updates."""
    current_user_id.set(user_id)
    last_event_id_str = request.headers.get("Last-Event-ID")
    last_event_id = int(last_event_id_str) if last_event_id_str else None

    from app.katalyst import db as kat_db
    reaction = await kat_db.get_reaction(reaction_id, user_id)
    if not reaction:
        raise HTTPException(status_code=404, detail="Reaction not found")

    katalyst_event_types = {
        "katalyst_reaction_spawned",
        "katalyst_reaction_completed",
        "katalyst_artifact_created",
        "katalyst_artifact_updated",
        "katalyst_blocker_created",
        "katalyst_blocker_resolved",
        "katalyst_workstream_advanced",
    }

    async def event_generator():
        # Send current state as initial event
        workstreams, artifacts, blockers, events = await asyncio.gather(
            kat_db.get_workstreams(reaction_id, user_id),
            kat_db.get_artifacts(reaction_id, user_id),
            kat_db.get_blockers(reaction_id, user_id),
            kat_db.get_events(reaction_id, user_id, limit=20),
        )
        yield format_bot_event({
            "type": "katalyst_state",
            "reaction": reaction,
            "workstreams": workstreams,
            "artifacts": artifacts,
            "blockers": blockers,
            "events": events,
        })

        # Stream live updates filtered to this reaction
        async for ev in event_bus.subscribe(last_event_id=last_event_id):
            ev_type = ev.get("type", "")
            if ev_type in katalyst_event_types and ev.get("reaction_id") == reaction_id:
                eid = ev.get("event_id", "")
                yield f"id: {eid}\ndata: {json.dumps(ev)}\n\n"
            elif ev_type == "heartbeat":
                yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
