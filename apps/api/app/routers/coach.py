"""Coach endpoints - main interaction with the LangGraph orchestrator."""

from __future__ import annotations

import re
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from app.db import log_activity, create_approval
from app.models import CoachRequest, CoachResponse
from app.resume_store import get_resume
from app.user_context import get_user_id, current_user_id
from app.sse import SSEConverter, format_sse
from app.triggers import check_triggers
from .shared import get_graph, generate_session_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["coach"])


@router.post("/coach/stream")
async def coach_stream(request: CoachRequest, user_id: str = Depends(get_user_id)):
    """Stream coach response as SSE events."""
    graph = get_graph()
    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    session_id = request.session_id or generate_session_id()
    # Prefix thread_id with user_id to prevent cross-user state collision
    config = {"configurable": {"thread_id": f"{user_id}:{session_id}"}}

    # Build input
    input_data: dict = {}

    if request.message:
        input_data["messages"] = [HumanMessage(content=request.message)]

    if request.context:
        ctx = request.context
        if ctx.resume_id:
            input_data["resume_id"] = ctx.resume_id
            # Load resume text
            resume_text = await get_resume(ctx.resume_id, user_id)
            if resume_text:
                input_data["resume_text"] = resume_text
        if ctx.company:
            input_data["target_company"] = ctx.company
        if ctx.role:
            input_data["target_role"] = ctx.role
        if ctx.job_status:
            input_data["job_status"] = ctx.job_status
        if ctx.job_description:
            input_data["job_description"] = ctx.job_description
        if ctx.focus_topic:
            input_data["focus_topic"] = ctx.focus_topic

    # If no message and no context, send a greeting prompt
    if not input_data.get("messages") and not request.message:
        input_data["messages"] = [HumanMessage(
            content="I just opened the dashboard. What should I focus on?"
        )]

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            current_user_id.set(user_id)
            response_text = ""
            sections = []
            section_cards = []
            converter = SSEConverter()

            # Check proactive triggers before graph invocation
            triggers = await check_triggers(user_id)
            for trigger in triggers:
                yield format_sse({
                    "type": "trigger",
                    "trigger_type": trigger["type"],
                    "title": trigger["title"],
                    "message": trigger["message"],
                    "priority": trigger["priority"],
                })

            async for event in graph.astream_events(input_data, config=config, version="v2"):
                sse_event = converter.convert(event)
                if sse_event:
                    if sse_event["type"] == "delta":
                        response_text += sse_event.get("text", "")
                    yield format_sse(sse_event)

            # Get final state for sections and section_cards
            state_snapshot = await graph.aget_state(config)
            current_values = state_snapshot.values if state_snapshot else {}
            sections = current_values.get("sections_generated", [])
            section_cards = current_values.get("section_cards", [])

            # Check if the graph is paused at an interrupt (HITL approval gate)
            if state_snapshot and state_snapshot.next:
                pending_approvals = current_values.get("pending_approvals", {})
                if pending_approvals:
                    for agent_name, pending in pending_approvals.items():
                        approval_id = await create_approval(
                            thread_id=session_id,
                            type=pending.get("type", "general"),
                            title=pending.get("title", "Agent output"),
                            agent=pending.get("agent", agent_name),
                            content=pending.get("content", ""),
                            priority=pending.get("priority", "medium"),
                        )
                        await log_activity(
                            agent=pending.get("agent", agent_name),
                            action=f"Awaiting approval: {pending.get('title', '')}",
                            detail=pending.get("type", ""),
                        )
                        yield format_sse({
                            "type": "approval_requested",
                            "approval_id": approval_id,
                            "agent": agent_name,
                            "approval": pending,
                            "session_id": session_id,
                        })

            # Emit section_card events for each card
            for card in section_cards:
                yield format_sse({
                    "type": "section_card",
                    "card_type": card.get("type", ""),
                    "title": card.get("title", ""),
                    "agent": card.get("agent", ""),
                    "content": card.get("content", ""),
                    "data": card.get("data"),
                })

            # Clean any leftover internal routing tags from streamed text
            clean_response = re.sub(r"\[(?:ROUTE|COMPANY|ROLE):\s*.+?\]", "", response_text).strip()

            # Final response event
            yield format_sse({
                "type": "response",
                "session_id": session_id,
                "response": clean_response,
                "sections_generated": sections,
                "section_cards": section_cards,
                "actions": [],
            })

        except Exception as e:
            logger.error("Stream error: %s", e, exc_info=True)
            yield format_sse({
                "type": "error",
                "message": str(e),
            })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/coach", response_model=CoachResponse)
async def coach(request: CoachRequest, user_id: str = Depends(get_user_id)):
    """Non-streaming coach endpoint."""
    graph = get_graph()
    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    session_id = request.session_id or generate_session_id()
    config = {"configurable": {"thread_id": f"{user_id}:{session_id}"}}

    input_data: dict = {}
    if request.message:
        input_data["messages"] = [HumanMessage(content=request.message)]

    if request.context:
        ctx = request.context
        if ctx.resume_id:
            input_data["resume_id"] = ctx.resume_id
            resume_text = await get_resume(ctx.resume_id, user_id)
            if resume_text:
                input_data["resume_text"] = resume_text
        if ctx.company:
            input_data["target_company"] = ctx.company
        if ctx.role:
            input_data["target_role"] = ctx.role
        if ctx.job_status:
            input_data["job_status"] = ctx.job_status
        if ctx.job_description:
            input_data["job_description"] = ctx.job_description
        if ctx.focus_topic:
            input_data["focus_topic"] = ctx.focus_topic

    if not input_data.get("messages"):
        input_data["messages"] = [HumanMessage(
            content="I just opened the dashboard. What should I focus on?"
        )]

    try:
        current_user_id.set(user_id)
        result = await graph.ainvoke(input_data, config=config)
        # Extract the last AI message
        response_text = ""
        for msg in reversed(result.get("messages", [])):
            if hasattr(msg, "content") and hasattr(msg, "type") and msg.type == "ai":
                response_text = msg.content
                break

        # Clean control tags
        response_text = re.sub(r"\[(?:ROUTE|COMPANY|ROLE):\s*.+?\]", "", response_text).strip()

        return CoachResponse(
            session_id=session_id,
            response=response_text,
            sections_generated=result.get("sections_generated", []),
            section_cards=result.get("section_cards", []),
        )
    except Exception as e:
        logger.error("Coach error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
