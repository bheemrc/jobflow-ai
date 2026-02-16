"""Prompt evolution tool: propose changes to agent prompts."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from .shared import _uid, get_current_group_chat

logger = logging.getLogger(__name__)


@tool
async def propose_prompt_change(
    field: str,
    new_value: str,
    rationale: str,
) -> str:
    """Propose a change to your own system prompt based on learnings.

    Use this when you've discovered something that should permanently
    change how you operate. Changes are applied immediately (autonomous mode).

    Args:
        field: What to change — "prompt", "tools", "temperature", "quality_criteria", "description"
        new_value: The proposed new value (for prompt, this will be appended; for lists, provide JSON)
        rationale: Why this change will improve your performance (be specific)

    Returns:
        Proposal ID, status, and whether it was auto-applied.
    """
    valid_fields = ("prompt", "tools", "temperature", "quality_criteria", "description", "max_tokens")
    if field not in valid_fields:
        return json.dumps({
            "success": False,
            "error": f"Invalid field. Must be one of: {', '.join(valid_fields)}",
        })

    # Get the calling agent's name from context
    agent_name = "unknown"
    try:
        import inspect
        frame = inspect.currentframe()
        # Try to get agent name from call context
        if frame and frame.f_back and frame.f_back.f_locals:
            agent_name = frame.f_back.f_locals.get("agent", "unknown")
    except Exception:
        pass

    group_chat_id = get_current_group_chat()

    try:
        from app.group_chat.prompt_evolution import create_and_apply_proposal
        result = await create_and_apply_proposal(
            agent=agent_name,
            field=field,
            new_value=new_value,
            rationale=rationale,
            group_chat_id=group_chat_id,
            user_id=_uid(),
        )

        return json.dumps({
            "success": True,
            **result,
            "message": f"Prompt change proposal created and auto-applied for field '{field}'.",
        })

    except Exception as e:
        logger.error("propose_prompt_change error: %s", e)
        return json.dumps({
            "success": False,
            "error": str(e),
        })
