"""Prompt proposals endpoints for agent self-improvement."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_prompt_proposals, get_prompt_proposal, update_prompt_proposal_status
from app.user_context import get_user_id, current_user_id

router = APIRouter(prefix="/prompt-proposals", tags=["prompt-proposals"])


@router.get("")
async def list_prompt_proposals(
    agent: str | None = None,
    status: str | None = None,
    limit: int = 50,
    user_id: str = Depends(get_user_id),
):
    """List prompt change proposals."""
    proposals = await get_prompt_proposals(agent=agent, status=status, limit=limit, user_id=user_id)
    return {"proposals": proposals, "total": len(proposals)}


@router.get("/{proposal_id}")
async def get_prompt_proposal_endpoint(proposal_id: int, user_id: str = Depends(get_user_id)):
    """Get a single prompt proposal."""
    proposal = await get_prompt_proposal(proposal_id, user_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return {"proposal": proposal}


@router.post("/{proposal_id}/approve")
async def approve_prompt_proposal(proposal_id: int, user_id: str = Depends(get_user_id)):
    """Approve and apply a prompt proposal."""
    from app.group_chat.prompt_evolution import write_yaml_changes

    current_user_id.set(user_id)

    proposal = await get_prompt_proposal(proposal_id, user_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if proposal.get("status") not in ("pending", "approved"):
        raise HTTPException(status_code=400, detail="Proposal already processed")

    # Apply changes
    try:
        await write_yaml_changes(proposal["agent"], proposal["proposed_changes"])
        await update_prompt_proposal_status(proposal_id, "applied", user_id)
        return {"ok": True, "status": "applied"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply: {str(e)}")


@router.post("/{proposal_id}/reject")
async def reject_prompt_proposal(proposal_id: int, user_id: str = Depends(get_user_id)):
    """Reject a prompt proposal."""
    proposal = await get_prompt_proposal(proposal_id, user_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if proposal.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Proposal already processed")

    await update_prompt_proposal_status(proposal_id, "rejected", user_id)
    return {"ok": True, "status": "rejected"}
