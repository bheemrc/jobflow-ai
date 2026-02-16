"""Job Intake agent node — analyzes job postings and matches against resume."""

from __future__ import annotations

import re
from functools import lru_cache

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.config import settings
from app.prompts import JOB_INTAKE_PROMPT
from app.state import AgentState
from app.tools import JOB_INTAKE_TOOLS
from app.nodes.tool_executor import run_agent_with_tools


@lru_cache
def _get_model():
    model = ChatOpenAI(model=settings.openai_model, temperature=0.2, max_tokens=4096)
    return model.bind_tools(JOB_INTAKE_TOOLS)


async def job_intake_node(state: AgentState, config: RunnableConfig) -> dict:
    """Analyze job postings and match against the user's resume."""
    context_parts = []
    if state.target_company:
        context_parts.append(f"Target Company: {state.target_company}")
    if state.target_role:
        context_parts.append(f"Target Role: {state.target_role}")
    if state.job_description:
        context_parts.append(f"Job Description:\n{state.job_description}")
    if state.resume_id:
        context_parts.append(f"Resume ID: {state.resume_id}")

    if not state.resume_text and state.resume_id:
        context_parts.append("Use review_resume tool to read the resume text.")
    elif state.resume_text:
        context_parts.append(f"Resume:\n{state.resume_text[:3000]}")

    # Encourage web search for company research
    if state.target_company:
        context_parts.append(
            f"Use web_search to research {state.target_company}: recent news, "
            "engineering culture, salary data, and tech stack."
        )

    if context_parts:
        context = "\n\n".join(context_parts)
    elif state.resume_id or state.resume_text:
        context = "The user has a resume uploaded. Review it and provide a comprehensive summary of their profile, skills, experience, and recommendations."
    else:
        context = "Analyze the user's job search pipeline."

    messages = [
        SystemMessage(content=JOB_INTAKE_PROMPT),
        HumanMessage(content=context),
    ]

    response, _ = await run_agent_with_tools(
        _get_model(), messages, JOB_INTAKE_TOOLS, config=config
    )

    # Build section cards
    cards = []

    # Try to extract match score from the response
    score_match = re.search(r"(?:match\s*score|score)[:\s]*(\d{1,3})", response.content, re.IGNORECASE)
    if score_match:
        cards.append({
            "type": "match_score",
            "title": f"Match Score: {state.target_company or 'Job'}",
            "agent": "job_intake",
            "data": {"score": int(score_match.group(1))},
            "content": response.content,
        })

    cards.append({
        "type": "skill_gap",
        "title": f"Analysis: {state.target_company or 'Job'} {state.target_role or ''}".strip(),
        "agent": "job_intake",
        "content": response.content,
    })

    return {
        "agent_outputs": {"job_intake": response.content},
        "messages": [response],
        "sections_generated": ["job_analysis"],
        "section_cards": cards,
        "active_agents": {"job_intake": "idle"},
    }
