"""Interview Prep agent node — builds interview prep packages."""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.config import settings
from app.prompts import INTERVIEW_PREP_PROMPT
from app.state import AgentState
from app.tools import INTERVIEW_PREP_TOOLS
from app.nodes.tool_executor import run_agent_with_tools


@lru_cache
def _get_model():
    model = ChatOpenAI(model=settings.strong_model, temperature=0.5, max_tokens=4096)
    return model.bind_tools(INTERVIEW_PREP_TOOLS)


def _validate_interview_output(content: str) -> str | None:
    """Validate that interview prep output has required sections."""
    content_lower = content.lower()
    has_star = "star" in content_lower or "situation" in content_lower
    has_questions = "question" in content_lower
    if not has_star and not has_questions:
        return (
            "Response must include STAR-format answers (Situation, Task, Action, Result) "
            "and interview questions. Include both behavioral and technical prep."
        )
    return None


async def interview_prep_node(state: AgentState, config: RunnableConfig) -> dict:
    """Build interview prep package with STAR answers, technical review, company research."""
    context_parts = []
    if state.target_company:
        context_parts.append(f"Company: {state.target_company}")
    if state.target_role:
        context_parts.append(f"Role: {state.target_role}")
    if state.job_description:
        context_parts.append(f"Job Description:\n{state.job_description}")

    if state.resume_text:
        context_parts.append(f"Resume:\n{state.resume_text}")
    elif state.resume_id:
        context_parts.append(
            f"Resume ID: {state.resume_id}\n"
            "Use the review_resume tool to read the user's resume."
        )

    if state.resume_profile:
        context_parts.append(f"Profile:\n{state.resume_profile}")
    else:
        context_parts.append(
            "Use extract_resume_profile to get a structured profile."
        )

    messages = [
        SystemMessage(content=INTERVIEW_PREP_PROMPT),
        HumanMessage(content=(
            "\n\n".join(context_parts) + "\n\n"
            "Build a complete interview prep package. Use real resume details for every STAR answer. "
            "Use web_search to research recent interview experiences at the company."
        )),
    ]

    response, _ = await run_agent_with_tools(
        _get_model(), messages, INTERVIEW_PREP_TOOLS, config=config,
        validate_fn=_validate_interview_output,
    )

    # Build section card
    section_card = {
        "type": "prep_plan",
        "title": f"Interview Prep for {state.target_company or 'Target Company'}",
        "agent": "interview_prep",
        "content": response.content,
    }

    return {
        "agent_outputs": {"interview_prep": response.content},
        "messages": [response],
        "sections_generated": ["interview_prep"],
        "section_cards": [section_card],
        "active_agents": {"interview_prep": "idle"},
    }
