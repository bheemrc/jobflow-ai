"""Generic agent node factory — creates agent nodes from YAML config.

Replaces the need for separate node files per specialist. Each agent is
configured from flows.yaml: model, temperature, tools, prompt, approval settings.
"""

from __future__ import annotations

import re
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.flow_config import AgentConfig, FlowConfig
from app.state import AgentState
from app.nodes.tool_executor import run_agent_with_tools

logger = logging.getLogger(__name__)


def _build_context(state: AgentState, agent_name: str) -> str:
    """Build context string from state for a specialist agent."""
    parts = []

    # Last user message
    for msg in reversed(state.messages):
        if hasattr(msg, "type") and msg.type == "human":
            parts.append(f"User request: {msg.content}")
            break

    if state.target_company:
        parts.append(f"Target Company: {state.target_company}")
    if state.target_role:
        parts.append(f"Target Role: {state.target_role}")
    if state.job_description:
        parts.append(f"Job Description:\n{state.job_description}")

    if state.resume_text:
        parts.append(f"Resume:\n{state.resume_text[:3000]}")
    elif state.resume_id:
        parts.append(f"Resume ID: {state.resume_id}\nUse review_resume tool to read the resume text.")

    if state.resume_profile:
        parts.append(f"Profile:\n{state.resume_profile}")

    if state.target_company:
        parts.append(
            f"Use web_search to research {state.target_company}: recent news, "
            "engineering culture, salary data, and tech stack."
        )

    if not parts:
        if state.resume_id or state.resume_text:
            parts.append("The user has a resume uploaded. Review it and provide comprehensive analysis.")
        else:
            parts.append("Analyze the user's request and provide helpful guidance.")

    return "\n\n".join(parts)


def _build_section_cards(agent_name: str, response_content: str, state: AgentState) -> list[dict]:
    """Build section cards based on agent type and response content."""
    cards = []
    company = state.target_company or "Job"
    role = state.target_role or ""

    if agent_name == "job_intake":
        score_match = re.search(r"(?:match\s*score|score)[:\s]*(\d{1,3})", response_content, re.IGNORECASE)
        if score_match:
            cards.append({
                "type": "match_score",
                "title": f"Match Score: {company}",
                "agent": agent_name,
                "data": {"score": int(score_match.group(1))},
                "content": response_content,
            })
        cards.append({
            "type": "skill_gap",
            "title": f"Analysis: {company} {role}".strip(),
            "agent": agent_name,
            "content": response_content,
        })
    elif agent_name == "resume_tailor":
        cards.append({
            "type": "resume_diff",
            "title": f"Resume Tailored for {company} {role}".strip(),
            "agent": agent_name,
            "content": response_content,
        })
    elif agent_name == "recruiter_chat":
        cards.append({
            "type": "recruiter_draft",
            "title": "Recruiter Response Draft",
            "agent": agent_name,
            "content": response_content,
        })
    elif agent_name == "interview_prep":
        cards.append({
            "type": "prep_plan",
            "title": f"Interview Prep for {company or 'Target Company'}",
            "agent": agent_name,
            "content": response_content,
        })
    elif agent_name == "leetcode_coach":
        cards.append({
            "type": "daily_problems",
            "title": "Practice Session",
            "agent": agent_name,
            "content": response_content,
        })
    elif agent_name == "system_design":
        cards.append({
            "type": "system_design",
            "title": f"System Design Prep: {company or 'Target Company'}",
            "agent": agent_name,
            "content": response_content,
        })
    else:
        cards.append({
            "type": agent_name,
            "title": f"{agent_name} output",
            "agent": agent_name,
            "content": response_content,
        })

    return cards


def _get_section_name(agent_name: str) -> str:
    """Map agent name to section identifier."""
    mapping = {
        "job_intake": "job_analysis",
        "resume_tailor": "resume_diff",
        "recruiter_chat": "recruiter_draft",
        "interview_prep": "interview_prep",
        "leetcode_coach": "leetcode",
        "system_design": "system_design",
    }
    return mapping.get(agent_name, agent_name)


def _get_validate_fn(agent_name: str):
    """Return a validation function for agents that need output validation."""
    if agent_name == "resume_tailor":
        def validate(content: str) -> str | None:
            if len(content) < 200:
                return "Response is too short. Provide at least 5 specific bullet-point changes with before/after text."
            change_indicators = ["bullet", "change", "add", "remove", "replace", "rewrite", "modify"]
            if not any(indicator in content.lower() for indicator in change_indicators):
                return (
                    "Response doesn't contain specific change instructions. "
                    "Use words like 'change', 'add', 'remove', 'replace' with exact bullet rewrites."
                )
            return None
        return validate

    if agent_name == "interview_prep":
        def validate(content: str) -> str | None:
            content_lower = content.lower()
            has_star = "star" in content_lower or "situation" in content_lower
            has_questions = "question" in content_lower
            if not has_star and not has_questions:
                return (
                    "Response must include STAR-format answers (Situation, Task, Action, Result) "
                    "and interview questions. Include both behavioral and technical prep."
                )
            return None
        return validate

    return None


def create_agent_node(agent_config: AgentConfig, flow_config: FlowConfig):
    """Factory: returns an async node function configured from YAML.

    The returned function has the same signature as existing specialist nodes
    so it drops into the LangGraph StateGraph seamlessly.
    """
    model_name = flow_config.resolve_model(agent_config.model)
    validate_fn = _get_validate_fn(agent_config.name)

    async def agent_node(state: AgentState, config: RunnableConfig) -> dict:
        tools = flow_config.get_tools_for_agent(agent_config.name)

        model = ChatOpenAI(
            model=model_name,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens,
        )
        if tools:
            model = model.bind_tools(tools)

        context = _build_context(state, agent_config.name)
        messages = [
            SystemMessage(content=agent_config.prompt),
            HumanMessage(content=context),
        ]

        response, _ = await run_agent_with_tools(
            model, messages, tools, config=config,
            validate_fn=validate_fn,
            min_tool_calls=agent_config.min_tool_calls,
            max_reflections=agent_config.max_reflections,
            quality_criteria=agent_config.quality_criteria,
        )

        cards = _build_section_cards(agent_config.name, response.content, state)

        result: dict = {
            "agent_outputs": {agent_config.name: response.content},
            "messages": [response],
            "sections_generated": [_get_section_name(agent_config.name)],
            "section_cards": cards,
            "active_agents": {agent_config.name: "idle"},
        }

        # Handle approval requirements
        if agent_config.requires_approval:
            result["pending_approvals"] = {agent_config.name: {
                "type": agent_config.approval_type or "general",
                "title": f"{agent_config.display_name} output for {state.target_company or 'job'} {state.target_role or ''}".strip(),
                "agent": agent_config.display_name,
                "content": response.content,
                "priority": agent_config.approval_priority,
            }}
            result["active_agents"] = {agent_config.name: "waiting"}

        # Special case: leetcode_coach conditional approval
        if agent_config.name == "leetcode_coach":
            last_user_msg = ""
            for msg in reversed(state.messages):
                if hasattr(msg, "type") and msg.type == "human":
                    last_user_msg = msg.content.lower()
                    break
            if "solution" in last_user_msg or "explain" in last_user_msg:
                result["pending_approvals"] = {agent_config.name: {
                    "type": "solution_review",
                    "title": "LeetCode solution explanation",
                    "agent": agent_config.display_name,
                    "content": response.content,
                    "priority": "medium",
                }}
                result["active_agents"] = {agent_config.name: "waiting"}

        return result

    return agent_node
