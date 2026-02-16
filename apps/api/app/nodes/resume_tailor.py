"""Resume Tailor agent node — generates targeted resume diffs."""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.config import settings
from app.prompts import RESUME_TAILOR_PROMPT
from app.state import AgentState
from app.tools import RESUME_TAILOR_TOOLS
from app.nodes.tool_executor import run_agent_with_tools


@lru_cache
def _get_model():
    model = ChatOpenAI(model=settings.strong_model, temperature=0.4, max_tokens=4096)
    return model.bind_tools(RESUME_TAILOR_TOOLS)


def _validate_resume_output(content: str) -> str | None:
    """Validate that resume tailor output is specific enough."""
    if len(content) < 200:
        return "Response is too short. Provide at least 5 specific bullet-point changes with before/after text."
    change_indicators = ["bullet", "change", "add", "remove", "replace", "rewrite", "modify"]
    if not any(indicator in content.lower() for indicator in change_indicators):
        return (
            "Response doesn't contain specific change instructions. "
            "Use words like 'change', 'add', 'remove', 'replace' with exact bullet rewrites."
        )
    return None


async def resume_tailor_node(state: AgentState, config: RunnableConfig) -> dict:
    """Generate resume diff for a specific job application."""
    context_parts = []
    if state.target_role:
        context_parts.append(f"Target Role: {state.target_role}")
    if state.target_company:
        context_parts.append(f"Target Company: {state.target_company}")
    if state.job_description:
        context_parts.append(f"Job Description:\n{state.job_description}")

    if state.resume_text:
        context_parts.append(f"Resume:\n{state.resume_text}")
    elif state.resume_id:
        context_parts.append(
            f"Resume ID: {state.resume_id}\n"
            "Use the review_resume tool to read the resume text."
        )
    else:
        context_parts.append(
            "Use the review_resume tool to read the user's latest resume."
        )

    if state.resume_profile:
        context_parts.append(f"Profile:\n{state.resume_profile}")
    else:
        context_parts.append(
            "Use extract_resume_profile to get a structured profile of the resume."
        )

    context = "\n\n".join(context_parts)

    messages = [
        SystemMessage(content=RESUME_TAILOR_PROMPT),
        HumanMessage(content=(
            f"{context}\n\n"
            "Generate a specific resume diff. What to change, what to emphasize, "
            "specific bullet point rewrites. Be concrete."
        )),
    ]

    response, _ = await run_agent_with_tools(
        _get_model(), messages, RESUME_TAILOR_TOOLS, config=config,
        validate_fn=_validate_resume_output,
    )

    # Build section card for structured frontend rendering
    section_card = {
        "type": "resume_diff",
        "title": f"Resume Tailored for {state.target_company} {state.target_role}".strip(),
        "agent": "resume_tailor",
        "content": response.content,
    }

    return {
        "agent_outputs": {"resume_tailor": response.content},
        "messages": [response],
        "pending_approvals": {"resume_tailor": {
            "type": "resume_diff",
            "title": f"Resume diff for {state.target_company} {state.target_role}".strip(),
            "agent": "Resume Tailor",
            "content": response.content,
            "priority": "high",
        }},
        "sections_generated": ["resume_diff"],
        "section_cards": [section_card],
        "active_agents": {"resume_tailor": "waiting"},
    }
