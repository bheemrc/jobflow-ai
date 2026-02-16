"""Coach node — fast router that extracts context and dispatches to specialist agents.

Uses flow_config for agent names, routing prompt, and fallback rules.
"""

from __future__ import annotations

import re
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage

from app.flow_config import get_flow_config
from app.memory import maybe_summarize
from app.state import AgentState

logger = logging.getLogger(__name__)


def _get_model():
    config = get_flow_config()
    return ChatOpenAI(
        model=config.resolve_model(config.routing.coach_model),
        temperature=config.routing.coach_temperature,
        max_tokens=config.routing.coach_max_tokens,
    )


async def coach_node(state: AgentState) -> dict:
    """Decide what to do based on user context and conversation."""
    config = get_flow_config()

    # Summarize old messages if conversation is long
    conversation = await maybe_summarize(list(state.messages))
    coach_prompt = config.get_coach_prompt()

    # Check if specialists already produced output this session
    has_prior_output = any(
        hasattr(m, "type") and m.type == "ai" and len(m.content) > 200
        for m in state.messages[:-1]  # exclude the latest message
    )

    if has_prior_output:
        coach_prompt += (
            "\n\n## Conversational Follow-ups\n"
            "The conversation above already contains specialist analysis.\n"
            "If the user asks a follow-up question, wants clarification, or discusses the existing analysis, "
            "use [ROUTE: respond] to answer directly from the conversation context.\n"
            "Only route to a specialist again if the user explicitly asks for NEW analysis, "
            "a different topic, or work that requires specialist tools.\n"
        )

    if state.focus_topic:
        focus_instruction = (
            f"FOCUS MODE: This is a dedicated study room for: {state.focus_topic}\n"
            f"Stay focused on this topic.\n\n"
        )
        coach_prompt = focus_instruction + coach_prompt

    messages = [SystemMessage(content=coach_prompt)] + conversation

    response = await _get_model().ainvoke(messages)
    content = response.content or ""

    # Extract routing decision (now supports multiple agents)
    agents = _parse_routing_decisions(content, state, config.valid_agents, config.routing.fallbacks)

    # Extract context (company/role) from coach's response
    updates: dict = {}
    company = _extract_tag(content, "COMPANY")
    role = _extract_tag(content, "ROLE")
    if company:
        updates["target_company"] = company
    if role:
        updates["target_role"] = role

    # Also try to extract from conversation if coach didn't tag it
    if not company and not state.target_company:
        company = _extract_company_from_messages(state)
        if company:
            updates["target_company"] = company
    if not role and not state.target_role:
        role = _extract_role_from_messages(state)
        if role:
            updates["target_role"] = role

    # Strip all control tags from the coach's visible response
    clean_content = _strip_tags(content)
    clean_msg = AIMessage(content=clean_content)

    return {
        "messages": [clean_msg],
        "dispatched_agents": agents,
        "active_agents": (
            {a: "running" for a in agents if a != "respond"}
            if agents != ["respond"]
            else {}
        ),
        # Clear per-turn accumulator fields (reducers will merge new values)
        "agent_outputs": {},
        "pending_approvals": {},
        "approval_decisions": {},
        "section_cards": [],
        "sections_generated": [],
        **updates,
    }


def _extract_tag(content: str, tag: str) -> str:
    """Extract a [TAG: value] from content."""
    match = re.search(rf"\[{tag}:\s*(.+?)\]", content, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _strip_tags(content: str) -> str:
    """Remove all control tags from the response."""
    cleaned = re.sub(r"\[ROUTE:\s*.+?\]", "", content)
    cleaned = re.sub(r"\[COMPANY:\s*.+?\]", "", cleaned)
    cleaned = re.sub(r"\[ROLE:\s*.+?\]", "", cleaned)
    return cleaned.strip()


def _parse_routing_decisions(
    content: str,
    state: AgentState,
    valid_agents: set[str],
    fallbacks: list[dict],
) -> list[str]:
    """Parse one or more routing decisions from coach output.

    Supports both single and multi-agent routing:
      [ROUTE: resume_tailor]
      [ROUTE: resume_tailor, interview_prep, job_intake]
    """
    route_match = re.search(r"\[ROUTE:\s*(.+?)\]", content)
    if route_match:
        raw = route_match.group(1)
        agents = [a.strip() for a in raw.split(",")]
        agents = [a for a in agents if a in valid_agents]
        if agents:
            # If "respond" is mixed with specialists, remove it
            if len(agents) > 1:
                agents = [a for a in agents if a != "respond"]
            return agents

    # Fallback: config-driven routing based on state
    for fb in fallbacks:
        condition = fb.get("condition", "")
        route = fb.get("route", ["respond"])

        if condition == "no_resume" and not state.resume_id:
            return route
        if condition == "interview_stage" and state.job_status == "interview" and state.target_company:
            return route
        if condition == "has_company_and_role" and state.target_company and state.target_role:
            return route
        if condition == "has_company" and state.target_company:
            return route
        if condition == "default":
            return route

    return ["respond"]


def _extract_company_from_messages(state: AgentState) -> str:
    """Try to find a company name from recent user messages."""
    known_companies = [
        "Google", "Amazon", "Apple", "Microsoft", "Meta", "Netflix",
        "Uber", "Lyft", "Airbnb", "Stripe", "Coinbase", "OpenAI",
        "Anthropic", "Tesla", "SpaceX", "Salesforce", "Adobe",
        "LinkedIn", "Twitter", "Snap", "Pinterest", "Spotify",
        "Databricks", "Snowflake", "Palantir", "Nvidia", "Intel",
        "IBM", "Oracle", "Samsung", "Sony", "Walmart", "JPMorgan",
        "Goldman Sachs", "Morgan Stanley", "Capital One", "Bloomberg",
        "Citadel", "Two Sigma", "Jane Street", "DoorDash", "Instacart",
        "Robinhood", "Square", "Block", "Shopify", "Atlassian",
    ]
    for msg in reversed(state.messages):
        if hasattr(msg, "type") and msg.type == "human":
            text = msg.content
            for company in known_companies:
                if company.lower() in text.lower():
                    return company
            match = re.search(
                r"(?:at|for|to|targeting|apply\w* (?:to|at|for))\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)",
                text,
            )
            if match:
                return match.group(1).strip()
            break
    return ""


def _extract_role_from_messages(state: AgentState) -> str:
    """Try to find a role/title from recent user messages."""
    role_patterns = [
        r"(?:for|as)\s+(?:a\s+)?(.+?(?:engineer|developer|scientist|manager|analyst|architect|lead|designer|sre|devops)\w*)",
        r"(?:SDE|SWE|PM|TPM|SDM|EM|IC|TL)\s*(?:\d|[IVX]+)?",
    ]
    for msg in reversed(state.messages):
        if hasattr(msg, "type") and msg.type == "human":
            text = msg.content
            for pattern in role_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(0).strip() if match.lastindex is None else match.group(1).strip()
            break
    return ""
