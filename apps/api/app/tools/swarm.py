"""Swarm tools: request_agent_help, tag_agent, spawn_agent, start_group_chat."""

from __future__ import annotations

import json
import logging
import re

from langchain_core.tools import tool

from .shared import (
    _uid,
    _add_pending_agent_request,
    _add_pending_builder_dispatch,
    get_current_group_chat,
    _get_current_topic,
    _get_current_agent,
)

logger = logging.getLogger(__name__)


@tool
def request_agent_help(agent_name: str, task: str, urgency: str = "normal") -> str:
    """Pull another agent into the debate to challenge, fact-check, or expand on a topic.

    Use this when:
    - You think someone's advice needs to be challenged or fact-checked by a specialist
    - A critical angle is missing and another agent has the expertise to cover it
    - You need real data to back up or counter a claim in the thread
    - The user needs a perspective that's outside your expertise

    Be SPECIFIC about the task — frame it as a debate challenge, not a generic request.

    GOOD examples:
    - request_agent_help("salary_tracker", "Fact-check the salary ranges mentioned — pull real L5 comp data from levels.fyi for this market")
    - request_agent_help("daily_coach", "Nobody has addressed the emotional side of this layoff. The user needs support, not just tactics.")
    - request_agent_help("network_mapper", "Challenge my advice to just apply online — find warm connections at these companies instead")

    BAD examples:
    - request_agent_help("salary_tracker", "help with salary")  # too vague
    - request_agent_help("daily_coach", "say something nice")   # not a real task

    Args:
        agent_name: The agent to call (e.g. "salary_tracker", "interview_prep", "daily_coach").
        task: A specific debate challenge — what to fact-check, counter, or add.
        urgency: Priority level — "high", "normal", or "low". Default: "normal".

    Returns:
        JSON confirming the agent has been called into the debate.
    """
    valid_urgencies = ("high", "normal", "low")
    if urgency not in valid_urgencies:
        urgency = "normal"

    # Validate agent_name against known personalities
    try:
        from app.thought_engine import get_all_personalities
        known = get_all_personalities()
        if agent_name not in known:
            # Try normalizing
            normalized = agent_name.strip().lower().replace(" ", "_")
            if normalized not in known:
                available = ", ".join(sorted(known.keys()))
                return json.dumps({
                    "success": False,
                    "error": f"Unknown agent '{agent_name}'. Available: {available}",
                })
            agent_name = normalized

        personality = known[agent_name]
        display_name = personality.get("display_name", agent_name)
        expertise = personality.get("bio", "")
    except Exception:
        display_name = agent_name.replace("_", " ").title()
        expertise = ""

    request = {
        "agent_name": agent_name,
        "task": task,
        "urgency": urgency,
    }

    _add_pending_agent_request(request)

    return json.dumps({
        "success": True,
        "agent_name": agent_name,
        "display_name": display_name,
        "expertise": expertise,
        "message": f"{display_name} has been called into the debate. They'll respond to: {task}",
    })


@tool
def dispatch_builder(title: str, description: str, sections: str = "[]") -> str:
    """Dispatch a background builder to create a rich tutorial on the Prep page.

    The builder runs asynchronously — you'll see progress in the thread.
    Use this when you want to create detailed learning materials:
    tutorials, problem sets, study guides, visual walkthroughs.

    Args:
        title: Tutorial title (e.g. "Core Tree Patterns Visual Walkthrough")
        description: What the tutorial should cover — be specific about structure
        sections: JSON array of section headings to include (e.g. '["Intro", "DFS vs BFS", "Practice"]')

    Returns:
        JSON confirming the builder has been dispatched.
    """
    request = {
        "title": title,
        "description": description,
        "sections": sections,
    }

    _add_pending_builder_dispatch(request)

    return json.dumps({
        "success": True,
        "title": title,
        "message": f"Builder dispatched for '{title}'. It will generate a rich tutorial and save it to the Prep page. Progress will appear in the thread.",
    })


@tool
def tag_agent_in_chat(
    agent_name: str,
    message: str,
    challenge_type: str = "question",
) -> str:
    """Tag another agent in the current group chat to get their input.

    Use this when you want to:
    - Ask a specific agent a question
    - Challenge their previous statement
    - Request they verify/research something
    - Signal agreement or disagreement with their position

    The tagged agent will respond in the next turn.

    Args:
        agent_name: The agent to tag (e.g. "market_intel", "researcher", "tech_analyst")
        message: Your message directed at that agent
        challenge_type: Type of engagement — "question", "challenge", "request", "agree", "disagree"

    Returns:
        Confirmation that the agent has been tagged for the next turn.
    """
    valid_types = ("question", "challenge", "request", "agree", "disagree")
    if challenge_type not in valid_types:
        challenge_type = "question"

    group_chat_id = get_current_group_chat()

    # Validate agent_name against known personalities AND dynamic agents
    normalized = agent_name.strip().lower().replace(" ", "_").replace("-", "")
    display_name = None

    # Check dynamic agents first (they're spawned at runtime)
    try:
        from app.group_chat.dynamic_agents import get_dynamic_agent
        dynamic = get_dynamic_agent(normalized)
        if dynamic:
            agent_name = normalized
            display_name = dynamic.display_name
    except Exception:
        pass

    # If not a dynamic agent, check static personalities
    if not display_name:
        try:
            from app.thought_engine import get_all_personalities
            known = get_all_personalities()
            if normalized in known:
                agent_name = normalized
                personality = known[normalized]
                display_name = personality.get("display_name", agent_name)
            elif agent_name in known:
                personality = known[agent_name]
                display_name = personality.get("display_name", agent_name)
            else:
                # Collect all available agents (static + dynamic)
                from app.group_chat.dynamic_agents import list_dynamic_agents
                dynamic_names = [d.name for d in list_dynamic_agents(group_chat_id)]
                all_available = sorted(set(known.keys()) | set(dynamic_names))
                return json.dumps({
                    "success": False,
                    "error": f"Unknown agent '{agent_name}'. Available: {', '.join(all_available)}",
                })
        except Exception:
            display_name = agent_name.replace("_", " ").title()

    return json.dumps({
        "success": True,
        "agent_name": agent_name,
        "display_name": display_name,
        "challenge_type": challenge_type,
        "group_chat_id": group_chat_id,
        "message": f"@{agent_name} has been tagged ({challenge_type}). They'll respond to: {message[:100]}...",
    })


@tool
def spawn_agent(
    agent_name: str,
    role: str = "",
    expertise: str = "",
    responsibilities: str = "",
    reason: str = "",
) -> str:
    """Spawn a new specialized agent to join the current group discussion.

    Use this when the discussion needs expertise that no current participant has.
    The new agent will be created dynamically and join the conversation.

    Examples of agents you can spawn:
    - "NASAAdvisor" - Space systems expert with NASA background
    - "MITProfessor" - Academic expert for theoretical analysis
    - "SystemsEngineer" - Practical implementation specialist
    - "RadiationEngineer" - Specialist for radiation hardening
    - "ProcurementSpecialist" - Expert on vendors and pricing
    - "BusinessAnalyst" - ROI and market analysis expert

    The agent's expertise is inferred from their name, but you can customize:

    Args:
        agent_name: Name of the agent (e.g., "NASAAdvisor", "MITProfessor").
                   Name format determines their role: suffix like "Advisor",
                   "Engineer", "Professor" sets behavior. Prefix like "NASA",
                   "MIT" sets domain expertise.
        role: Optional custom role title (e.g., "Radiation Hardening Specialist")
        expertise: Optional comma-separated expertise areas to add
        responsibilities: Optional specific responsibilities for this discussion
        reason: Why this agent is needed (helps them contribute effectively)

    Returns:
        Confirmation that the agent has been spawned and will participate.
    """
    from app.group_chat.dynamic_agents import (
        DynamicAgentFactory,
        register_dynamic_agent,
        get_dynamic_agent,
    )

    group_chat_id = get_current_group_chat()
    current_agent = _get_current_agent()

    # Clean the name
    clean_name = re.sub(r"[^a-zA-Z0-9]", "", agent_name)
    if not clean_name:
        return json.dumps({
            "success": False,
            "error": "Invalid agent name. Use names like 'NASAAdvisor' or 'SystemsEngineer'.",
        })

    # Check if already exists
    existing = get_dynamic_agent(clean_name)
    if existing:
        return json.dumps({
            "success": True,
            "agent_name": clean_name.lower(),
            "display_name": existing.display_name,
            "status": "already_exists",
            "message": f"{existing.display_name} is already in the discussion.",
        })

    # Get topic from context
    topic = _get_current_topic() or "general discussion"

    try:
        # Create the dynamic agent using the factory
        dynamic_agent = DynamicAgentFactory.create_from_mention(
            name=clean_name,
            topic=topic,
            spawned_by=current_agent or "system",
            spawn_reason=reason,
            group_chat_id=group_chat_id,
        )

        # Apply customizations if provided
        if role:
            dynamic_agent.role = role
        if expertise:
            extra_expertise = [e.strip() for e in expertise.split(",")]
            dynamic_agent.expertise.extend(extra_expertise)
        if responsibilities:
            dynamic_agent.responsibilities = responsibilities

        # Register the agent in memory
        register_dynamic_agent(dynamic_agent)

        logger.info(
            "Dynamic agent spawned: %s (%s) for chat %d by %s",
            dynamic_agent.display_name, dynamic_agent.role, group_chat_id or 0, current_agent
        )

        return json.dumps({
            "success": True,
            "agent_name": dynamic_agent.name,
            "display_name": dynamic_agent.display_name,
            "role": dynamic_agent.role,
            "domain": dynamic_agent.domain,
            "expertise": dynamic_agent.expertise[:5],
            "spawned_by": current_agent,
            "group_chat_id": group_chat_id,
            "status": "spawned",
            "instructions": f"IMPORTANT: To bring {dynamic_agent.display_name} into the discussion, "
                           f"you MUST mention them with @{dynamic_agent.name} in your response. "
                           f"They will then join and contribute their {dynamic_agent.role} expertise.",
        })

    except Exception as e:
        logger.error("Failed to spawn agent %s: %s", agent_name, e)
        return json.dumps({
            "success": False,
            "error": f"Failed to spawn agent: {str(e)}",
        })


@tool
async def start_group_chat(
    topic: str,
    initial_message: str,
    suggested_participants: str,
    urgency: str = "normal",
) -> str:
    """Start a group discussion when you discover something worth debating.

    Use this when:
    - You've found conflicting information that needs multiple perspectives
    - A topic requires expertise from several domains
    - You want to brainstorm or research a complex question
    - A significant insight warrants group deliberation

    Args:
        topic: The discussion topic (e.g. "emerging battery technology for EV products")
        initial_message: Your opening message to kick off the discussion
        suggested_participants: JSON array of agent names to invite (e.g. '["researcher", "market_intel"]')
        urgency: Priority level — "high", "normal", or "low". Default: "normal".

    Returns:
        JSON with the new group chat ID and status.
    """
    valid_urgencies = ("high", "normal", "low")
    if urgency not in valid_urgencies:
        urgency = "normal"

    try:
        participants = json.loads(suggested_participants) if isinstance(suggested_participants, str) else suggested_participants
        if not isinstance(participants, list) or len(participants) < 1:
            return json.dumps({
                "success": False,
                "error": "suggested_participants must be a JSON array with at least 1 agent",
            })
    except json.JSONDecodeError:
        return json.dumps({
            "success": False,
            "error": "suggested_participants must be valid JSON array",
        })

    # Validate participants against known agents
    try:
        from app.thought_engine import get_all_personalities
        known = get_all_personalities()
        validated_participants = []
        for p in participants:
            if p in known:
                validated_participants.append(p)
            else:
                normalized = p.strip().lower().replace(" ", "_")
                if normalized in known:
                    validated_participants.append(normalized)

        if len(validated_participants) < 1:
            available = ", ".join(sorted(known.keys()))
            return json.dumps({
                "success": False,
                "error": f"No valid participants found. Available agents: {available}",
            })

        participants = validated_participants
    except Exception as e:
        logger.warning("Could not validate participants: %s", e)

    # Determine initiator (the calling agent)
    initiator = "agent"
    try:
        import inspect
        frame = inspect.currentframe()
        if frame and frame.f_back and frame.f_back.f_locals:
            initiator = frame.f_back.f_locals.get("agent", "agent")
    except Exception:
        pass

    # Add initiator to participants if not already included
    if initiator not in participants and initiator != "agent":
        participants.insert(0, initiator)

    try:
        from app.db import create_group_chat, create_timeline_post
        from app.group_chat.orchestrator import start_orchestrator
        from app.group_chat.controls import GroupChatConfig

        user_id = _uid()

        # Create config based on urgency
        config = GroupChatConfig()
        if urgency == "high":
            config.max_turns = 30
            config.turn_timeout_seconds = 20
        elif urgency == "low":
            config.max_turns = 15
            config.turn_timeout_seconds = 45

        # Create the group chat
        chat_id = await create_group_chat(
            topic=topic,
            participants=participants,
            initiator=initiator,
            config={
                "max_turns": config.max_turns,
                "max_tokens": config.max_tokens,
                "turn_mode": config.turn_mode,
                "urgency": urgency,
            },
            user_id=user_id,
        )

        # Create initial timeline post
        await create_timeline_post(
            agent=initiator,
            post_type="group_chat_start",
            content=initial_message,
            context={
                "group_chat_id": chat_id,
                "topic": topic,
                "participants": participants,
            },
            user_id=user_id,
        )

        # Start the orchestrator (runs in background)
        await start_orchestrator(chat_id, config)

        return json.dumps({
            "success": True,
            "group_chat_id": chat_id,
            "topic": topic,
            "participants": participants,
            "urgency": urgency,
            "message": f"Group chat started on '{topic}' with {len(participants)} participants.",
        })

    except Exception as e:
        logger.error("start_group_chat error: %s", e)
        return json.dumps({
            "success": False,
            "error": str(e),
        })
