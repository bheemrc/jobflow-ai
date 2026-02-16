"""Recruiter Chat agent node — drafts responses to recruiter messages."""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.config import settings
from app.prompts import RECRUITER_CHAT_PROMPT
from app.state import AgentState
from app.tools import RECRUITER_CHAT_TOOLS
from app.nodes.tool_executor import run_agent_with_tools


@lru_cache
def _get_model():
    model = ChatOpenAI(model=settings.strong_model, temperature=0.6, max_tokens=4096)
    return model.bind_tools(RECRUITER_CHAT_TOOLS)


async def recruiter_chat_node(state: AgentState, config: RunnableConfig) -> dict:
    """Draft responses to recruiter messages."""
    last_user_msg = ""
    for msg in reversed(state.messages):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_msg = msg.content
            break

    context_parts = [f"Recruiter message or context:\n{last_user_msg}"]

    if state.resume_text:
        context_parts.append(f"Resume:\n{state.resume_text[:2000]}")
    elif state.resume_id:
        context_parts.append(
            f"Resume ID: {state.resume_id}\n"
            "Use the review_resume tool to read the user's resume."
        )

    messages = [
        SystemMessage(content=RECRUITER_CHAT_PROMPT),
        HumanMessage(content=(
            "\n\n".join(context_parts) + "\n\n"
            "Draft a reply that sounds human, includes talking points, "
            "and asks smart questions about the role."
        )),
    ]

    response, _ = await run_agent_with_tools(
        _get_model(), messages, RECRUITER_CHAT_TOOLS, config=config
    )

    return {
        "agent_outputs": {"recruiter_chat": response.content},
        "messages": [response],
        "pending_approvals": {"recruiter_chat": {
            "type": "recruiter_reply",
            "title": "Draft recruiter response",
            "agent": "Recruiter Chat",
            "content": response.content,
            "priority": "high",
        }},
        "sections_generated": ["recruiter_draft"],
        "section_cards": [{
            "type": "recruiter_draft",
            "title": "Recruiter Response Draft",
            "agent": "recruiter_chat",
            "content": response.content,
        }],
        "active_agents": {"recruiter_chat": "waiting"},
    }
