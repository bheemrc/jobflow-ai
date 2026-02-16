"""Group chat API router.

Handles all multi-agent group discussion endpoints with proper SSE streaming.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

import fastapi
from fastapi import APIRouter, Depends, HTTPException

from app.db import (
    create_group_chat,
    get_group_chat,
    get_group_chats,
    get_group_chat_messages,
    get_full_workspace,
    add_group_chat_participant,
    conclude_group_chat,
)
from app.event_bus import event_bus
from app.models import GroupChatCreate
from app.sse_stream import sse_response, format_sse
from app.thought_engine import get_all_personalities
from app.user_context import get_user_id, current_user_id
from app.group_chat.controls import GroupChatConfig, get_filtered_tools
from app.group_chat.orchestrator import (
    start_orchestrator,
    stop_orchestrator,
    get_orchestrator,
)
from app.group_chat.dynamic_agents import (
    suggest_agents_for_topic,
    get_default_participants,
    analyze_expertise_gap,
    get_agent_display_info,
    AGENT_ARCHETYPES,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/group-chats", tags=["group-chats"])


@router.get("/agents")
async def list_available_agents(user_id: str = Depends(get_user_id)):
    """List all available agents for group chats.

    These are the base archetype agents. Dynamic agents (like NASAEngineer,
    RadiationSpecialist, QuantumPhysicist) can be spawned on-demand during
    conversations based on the topic being discussed.
    """
    agents = []
    for agent_id, config in AGENT_ARCHETYPES.items():
        agents.append({
            "id": agent_id,
            "display_name": config.get("display_name", agent_id.title()),
            "description": config.get("description", ""),
            "expertise": config.get("expertise", []),
            "style": config.get("style", "neutral"),
        })
    return {
        "agents": agents,
        "info": {
            "dynamic_agents": "Agents can spawn domain-specific experts during discussion",
            "examples": [
                "NASAEngineer - Space systems expert",
                "RadiationSpecialist - Radiation hardening expert",
                "QuantumPhysicist - Quantum mechanics expert",
                "Any {Org}{Role} combination works dynamically",
            ],
        },
    }


@router.post("/suggest-agents")
async def suggest_agents(
    body: dict,
    user_id: str = Depends(get_user_id),
):
    """Suggest relevant agents for a topic."""
    topic = body.get("topic", "")
    exclude = body.get("exclude", [])
    max_suggestions = body.get("max", 4)

    if not topic:
        raise HTTPException(status_code=400, detail="topic is required")

    suggestions = suggest_agents_for_topic(
        topic=topic,
        exclude=exclude,
        max_suggestions=max_suggestions,
    )

    return {
        "suggestions": [
            {
                "agent": s.agent,
                "relevance_score": s.relevance_score,
                "reason": s.reason,
                "expertise_match": s.expertise_match,
            }
            for s in suggestions
        ],
        "default_participants": get_default_participants(topic),
    }


@router.post("/start")
async def start_group_chat_endpoint(
    body: GroupChatCreate,
    user_id: str = Depends(get_user_id),
):
    """Start a new multi-agent group chat."""
    current_user_id.set(user_id)

    # Validate participants
    try:
        personalities = get_all_personalities()
        validated = [p for p in body.participants if p in personalities]
        if len(validated) < 2:
            raise HTTPException(
                status_code=400, detail="At least 2 valid participants required"
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Build config from request
    config = GroupChatConfig()
    if body.config:
        if "max_turns" in body.config:
            config.max_turns = int(body.config["max_turns"])
        if "max_tokens" in body.config:
            config.max_tokens = int(body.config["max_tokens"])
        if "turn_mode" in body.config:
            config.turn_mode = body.config["turn_mode"]
        if "allowed_tools" in body.config:
            config.allowed_tools = list(body.config["allowed_tools"])

    # Create the group chat in database
    chat_id = await create_group_chat(
        topic=body.topic,
        participants=validated,
        initiator="user",
        config={
            "max_turns": config.max_turns,
            "max_tokens": config.max_tokens,
            "turn_mode": config.turn_mode,
            "allowed_tools": config.allowed_tools,
        },
        user_id=user_id,
    )

    # Start orchestrator in background
    await start_orchestrator(chat_id, config)

    return {
        "ok": True,
        "group_chat_id": chat_id,
        "topic": body.topic,
        "participants": validated,
    }


@router.get("")
async def list_group_chats_endpoint(
    status: str | None = None,
    limit: int = 50,
    user_id: str = Depends(get_user_id),
):
    """List all group chats for the user."""
    current_user_id.set(user_id)
    chats = await get_group_chats(status=status, limit=limit, user_id=user_id)
    return {"group_chats": chats, "total": len(chats)}


@router.get("/{chat_id}")
async def get_group_chat_endpoint(
    chat_id: int,
    user_id: str = Depends(get_user_id),
):
    """Get a single group chat with its messages."""
    current_user_id.set(user_id)
    chat = await get_group_chat(chat_id, user_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Group chat not found")

    messages = await get_group_chat_messages(chat_id, user_id=user_id)
    return {"group_chat": chat, "messages": messages}


@router.get("/{chat_id}/messages")
async def get_messages_endpoint(
    chat_id: int,
    limit: int = 100,
    user_id: str = Depends(get_user_id),
):
    """Get messages from a group chat."""
    current_user_id.set(user_id)
    messages = await get_group_chat_messages(chat_id, user_id, limit=limit)
    return {"messages": messages, "total": len(messages)}


@router.post("/{chat_id}/add-participant")
async def add_participant_endpoint(
    chat_id: int,
    body: dict,
    user_id: str = Depends(get_user_id),
):
    """Add a participant to an active group chat."""
    current_user_id.set(user_id)
    agent = body.get("agent")
    if not agent:
        raise HTTPException(status_code=400, detail="agent is required")

    orchestrator = get_orchestrator(chat_id)
    if orchestrator:
        success = await orchestrator.add_participant(agent)
        if not success:
            raise HTTPException(status_code=400, detail="Could not add participant")
    else:
        await add_group_chat_participant(chat_id, agent, user_id)

    return {"ok": True, "agent": agent}


@router.post("/{chat_id}/pause")
async def pause_endpoint(
    chat_id: int,
    user_id: str = Depends(get_user_id),
):
    """Pause an active group chat."""
    current_user_id.set(user_id)
    orchestrator = get_orchestrator(chat_id)
    if orchestrator:
        await orchestrator.pause()
    return {"ok": True, "status": "paused"}


@router.post("/{chat_id}/resume")
async def resume_endpoint(
    chat_id: int,
    user_id: str = Depends(get_user_id),
):
    """Resume a paused group chat."""
    current_user_id.set(user_id)
    orchestrator = get_orchestrator(chat_id)
    if orchestrator:
        await orchestrator.resume()
    else:
        # Restart orchestrator if not running
        chat = await get_group_chat(chat_id, user_id)
        if chat and chat.get("status") == "paused":
            config = GroupChatConfig()
            stored = chat.get("config", {})
            if stored.get("max_turns"):
                config.max_turns = stored["max_turns"]
            if stored.get("allowed_tools"):
                config.allowed_tools = stored["allowed_tools"]
            await start_orchestrator(chat_id, config)

    return {"ok": True, "status": "active"}


@router.post("/{chat_id}/conclude")
async def conclude_endpoint(
    chat_id: int,
    user_id: str = Depends(get_user_id),
):
    """Conclude a group chat and generate summary."""
    current_user_id.set(user_id)
    orchestrator = get_orchestrator(chat_id)

    if orchestrator:
        await orchestrator.conclude()
        await stop_orchestrator(chat_id)
    else:
        await conclude_group_chat(chat_id, "Chat concluded by user.", user_id)

    return {"ok": True, "status": "concluded"}


@router.get("/{chat_id}/stream")
async def stream_endpoint(
    request: fastapi.Request,
    chat_id: int,
    user_id: str = Depends(get_user_id),
):
    """SSE stream for real-time group chat updates."""
    current_user_id.set(user_id)

    async def generator() -> AsyncGenerator[dict, None]:
        # Send initial connected event
        yield {"type": "connected", "group_chat_id": chat_id}
        logger.info("SSE stream started for chat %d (type=%s)", chat_id, type(chat_id).__name__)

        # Stream events filtered to this chat
        # Note: Let the event_bus handle cleanup via its finally block
        async for event in event_bus.subscribe(include_heartbeats=True):
            event_type = event.get("type", "")
            event_chat_id = event.get("group_chat_id")

            # Debug all non-heartbeat events
            if event_type != "heartbeat":
                logger.info(
                    "SSE received event: type=%s, event_chat_id=%s (type=%s), filter_chat_id=%d, match=%s",
                    event_type,
                    event_chat_id,
                    type(event_chat_id).__name__ if event_chat_id else "None",
                    chat_id,
                    event_chat_id == chat_id,
                )

            # Filter and yield events
            if event_type == "heartbeat":
                yield event
            elif event_chat_id == chat_id:
                logger.info("SSE yielding event: type=%s for chat %d", event_type, chat_id)
                yield event

        logger.info("SSE stream ended for chat %d", chat_id)

    return await sse_response(request, generator())


@router.get("/{chat_id}/workspace")
async def get_workspace_endpoint(
    chat_id: int,
    user_id: str = Depends(get_user_id),
):
    """Get the shared workspace for a group chat.

    Returns tasks, findings, decisions, and tool calls.
    """
    current_user_id.set(user_id)

    # Verify chat exists and user has access
    chat = await get_group_chat(chat_id, user_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    workspace = await get_full_workspace(chat_id)
    return workspace
