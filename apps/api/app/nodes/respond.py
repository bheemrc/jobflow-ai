"""Respond node — composes the final response from parallel agent outputs."""

from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.flow_config import get_flow_config
from app.memory import maybe_summarize
from app.state import AgentState

logger = logging.getLogger(__name__)

# Map agent names to prep material types for auto-save
_AGENT_TO_PREP_TYPE: dict[str, str] = {
    "interview_prep": "interview",
    "system_design": "system_design",
    "leetcode_coach": "leetcode",
    "job_intake": "company_research",
}


def _get_agent_display_names() -> dict[str, str]:
    """Derive display names from current flow config."""
    config = get_flow_config()
    return {name: cfg.display_name for name, cfg in config.agents.items()}


def _clean_response(text: str) -> str:
    """Strip any leftover control tags from the response."""
    cleaned = re.sub(r"\[ROUTE:\s*.+?\]", "", text)
    cleaned = re.sub(r"\[COMPANY:\s*.+?\]", "", cleaned)
    cleaned = re.sub(r"\[ROLE:\s*.+?\]", "", cleaned)
    return cleaned.strip()


# Fields to reset at end of turn
_RESET = {
    "pending_approvals": {},
    "approval_decisions": {},
    "agent_outputs": {},
}


async def _auto_save_outputs(state: AgentState, display_names: dict[str, str]) -> None:
    """Automatically persist agent outputs to prep_materials and journal_entries.

    This runs as a post-execution hook so we don't rely on the LLM
    remembering to call save tools — outputs are always captured.
    """
    from app.db import create_prep_material, create_journal_entry

    if not state.agent_outputs:
        return

    company = state.target_company or None
    role = state.target_role or None

    for agent_name, output_text in state.agent_outputs.items():
        if not output_text or len(output_text) < 100:
            continue  # Skip trivially short outputs

        agent_label = display_names.get(agent_name, agent_name)

        # Save as prep material if this agent type maps to a prep type
        prep_type = _AGENT_TO_PREP_TYPE.get(agent_name)
        if prep_type:
            title_prefix = {
                "interview": "Interview Prep",
                "system_design": "System Design",
                "leetcode": "LeetCode Plan",
                "company_research": "Job Analysis",
            }.get(prep_type, "Prep")
            title = f"{title_prefix}: {company or 'General'}"
            if role:
                title += f" — {role}"

            try:
                mid = await create_prep_material(
                    material_type=prep_type,
                    title=title,
                    content={"text": output_text},
                    company=company,
                    role=role,
                    agent_source=agent_name,
                )
                logger.info("Auto-saved prep material %d from agent %s", mid, agent_name)
            except Exception as e:
                logger.warning("Failed to auto-save prep material from %s: %s", agent_name, e)

        # Save a journal entry for every agent output
        try:
            tags = [agent_name]
            if company:
                tags.append(company.lower().replace(" ", "_"))

            jid = await create_journal_entry(
                title=f"{agent_label} session" + (f" — {company}" if company else ""),
                content=output_text[:5000],  # Truncate for journal
                entry_type="summary",
                agent=agent_name,
                priority="medium",
                tags=tags,
            )
            logger.info("Auto-saved journal entry %d from agent %s", jid, agent_name)
        except Exception as e:
            logger.warning("Failed to auto-save journal entry from %s: %s", agent_name, e)


async def respond_node(state: AgentState) -> dict:
    """Compose the final response incorporating outputs from parallel agents."""
    display_names = _get_agent_display_names()

    # Handle post-approval responses (graph resumed after interrupt)
    if state.approval_decisions:
        parts = []
        for agent_name, decision in state.approval_decisions.items():
            approval = state.pending_approvals.get(agent_name, {})
            title = approval.get("title", agent_name)
            display_name = approval.get("agent", display_names.get(agent_name, agent_name))

            if decision == "approved":
                parts.append(f"Approved: **{title}** — {display_name}'s output is ready to use.")
            else:
                parts.append(f"Rejected: **{title}** — let me know if you'd like a different approach.")

        content = "\n\n".join(parts)
        return {
            "messages": [AIMessage(content=content)],
            **_RESET,
        }

    if state.agent_outputs:
        # Auto-save outputs to prep_materials and journal_entries
        try:
            await _auto_save_outputs(state, display_names)
        except Exception as e:
            logger.warning("Auto-save outputs failed: %s", e)

        if len(state.agent_outputs) == 1:
            # Single agent — use its output directly (backward compatible)
            content = _clean_response(list(state.agent_outputs.values())[0])
        else:
            # Multiple parallel agents — compose with headers
            parts = []
            for agent_name, output in state.agent_outputs.items():
                label = display_names.get(agent_name, agent_name)
                parts.append(f"## {label}\n\n{_clean_response(output)}")
            content = "\n\n---\n\n".join(parts)

        return {
            "messages": [AIMessage(content=content)],
            **_RESET,
        }

    # No agent output — check if this is a conversational follow-up that needs
    # a generated response (coach routed here with [ROUTE: respond])
    has_conversation_history = sum(
        1 for m in state.messages
        if hasattr(m, "type") and m.type == "ai" and len(m.content) > 200
    ) > 0

    # Get the coach's last message and clean it
    coach_msg = ""
    for msg in reversed(state.messages):
        if hasattr(msg, "type") and msg.type == "ai":
            coach_msg = _clean_response(msg.content)
            break

    if has_conversation_history and len(coach_msg) < 100:
        # Coach gave a short routing ack — generate a real conversational response
        config = get_flow_config()
        model = ChatOpenAI(
            model=config.resolve_model("default"),
            temperature=0.5,
            max_tokens=2048,
        )
        conversation = await maybe_summarize(list(state.messages))

        focus_ctx = ""
        if state.focus_topic:
            focus_ctx = f"This is a focused study room for: {state.focus_topic}\n"

        system = SystemMessage(content=(
            f"{focus_ctx}"
            "You are an AI Career Coach. The conversation above contains previous specialist analysis. "
            "Answer the user's follow-up question directly using the context from the conversation. "
            "Be helpful, specific, and reference the previous analysis when relevant. "
            "Do NOT use [ROUTE:], [COMPANY:], or [ROLE:] tags."
        ))
        response = await model.ainvoke([system] + conversation)
        return {
            "messages": [AIMessage(content=response.content or "")],
            **_RESET,
        }

    # Coach's own message is adequate — just clean control tags
    if coach_msg:
        return {
            "messages": [AIMessage(content=coach_msg)],
            **_RESET,
        }

    return {**_RESET}
