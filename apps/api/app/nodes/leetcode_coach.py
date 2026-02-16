"""LeetCode Coach agent node — selects problems, provides hints, tracks progress."""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.config import settings
from app.prompts import LEETCODE_COACH_PROMPT
from app.state import AgentState
from app.tools import LEETCODE_COACH_TOOLS
from app.nodes.tool_executor import run_agent_with_tools


@lru_cache
def _get_model():
    model = ChatOpenAI(model=settings.openai_model, temperature=0.3, max_tokens=4096)
    return model.bind_tools(LEETCODE_COACH_TOOLS)


async def leetcode_coach_node(state: AgentState, config: RunnableConfig) -> dict:
    """Select daily problems, provide hints, track progress."""
    last_user_msg = ""
    for msg in reversed(state.messages):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_msg = msg.content
            break

    context_parts = [f"User request: {last_user_msg}"]
    if state.target_role:
        context_parts.append(f"Target role: {state.target_role}")
    if state.resume_profile:
        context_parts.append(f"Profile:\n{state.resume_profile}")

    context_parts.append(
        "Use the get_leetcode_progress tool to check current progress, "
        "then select_leetcode_problems to pick appropriate problems. "
        "Use web_search to find tutorials for the patterns you recommend."
    )

    messages = [
        SystemMessage(content=LEETCODE_COACH_PROMPT),
        HumanMessage(content="\n\n".join(context_parts)),
    ]

    response, _ = await run_agent_with_tools(
        _get_model(), messages, LEETCODE_COACH_TOOLS, config=config
    )

    needs_approval = "solution" in last_user_msg.lower() or "explain" in last_user_msg.lower()

    # Build section cards
    cards = [
        {
            "type": "daily_problems",
            "title": "Practice Session",
            "agent": "leetcode_coach",
            "content": response.content,
        },
    ]

    result: dict = {
        "agent_outputs": {"leetcode_coach": response.content},
        "messages": [response],
        "sections_generated": ["leetcode"],
        "section_cards": cards,
        "active_agents": {"leetcode_coach": "idle"},
    }

    if needs_approval:
        result["pending_approvals"] = {"leetcode_coach": {
            "type": "solution_review",
            "title": "LeetCode solution explanation",
            "agent": "LeetCode Coach",
            "content": response.content,
            "priority": "medium",
        }}
        result["active_agents"] = {"leetcode_coach": "waiting"}

    return result
