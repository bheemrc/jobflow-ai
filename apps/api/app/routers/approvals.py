"""Approval endpoints for HITL (Human-in-the-loop) gates."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from langgraph.types import Command

from app.db import (
    get_pending_approvals,
    get_approval_by_id,
    resolve_approval,
    get_resolved_approvals_for_thread,
    log_activity,
)
from app.models import ApprovalDecision, BatchApprovalDecisions
from app.user_context import get_user_id
from .shared import get_graph

logger = logging.getLogger(__name__)

router = APIRouter(tags=["approvals"])


@router.get("/approvals")
async def list_approvals(user_id: str = Depends(get_user_id)):
    """List pending approval items."""
    items = await get_pending_approvals(user_id=user_id)
    # Serialize datetime objects
    for item in items:
        if "created_at" in item and hasattr(item["created_at"], "isoformat"):
            item["created_at"] = item["created_at"].isoformat()
    return {"approvals": items}


@router.post("/approvals/{approval_id}")
async def resolve_approval_endpoint(approval_id: int, body: ApprovalDecision, user_id: str = Depends(get_user_id)):
    """Process a single approval decision.

    If this is the last pending approval for the thread, resumes the graph
    with a decisions dict covering all approvals for that thread.
    """
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Decision must be 'approved' or 'rejected'")

    approval = await get_approval_by_id(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if approval.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Approval already resolved")

    thread_id = approval.get("thread_id", "")
    if not thread_id:
        raise HTTPException(status_code=400, detail="Approval has no associated session for graph resumption")

    # Mark the approval as resolved in the database
    await resolve_approval(approval_id, body.decision)

    await log_activity(
        agent="user",
        action=f"{'Approved' if body.decision == 'approved' else 'Rejected'}: {approval.get('title', '')}",
        detail=f"approval_id={approval_id}",
    )

    # Check if there are still pending approvals for this thread
    all_approvals = await get_pending_approvals()
    remaining = [a for a in all_approvals if a.get("thread_id") == thread_id and a.get("status") == "pending"]

    if remaining:
        # Other approvals still pending — don't resume graph yet
        return {
            "ok": True,
            "approval_id": approval_id,
            "decision": body.decision,
            "remaining_approvals": len(remaining),
            "response": "",
        }

    # All approvals for this thread resolved — resume the graph
    return await _resume_graph_for_thread(thread_id, user_id)


@router.post("/approvals/batch")
async def batch_resolve_approvals(body: BatchApprovalDecisions, user_id: str = Depends(get_user_id)):
    """Resolve multiple approvals at once and resume the graph."""
    if not body.decisions:
        raise HTTPException(status_code=400, detail="No decisions provided")

    thread_id = None
    for aid, decision in body.decisions.items():
        if decision not in ("approved", "rejected"):
            raise HTTPException(status_code=400, detail=f"Invalid decision for approval {aid}")

        approval = await get_approval_by_id(aid)
        if not approval:
            raise HTTPException(status_code=404, detail=f"Approval {aid} not found")
        if approval.get("status") != "pending":
            raise HTTPException(status_code=409, detail=f"Approval {aid} already resolved")

        # All approvals in a batch must belong to the same thread
        if thread_id is None:
            thread_id = approval.get("thread_id", "")
        elif approval.get("thread_id") != thread_id:
            raise HTTPException(status_code=400, detail="All approvals in a batch must belong to the same session")

        await resolve_approval(aid, decision)
        await log_activity(
            agent="user",
            action=f"{'Approved' if decision == 'approved' else 'Rejected'}: {approval.get('title', '')}",
            detail=f"approval_id={aid}",
        )

    if not thread_id:
        raise HTTPException(status_code=400, detail="No thread_id found for approvals")

    return await _resume_graph_for_thread(thread_id, user_id)


async def _resume_graph_for_thread(thread_id: str, user_id: str) -> dict:
    """Build a decisions dict from all resolved approvals for the thread and resume the graph."""
    graph = get_graph()
    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    config = {"configurable": {"thread_id": f"{user_id}:{thread_id}"}}
    try:
        state_snapshot = await graph.aget_state(config)
        if not state_snapshot or not state_snapshot.next:
            raise HTTPException(status_code=409, detail="Graph is not in an interrupted state")

        # Build decisions dict keyed by agent name from the interrupt's pending_approvals
        current_values = state_snapshot.values if state_snapshot else {}
        pending = current_values.get("pending_approvals", {})

        # Look up resolved approvals from DB to get their decisions
        resolved = await get_resolved_approvals_for_thread(thread_id)

        # Map agent_name → decision
        decisions = {}
        for agent_name in pending:
            # Find the matching resolved approval
            for r in resolved:
                if r.get("agent") == agent_name:
                    decisions[agent_name] = r.get("status", "approved")
                    break
            else:
                # Default to approved if we can't find the record
                decisions[agent_name] = "approved"

        result = await graph.ainvoke(Command(resume=decisions), config=config)

        response_text = ""
        for msg in reversed(result.get("messages", [])):
            if hasattr(msg, "type") and msg.type == "ai":
                response_text = msg.content
                break

        return {
            "ok": True,
            "decisions": decisions,
            "response": response_text,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to resume graph for thread %s: %s", thread_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Graph resumption failed: {str(e)}")
