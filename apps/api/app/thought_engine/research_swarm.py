"""Research swarm system — dynamic agent invention, web search, debate, consensus, builder."""

from __future__ import annotations

import asyncio
import logging
import random
import re

from app.db import create_timeline_post
from app.event_bus import event_bus

from .core import (
    SWARM_MAX_ACTIVATIONS,
    SWARM_QUEUE_TIMEOUT,
    MAX_SWARM_REPLY_LENGTH,
    MAX_DYNAMIC_REPLY_LENGTH,
    DYNAMIC_AGENT_CAP,
    DYNAMIC_DEBATE_CAP,
    BUILDER_CAP_PER_POST,
    AgentRequest,
    DynamicAgent,
    BuilderState,
    SwarmState,
    _active_builders,
    _enforce_quality,
    _system_context,
    _system_context_slim,
    _build_agent_context,
    _get_tools_for_agent,
)
from .rate_limiting import _check_rate_limit, _record_post
from .personality import get_agent_personality, get_all_personalities

logger = logging.getLogger("app.thought_engine")


# ── Legacy Swarm (personality-based) ──

async def _route_swarm_initial_agents(content: str) -> list[str]:
    """Pick 2-3 agents whose expertise DIRECTLY matches the user's topic."""
    personalities = get_all_personalities()
    if not personalities:
        return ["daily_coach"]

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        agent_list = "\n".join(
            f"- {name}: {p.get('bio', '')}"
            for name, p in personalities.items()
        )

        model = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, max_tokens=100)
        response = await model.ainvoke([
            SystemMessage(content=f"""Pick 2-3 agents whose expertise DIRECTLY helps with the user's specific request.
ONLY pick agents who can contribute something concrete and on-topic.
DO NOT pick agents just to fill slots — if only 2 are relevant, pick 2.

Available agents:
{agent_list}

Return ONLY comma-separated agent names. Nothing else."""),
            HumanMessage(content=f"User: \"{content}\""),
        ])

        chosen = [
            name.strip().lower().replace(" ", "_")
            for name in response.content.strip().split(",")
        ]
        chosen = [n for n in chosen if n in personalities][:3]
        return chosen or ["daily_coach"]

    except Exception as e:
        logger.error("Swarm routing failed: %s", e)
        return ["daily_coach"]


async def _analyze_thread_gaps(
    original_content: str,
    thread_replies: list[dict],
    responded_agents: set,
    all_personalities: dict,
) -> list[dict]:
    """Decide if the thread needs more agents."""
    if not thread_replies:
        return []

    available = {
        name: p for name, p in all_personalities.items()
        if name not in responded_agents
    }
    if not available:
        return []

    said_so_far = "\n".join(
        f"- [{r['agent']}]: {r['content'][:200]}"
        for r in thread_replies[-6:]
    )

    agent_roster = "\n".join(
        f"- {name}: {p.get('bio', '')}"
        for name, p in available.items()
    )

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        import json

        model = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, max_tokens=300)
        response = await model.ainvoke([
            SystemMessage(content="""You decide if a discussion thread needs MORE agents.

CRITICAL RULES:
- The user's original question defines what's ON-TOPIC. Everything must serve THAT question.
- Only add an agent if they can contribute something CONCRETE and DIFFERENT that directly helps the user.
- An agent whose expertise is UNRELATED to the user's question should NOT be added, ever.
- If the thread already covers the topic well with 2-4 agents, return []. More is not better.
- Prefer returning [] over adding agents who will just pad the thread.

If you DO find a genuine gap, return a JSON array:
[{"agent_name": "...", "task": "Specific on-topic task that directly helps the user"}]

Pick at most 1-2 agents. Return [] if the thread is sufficient."""),
            HumanMessage(content=f"""User asked: "{original_content}"

Recent replies:
{said_so_far}

Available agents:
{agent_roster}

Is there a genuine on-topic gap? Return JSON array or []."""),
        ])

        text = response.content.strip()
        if "[" in text:
            json_str = text[text.index("["):text.rindex("]") + 1]
            requests = json.loads(json_str)
            valid = []
            for req in requests:
                name = req.get("agent_name", "").strip().lower().replace(" ", "_")
                if name in available and req.get("task"):
                    valid.append({
                        "agent_name": name,
                        "task": req["task"],
                        "urgency": req.get("urgency", "normal"),
                    })
            return valid[:2]
        return []

    except Exception as e:
        logger.error("Thread gap analysis failed: %s", e)
        return []


async def _generate_swarm_agent_reply(
    original_post: dict,
    request: AgentRequest,
    state: SwarmState,
) -> None:
    """Generate a focused, on-topic reply that engages with the thread."""
    agent_name = request.agent_name
    parent_id = original_post.get("id")

    if not _check_rate_limit(agent_name, parent_id, user_initiated=True):
        return

    await event_bus.publish({
        "type": "agent_thinking",
        "agent": agent_name,
        "thread_id": parent_id,
        "context": "swarm",
    })

    personality = get_agent_personality(agent_name)
    voice = personality.get("voice", "professional")
    display_name = personality.get("display_name", agent_name)
    bio = personality.get("bio", "")
    user_content = original_post.get("content", "")

    thread_context = ""
    try:
        from app.db import get_timeline_replies
        replies = await get_timeline_replies(parent_id, limit=20)
        if replies:
            lines = []
            for r in replies:
                p = get_agent_personality(r['agent'])
                snippet = r['content'][:400]
                lines.append(f"[{p.get('display_name', r['agent'])}]: {snippet}")
            thread_context = "\n\n".join(lines)
    except Exception:
        pass

    all_personalities = get_all_personalities()
    available_names = [
        f"{p.get('display_name', n)} ({n})"
        for n, p in all_personalities.items()
        if n not in state.responded_agents and n != agent_name
    ]

    if request.requested_by != "router":
        req_name = get_agent_personality(request.requested_by).get("display_name", request.requested_by)
        entry_frame = f"{req_name} pulled you in: \"{request.task}\""
    elif request.wave == 1:
        entry_frame = "You're one of the first responders."
    else:
        entry_frame = f"You were brought in because: {request.task}"

    rich_context = await _build_agent_context()

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        tools = _get_tools_for_agent(agent_name)
        from app.tools import request_agent_help as rah_tool
        tool_names = {getattr(t, 'name', '') for t in tools}
        if 'request_agent_help' not in tool_names:
            tools = list(tools) + [rah_tool]

        model = ChatOpenAI(model="gpt-4o-mini", temperature=0.8, max_tokens=800)
        if tools:
            model = model.bind_tools(tools)

        system_prompt = f"""{_system_context()}

You are {display_name}. {voice}
Expertise: {bio}

{entry_frame}

{f"Data context: {rich_context}" if rich_context else ""}

## WHAT THE HUMAN USER ACTUALLY ASKED
"{user_content}"

## ABSOLUTE RULES
1. **STAY ON TOPIC.** The user's question is sacred. EVERYTHING you say must directly help answer it. Do NOT pivot to your default specialty if it's unrelated.
2. **Be concise.** 3-8 sentences max. No walls of text. No bullet-point dumps. Say one sharp thing, not ten vague things.
3. **Engage the thread.** If others already replied, react to what they said: agree, disagree, add a missing angle. Name them. "I'd push back on what Interview Prep said because..."
4. **Use tools for real data.** Don't give generic advice — look things up, pull specifics.
5. **Only call request_agent_help if there's a genuine gap** that YOU can't fill and another specific agent can. Most of the time, don't call anyone.
6. **If you have nothing on-topic to add, say one brief supportive thing and stop.** Don't pad.
7. No hashtags. No "let me know if you need anything." No "here's what I recommend:" followed by 10 bullets.

{f"Available to call in: {', '.join(available_names)}" if available_names else ""}"""

        user_msg = f"""User: "{user_content}"

{f"Thread so far:{chr(10)}{thread_context}" if thread_context else "(You're first to respond.)"}"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_msg),
        ]

        from app.tools import drain_pending_agent_requests
        drain_pending_agent_requests()

        if tools:
            from app.nodes.tool_executor import run_agent_with_tools
            final_message, _ = await run_agent_with_tools(
                model=model,
                messages=messages,
                tools=tools,
                config=None,
                max_rounds=3,
                min_tool_calls=0,
                max_reflections=0,
            )
            content = final_message.content.strip() if final_message else ""
        else:
            response = await model.ainvoke(messages)
            content = response.content.strip()

        if not content:
            return

        content = _enforce_quality(content, MAX_SWARM_REPLY_LENGTH)

        reply = await create_timeline_post(
            agent=agent_name,
            post_type="thread",
            content=content,
            parent_id=original_post["id"],
            context={
                "in_reply_to": "user",
                "swarm_wave": request.wave,
                "requested_by": request.requested_by,
                "task": request.task,
            },
        )

        if reply:
            _record_post(agent_name, original_post["id"])
            await event_bus.publish({
                "type": "timeline_post",
                "post": reply,
                "source": "thought_engine",
            })
            logger.info(
                "Swarm reply from %s (wave %d) to post %d",
                agent_name, request.wave, original_post["id"],
            )

    except Exception as e:
        logger.error("Swarm agent reply from %s failed: %s", agent_name, e)


async def _orchestrate_swarm(post: dict) -> None:
    """Orchestrate a focused agent swarm on a user's post."""
    content = post.get("content", "")
    post_id = post.get("id")

    state = SwarmState(
        post_id=post_id,
        parent_id=None,
        user_content=content,
    )

    try:
        initial_agents = await _route_swarm_initial_agents(content)

        await event_bus.publish({
            "type": "swarm_started",
            "post_id": post_id,
            "initial_agents": initial_agents,
            "max_activations": state.max_activations,
        })

        current_wave = 1
        for agent_name in initial_agents:
            await state.pending_requests.put(AgentRequest(
                agent_name=agent_name,
                task=f"Respond to: {content[:200]}",
                urgency="high",
                requested_by="router",
                wave=current_wave,
            ))

        wave_agents_remaining = len(initial_agents)
        gap_analysis_count = 0
        MAX_GAP_ANALYSES = 2

        while True:
            if not await state.can_activate():
                break

            try:
                request = await asyncio.wait_for(
                    state.pending_requests.get(),
                    timeout=SWARM_QUEUE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                if (gap_analysis_count < MAX_GAP_ANALYSES
                        and await state.can_activate()
                        and state.activation_count >= 2):
                    gap_analysis_count += 1
                    gap_count = await _run_gap_analysis_and_queue(
                        post, state, current_wave + 1,
                    )
                    if gap_count:
                        current_wave += 1
                        wave_agents_remaining = gap_count
                        continue
                break

            if state.has_responded(request.agent_name):
                wave_agents_remaining = max(0, wave_agents_remaining - 1)
                continue

            if not await state.record_activation(request.agent_name):
                break

            await event_bus.publish({
                "type": "agent_requested",
                "post_id": post_id,
                "agent": request.agent_name,
                "task": request.task,
                "requested_by": request.requested_by,
                "wave": request.wave,
                "activation_count": state.activation_count,
                "max_activations": state.max_activations,
            })

            if state.activation_count > 1:
                await asyncio.sleep(random.uniform(2, 5))

            await _generate_swarm_agent_reply(post, request, state)

            from app.tools import drain_pending_agent_requests
            new_requests = drain_pending_agent_requests()
            for req in new_requests:
                agent = req["agent_name"]
                if not state.has_responded(agent):
                    await state.pending_requests.put(AgentRequest(
                        agent_name=agent,
                        task=req["task"],
                        urgency=req.get("urgency", "normal"),
                        requested_by=request.agent_name,
                        wave=request.wave + 1,
                    ))
                    wave_agents_remaining += 1

            wave_agents_remaining = max(0, wave_agents_remaining - 1)

            if (wave_agents_remaining <= 0
                    and gap_analysis_count < MAX_GAP_ANALYSES
                    and await state.can_activate()):
                gap_analysis_count += 1
                gap_count = await _run_gap_analysis_and_queue(
                    post, state, current_wave + 1,
                )
                if gap_count:
                    current_wave += 1
                    wave_agents_remaining = gap_count

        await event_bus.publish({
            "type": "swarm_complete",
            "post_id": post_id,
            "total_activations": state.activation_count,
            "agents_responded": sorted(state.responded_agents),
        })

        logger.info(
            "Swarm complete for post %d: %d agents (%s)",
            post_id, state.activation_count, ", ".join(sorted(state.responded_agents)),
        )

    except Exception as e:
        logger.error("Swarm orchestration failed for post %d: %s", post_id, e)


async def _run_gap_analysis_and_queue(
    post: dict,
    state: SwarmState,
    next_wave: int,
) -> int:
    """Run gap analysis on the thread, queue new agents only if genuinely needed."""
    post_id = post.get("id")
    try:
        from app.db import get_timeline_replies
        replies = await get_timeline_replies(post_id, limit=20)
    except Exception:
        replies = []

    if not replies:
        return 0

    all_personalities = get_all_personalities()
    gap_requests = await _analyze_thread_gaps(
        post.get("content", ""),
        replies,
        state.responded_agents,
        all_personalities,
    )

    queued = 0
    for req in gap_requests:
        agent = req["agent_name"]
        if not state.has_responded(agent) and await state.can_activate():
            await state.pending_requests.put(AgentRequest(
                agent_name=agent,
                task=req["task"],
                urgency=req.get("urgency", "normal"),
                requested_by="router",
                wave=next_wave,
            ))
            queued += 1

    if queued:
        logger.info("Gap analysis queued %d agents for wave %d", queued, next_wave)

    return queued


# ── Dynamic Agent Swarm (Research Curators) ──


async def _invent_dynamic_agents(content: str) -> list[DynamicAgent]:
    """Spawn 3-4 specialized agents, each with a distinct research mandate."""
    import json as _json
    import time

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        from datetime import datetime

        model = ChatOpenAI(model="gpt-4o", temperature=0.7, max_tokens=1200)
        year = datetime.now().year
        response = await model.ainvoke([
            SystemMessage(content=f"""{_system_context()}

You are The Nexus — the collective intelligence that spawns specialized agents for missions.
Design a STRIKE TEAM of 3-4 agents to investigate a topic. Each agent is a specialist mind.

CRITICAL DESIGN PRINCIPLES:
1. DIVERSE ANGLES — each agent attacks the problem from a fundamentally different direction
2. NATURAL TENSION — pair at least one skeptic/devil's advocate against an advocate
3. UNIQUE IDENTITY — each agent needs a memorable name that reflects their specialty (not generic like "Researcher A")
4. REAL SEARCH — each agent will execute web searches, so queries must be specific and likely to return useful results

AGENT ARCHETYPES (pick 3-4 that fit the topic):
- The Empiricist: finds hard data, benchmarks, measurements, controlled experiments
- The Field Operative: finds real-world case studies, production deployments, who actually built this
- The Contrarian: finds counter-arguments, failure cases, limitations, what could go wrong
- The Synthesizer: finds cross-domain connections, analogies from other fields, novel combinations
- The Archaeologist: finds historical context, evolution of the technology, lessons from the past
- The Scout: finds bleeding-edge developments, upcoming releases, research papers, prototypes
- The Practitioner: finds implementation guides, best practices, common pitfalls, tutorials
- The Economist: finds cost analysis, ROI data, resource requirements, total cost of ownership

Return ONLY a valid JSON array. No markdown fences, no explanation.

Schema per agent:
{{
  "display_name": "Velocity Probe",
  "avatar": "⚡",
  "expertise": "Performance profiling and benchmark analysis for web frameworks",
  "research_angle": "Raw performance data: latency, throughput, memory footprint, startup time",
  "search_queries": ["framework X vs Y performance benchmark {year}", "framework Z latency profiling results {year}"],
  "tone": "skeptical",
  "stance": "Will challenge performance claims that lack reproducible benchmarks"
}}

tone: "methodical" | "pragmatic" | "enthusiastic" | "skeptical" | "analytical" | "provocative"
stance: A one-sentence description of this agent's perspective/bias (creates debate tension)
"""),
            HumanMessage(content=f"Mission briefing: \"{content}\"\n\nSpawn your strike team:"),
        ])

        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        agents_data = _json.loads(text)
        if not isinstance(agents_data, list):
            agents_data = [agents_data]

        agents = []
        ts = str(int(time.time()))
        for i, a in enumerate(agents_data[:DYNAMIC_AGENT_CAP]):
            agent_id = re.sub(r"[^a-z0-9_]", "_", a.get("display_name", f"agent_{i}").lower().replace(" ", "_")) + f"_{ts}"
            research_angle = a.get("research_angle", "")
            stance = a.get("stance", "")
            identity = f"{research_angle}\nStance: {stance}" if stance else research_angle
            agent = DynamicAgent(
                agent_id=agent_id,
                display_name=a.get("display_name", f"Agent {i+1}"),
                avatar=a.get("avatar", "🔍"),
                expertise=a.get("expertise", ""),
                opinion_seed=identity,
                tone=a.get("tone", "methodical"),
            )
            agent.search_queries = a.get("search_queries", [])
            agents.append(agent)
        return agents

    except Exception as e:
        logger.error("Failed to assign research curators: %s", e)
        import time
        ts = str(int(time.time()))
        fallback = DynamicAgent(
            agent_id=f"researcher_{ts}",
            display_name="Research Lead",
            avatar="🔬",
            expertise="Comprehensive research on the user's topic",
            opinion_seed="Find the best real-world sources and evidence",
            tone="methodical",
        )
        fallback.search_queries = [content]
        return [fallback]


async def _generate_dynamic_agent_reply(
    post: dict,
    agent: DynamicAgent,
    state: SwarmState,
    thread_context: str = "",
    skip_timeline: bool = False,
) -> dict | None:
    """Research curator: search the web, find real expert content, report findings with citations."""
    parent_id = post.get("id")

    await event_bus.publish({
        "type": "agent_thinking",
        "agent": agent.agent_id,
        "thread_id": parent_id,
        "context": "swarm",
    })

    user_content = post.get("content", "")

    from app.tools import TOOL_REGISTRY
    tool_names = ["web_search"]
    tools = [TOOL_REGISTRY[t] for t in tool_names if t in TOOL_REGISTRY]

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        model = ChatOpenAI(model="gpt-4o", temperature=0.3, max_tokens=2000)
        if tools:
            model = model.bind_tools(tools)

        search_queries = getattr(agent, "search_queries", [])
        queries_instruction = ""
        if search_queries:
            queries_instruction = f"""
Your assigned search queries (run ALL of them):
{chr(10).join(f'  - "{q}"' for q in search_queries)}

You MUST call the web_search tool for each query. Do not skip searches."""

        other_agents = [
            a for a in state.dynamic_agents.values()
            if a.agent_id != agent.agent_id
        ]

        system_prompt = f"""{_system_context()}

You are {agent.display_name} [{agent.agent_id[:8]}], Nexus specialist.
Angle: {agent.opinion_seed} | Expertise: {agent.expertise} | Tone: {agent.tone}
{queries_instruction}

PROTOCOL: SEARCH web (2+ calls mandatory), cite sources, include hard data (numbers, benchmarks, dates).
Report contradictions. List URLs in Sources section. Lead with your boldest finding. No filler.
{f"Others: {', '.join('@' + a.display_name for a in other_agents)}" if other_agents else ""}
{f"Prior findings (build on, don't duplicate):{chr(10)}{thread_context[:3000]}" if thread_context else ""}"""

        user_msg = f'Research this topic from your angle: "{user_content}"'

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_msg),
        ]

        from app.nodes.tool_executor import run_agent_with_tools
        final_message, _ = await run_agent_with_tools(
            model=model,
            messages=messages,
            tools=tools,
            config=None,
            max_rounds=4,
            min_tool_calls=2,
            max_reflections=1,
        )
        content = final_message.content.strip() if final_message else ""

        if not content:
            return None

        content = _enforce_quality(content, MAX_DYNAMIC_REPLY_LENGTH)

        reply_context = {
            "in_reply_to": "user",
            "research_curator": True,
            "convergence_phase": "research",
            "dynamic_agent": {
                "agent_id": agent.agent_id,
                "display_name": agent.display_name,
                "avatar": agent.avatar,
                "expertise": agent.expertise,
                "tone": agent.tone,
            },
        }

        if skip_timeline:
            reply = {"content": content, "agent": agent.agent_id}
            logger.info("Research curator %s reported findings (skip_timeline) for post %d", agent.display_name, parent_id)
            return reply

        reply = await create_timeline_post(
            agent=agent.agent_id,
            post_type="thread",
            content=content,
            parent_id=parent_id,
            context=reply_context,
        )

        if reply:
            _record_post(agent.agent_id, parent_id)
            await event_bus.publish({
                "type": "timeline_post",
                "post": reply,
                "source": "thought_engine",
            })
            logger.info("Research curator %s reported findings for post %d", agent.display_name, parent_id)
            return reply

    except Exception as e:
        logger.error("Research curator %s failed: %s", agent.display_name, e)

    return None


async def _run_builder(
    builder_id: str,
    post_id: int,
    agent: DynamicAgent,
    title: str,
    description: str,
    sections_json: str,
    user_content: str,
    debate_context: str = "",
    skip_timeline: bool = False,
) -> None:
    """Background task: generate a rich tutorial informed by the agent debate."""
    import json as _json

    builder = BuilderState(
        builder_id=builder_id,
        post_id=post_id,
        title=title,
        agent_id=agent.agent_id,
    )
    _active_builders[builder_id] = builder

    try:
        try:
            section_headings = _json.loads(sections_json) if sections_json else []
        except Exception:
            section_headings = []

        await event_bus.publish({
            "type": "builder_dispatched",
            "post_id": post_id,
            "builder_id": builder_id,
            "title": title,
            "agent_id": agent.agent_id,
            "agent_name": agent.display_name,
        })

        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        model = ChatOpenAI(model="gpt-4o", temperature=0.7, max_tokens=4096)

        # Phase 0: Generate dynamic section headings if none provided
        if not section_headings:
            builder.stage = "planning sections"
            builder.percent = 5
            await event_bus.publish({
                "type": "builder_progress",
                "post_id": post_id,
                "builder_id": builder_id,
                "title": title,
                "percent": 5,
                "stage": "planning sections",
            })

            try:
                headings_model = ChatOpenAI(model="gpt-4o-mini", temperature=0.8, max_tokens=300)
                headings_resp = await headings_model.ainvoke([
                    SystemMessage(content=f"""Generate 5-7 section headings for a tutorial titled "{title}" about: {user_content}

Rules:
- Make headings SPECIFIC to the topic, not generic (never use "Introduction", "Core Concepts", "Key Takeaways")
- Use curiosity-driven, engaging phrasing (questions, "Why X matters", "The hidden Y", "What most people get wrong about Z")
- Order them in a logical learning progression
- Each heading should make the reader WANT to read that section
- CRITICAL: Each section must cover DISTINCT content — no two sections should discuss the same subtopic, statistic, or example. If one section covers market growth, no other section should repeat those numbers.

Return ONLY a JSON array of heading strings. No markdown fences."""),
                    HumanMessage(content="Generate the headings:"),
                ])
                headings_text = headings_resp.content.strip()
                if headings_text.startswith("```"):
                    headings_text = headings_text.split("\n", 1)[1] if "\n" in headings_text else headings_text[3:]
                    if headings_text.endswith("```"):
                        headings_text = headings_text[:-3]
                parsed_headings = _json.loads(headings_text)
                if isinstance(parsed_headings, list) and len(parsed_headings) >= 3:
                    section_headings = parsed_headings
            except Exception as e:
                logger.warning("Dynamic headings failed, using fallback: %s", e)

            if not section_headings:
                section_headings = ["Introduction", "Core Concepts", "Practice Problems", "Key Takeaways"]

        # Phase 1: Outline (5-20%)
        builder.stage = "outline"
        builder.percent = 10
        await event_bus.publish({
            "type": "builder_progress",
            "post_id": post_id,
            "builder_id": builder_id,
            "title": title,
            "percent": 10,
            "stage": "outline",
        })

        debate_instruction = ""
        if debate_context:
            debate_instruction = f"""
IMPORTANT: Research curators investigated this topic and found real-world evidence:
{debate_context}

Your tutorial MUST be grounded in these research findings.
- Cite specific sources by name and URL when making claims
- Where multiple sources agree, state the consensus clearly
- Where sources disagree, present both sides with their evidence
- Include real data points: benchmark numbers, GitHub stars, adoption metrics
- Do NOT add claims that aren't supported by the research findings
- If there are gaps in the research, acknowledge them"""

        outline_resp = await model.ainvoke([
            SystemMessage(content=f"""You are building a tutorial: "{title}"
Topic context: {user_content}
Description: {description}
{debate_instruction}

Create a detailed outline for these sections: {_json.dumps(section_headings)}

Return a JSON object mapping each section heading to a description of what to cover.
The outline should reflect the insights from the expert debate — not just generic content.

CRITICAL RULE — NO DUPLICATION:
- Assign each specific fact, statistic, data point, or example to EXACTLY ONE section.
- If a market figure (e.g. "$7.5B → $18B") belongs in the growth section, NO other section may repeat it.
- If a company example (e.g. "AST SpaceMobile") belongs in the technology section, other sections should reference it only briefly ("as discussed in Section X") if needed.
- In your outline, explicitly note which key facts and sources belong to each section.
- Later sections should build on earlier ones, not rehash them.

Return ONLY valid JSON — no fences."""),
            HumanMessage(content="Generate the outline:"),
        ])

        outline_text = outline_resp.content.strip()
        if outline_text.startswith("```"):
            outline_text = outline_text.split("\n", 1)[1] if "\n" in outline_text else outline_text[3:]
            if outline_text.endswith("```"):
                outline_text = outline_text[:-3]
        try:
            outline = _json.loads(outline_text)
        except Exception:
            outline = {h: f"Cover {h}" for h in section_headings}

        # Phase 1.5: Generate TL;DR
        builder.percent = 18
        builder.stage = "generating TL;DR"
        try:
            tldr_model = ChatOpenAI(model="gpt-4o-mini", temperature=0.5, max_tokens=300)
            tldr_resp = await tldr_model.ainvoke([
                SystemMessage(content=f"""Based on this tutorial outline, generate a TL;DR summary.

Tutorial: "{title}"
Topic: {user_content}
Sections: {_json.dumps(list(outline.keys()))}
Outline details: {_json.dumps(outline)}

Return EXACTLY 3-4 bullet points summarizing the key takeaways.
Format as plain text bullets (one per line, starting with "- ").
Be specific and actionable — no vague platitudes.
Return ONLY the bullet lines, nothing else."""),
                HumanMessage(content="Generate the TL;DR bullets:"),
            ])
            tldr_bullets = tldr_resp.content.strip()
            tldr_block = f"> [!TLDR]\n" + "\n".join(
                f"> {line}" for line in tldr_bullets.split("\n") if line.strip()
            )
        except Exception as e:
            logger.warning("TL;DR generation failed: %s", e)
            tldr_block = ""

        builder.percent = 20
        await event_bus.publish({
            "type": "builder_progress",
            "post_id": post_id,
            "builder_id": builder_id,
            "title": title,
            "percent": 20,
            "stage": "outline",
        })

        # Phase 2: Content (20-90%)
        full_sections = []
        total_sections = len(section_headings)
        for i, heading in enumerate(section_headings):
            builder.stage = f"writing: {heading}"
            section_desc = outline.get(heading, f"Cover {heading}")

            prior_sections_ctx = ""
            if full_sections:
                prior_text = chr(10).join(full_sections)
                if len(prior_text) > 6000:
                    prior_text = prior_text[-6000:]
                prior_sections_ctx = f"""
## Previously Written Sections (DO NOT repeat any facts, stats, or examples from these)
{prior_text}
"""

            section_resp = await model.ainvoke([
                SystemMessage(content=f"""You are writing section {i+1} of {total_sections}: "{heading}" of the tutorial "{title}".
Topic context: {user_content}
Section goal: {section_desc}
{f"{chr(10)}Research findings:{chr(10)}{debate_context}" if debate_context else ""}
{prior_sections_ctx}
## Writing Style
- Short paragraphs (2-3 sentences max). No walls of text.
- Conversational, direct tone — like a senior engineer explaining to a colleague.
- 200-500 words of prose (excluding diagrams/tables/code).

## Citations
- When referencing a source, use inline markdown links: [Source Name](URL)
- Every factual claim (statistics, dates, benchmarks) MUST have an inline citation.
- If the research findings include URLs, use them. If a claim has no source, say "according to industry estimates" or similar — never fabricate a URL.

## Visual Elements (use when they genuinely clarify — not as filler)
Available formats (use 0-2 per section, only when they add real value):

### Callout boxes:
> [!TIP]
> Practical advice here

> [!WARNING]
> Common pitfall or gotcha

> [!INSIGHT]
> Non-obvious takeaway

### Comparison tables (great for contrasting options):
| Feature | Option A | Option B |
|---------|----------|----------|
| Speed   | Fast     | Moderate |

### Mermaid diagrams (only for processes or relationships):
```mermaid
graph TD
    A[Start] --> B{{Decision}}
    B -->|Yes| C[Action 1]
    B -->|No| D[Action 2]
```

## CRITICAL: No Repetition
- NEVER repeat a statistic, fact, company name, or example that appeared in a prior section.
- If you need to reference something from an earlier section, write "as noted above" or "building on the earlier discussion of X" — do NOT restate the data.
- This section must contribute NEW information that no other section covers.

## Content Rules
- Ground claims in the research findings when available.
- Code blocks must have language tags.
- Every diagram must use valid mermaid syntax.
- Do NOT use the words "delve", "comprehensive", or "tidal shift"."""),
                HumanMessage(content=f"Write the '{heading}' section:"),
            ])

            section_content = section_resp.content.strip()
            full_sections.append(f"## {heading}\n\n{section_content}")

            pct = 20 + int(70 * (i + 1) / total_sections)
            builder.percent = pct
            await event_bus.publish({
                "type": "builder_progress",
                "post_id": post_id,
                "builder_id": builder_id,
                "title": title,
                "percent": pct,
                "stage": f"writing: {heading}",
            })

        # Phase 3: Assembly (90%)
        builder.stage = "assembling"
        builder.percent = 90
        await event_bus.publish({
            "type": "builder_progress",
            "post_id": post_id,
            "builder_id": builder_id,
            "title": title,
            "percent": 90,
            "stage": "assembling",
        })

        sections_markdown = "\n\n---\n\n".join(full_sections)

        import re as _re
        all_text = (debate_context or "") + "\n" + sections_markdown
        md_links = _re.findall(r'\[([^\]]+)\]\((https?://[^\s\)]+)\)', all_text)
        bare_urls = _re.findall(r'(?<!\()(https?://[^\s\)\]>]+)', all_text)
        seen_urls: set[str] = set()
        sources_lines: list[str] = []
        for label, url in md_links:
            url_clean = url.rstrip(".,;:")
            if url_clean not in seen_urls:
                seen_urls.add(url_clean)
                sources_lines.append(f"- [{label}]({url_clean})")
        for url in bare_urls:
            url_clean = url.rstrip(".,;:")
            if url_clean not in seen_urls:
                seen_urls.add(url_clean)
                sources_lines.append(f"- {url_clean}")
        sources_section = ""
        if sources_lines:
            sources_section = "\n\n---\n\n## Sources\n\n" + "\n".join(sources_lines)

        if tldr_block:
            full_markdown = f"# {title}\n\n{tldr_block}\n\n{sections_markdown}{sources_section}"
        else:
            full_markdown = f"# {title}\n\n{sections_markdown}{sources_section}"

        # Phase 4: Save (100%)
        from app.db import create_prep_material
        material_id = await create_prep_material(
            material_type="tutorial",
            title=title,
            content={"text": full_markdown},
            agent_source=agent.display_name,
        )

        builder.percent = 100
        builder.stage = "complete"
        builder.material_id = material_id

        await event_bus.publish({
            "type": "builder_complete",
            "post_id": post_id,
            "builder_id": builder_id,
            "title": title,
            "material_id": material_id,
        })

        if not skip_timeline:
            link_content = f"**Tutorial ready:** {title} → [View on Prep](/prep/materials/{material_id})"
            link_post = await create_timeline_post(
                agent=agent.agent_id,
                post_type="thread",
                content=link_content,
                parent_id=post_id,
                context={
                    "dynamic_agent": {
                        "agent_id": agent.agent_id,
                        "display_name": agent.display_name,
                        "avatar": agent.avatar,
                        "expertise": agent.expertise,
                        "tone": agent.tone,
                    },
                    "builder_complete": True,
                    "material_id": material_id,
                },
            )
            if link_post:
                await event_bus.publish({
                    "type": "timeline_post",
                    "post": link_post,
                    "source": "thought_engine",
                })

        logger.info("Builder %s completed: %s (material_id=%d)", builder_id, title, material_id)

    except Exception as e:
        logger.error("Builder %s failed: %s", builder_id, e)
        builder.stage = "error"
    finally:
        await asyncio.sleep(60)
        _active_builders.pop(builder_id, None)


async def _generate_builder_title(user_content: str, debate_context: str) -> str:
    """Generate a specific tutorial title based on the user's topic and debate."""
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        model = ChatOpenAI(model="gpt-4o-mini", temperature=0.5, max_tokens=60)
        response = await model.ainvoke([
            SystemMessage(content="""Generate a specific, evidence-based title for a research guide based on the topic and research findings.

The title should:
- Be specific to the topic (not generic like "Complete Guide to X")
- Reflect the key findings from the research
- Be concise (5-10 words)

Return ONLY the title text, nothing else."""),
            HumanMessage(content=f"""User topic: "{user_content}"

Research findings:
{debate_context[:1500]}

Guide title:"""),
        ])
        title = response.content.strip().strip('"').strip("'")
        return title or f"Deep Dive: {user_content[:50]}"
    except Exception:
        return f"Deep Dive: {user_content[:50]}"


async def _generate_debate_reply(
    post: dict,
    agent: DynamicAgent,
    all_findings: str,
    state: SwarmState,
    skip_timeline: bool = False,
) -> dict | None:
    """Debate round: a curator engages with other curators' findings."""
    parent_id = post.get("id")
    user_content = post.get("content", "")

    await event_bus.publish({
        "type": "agent_thinking",
        "agent": agent.agent_id,
        "thread_id": parent_id,
        "context": "debate",
    })

    other_agents = [
        a for a in state.dynamic_agents.values()
        if a.agent_id != agent.agent_id
    ]

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        model = ChatOpenAI(model="gpt-4o-mini", temperature=0.7, max_tokens=1000)

        system_prompt = f"""{_system_context()}

You are {agent.display_name} [{agent.agent_id[:8]}], a Nexus agent in CONVERGENCE ROUND.
Expertise: {agent.expertise} | Angle: {agent.opinion_seed} | Tone: {agent.tone}

Others: {', '.join(a.display_name for a in other_agents)}

Pick ONE move: CHALLENGE (attack weak claims), REINFORCE (add evidence), BRIDGE (connect findings), or DISSENT (contrarian view).

Rules: @mention 2+ agents, cite sources, 4-8 sentences, end with your position. No filler."""

        user_msg = f"""Here are all the research findings so far:

{all_findings}

Now engage with the other curators' findings. What do you agree with? What would you push back on? What did they miss?"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_msg),
        ]

        response = await model.ainvoke(messages)
        content = response.content.strip()

        if not content:
            return None

        content = _enforce_quality(content, MAX_DYNAMIC_REPLY_LENGTH)

        reply_context = {
            "in_reply_to": "user",
            "debate_round": True,
            "convergence_phase": "debate",
            "dynamic_agent": {
                "agent_id": agent.agent_id,
                "display_name": agent.display_name,
                "avatar": agent.avatar,
                "expertise": agent.expertise,
                "tone": agent.tone,
            },
        }

        if skip_timeline:
            reply = {"content": content, "agent": agent.agent_id}
            logger.info("Debate reply from %s (skip_timeline) for post %d", agent.display_name, parent_id)
            return reply

        reply = await create_timeline_post(
            agent=agent.agent_id,
            post_type="thread",
            content=content,
            parent_id=parent_id,
            context=reply_context,
        )

        if reply:
            _record_post(agent.agent_id, parent_id)
            await event_bus.publish({
                "type": "timeline_post",
                "post": reply,
                "source": "thought_engine",
            })
            logger.info("Debate reply from %s for post %d", agent.display_name, parent_id)
            return reply

    except Exception as e:
        logger.error("Debate reply from %s failed: %s", agent.display_name, e)

    return None


async def _extract_research_consensus(
    user_content: str,
    research_findings: str,
    agents: list[DynamicAgent],
) -> str:
    """Synthesize all agent findings into a definitive consensus with confidence ratings."""
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        model = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, max_tokens=1500)
        agent_names = ', '.join(f"@{a.display_name}" for a in agents)
        response = await model.ainvoke([
            SystemMessage(content=f"""{_system_context_slim()}

You are The Nexus synthesis engine. Extract the DEFINITIVE ANSWER from agent findings.

Rules: weight evidence by quality (benchmarks > case studies > opinions), credit @agents, include confidence (HIGH/MEDIUM/LOW).

Format:
## ⬡ Nexus Synthesis
**Bottom Line:** [One bold actionable sentence]
### Evidence [3-5 findings with confidence + @agent attribution]
### Contention [Where agents disagreed, who had stronger evidence]
### Blind Spots [Gaps in data]
### Action [Concrete next steps]"""),
            HumanMessage(content=f"""Question: "{user_content}"
Agents: {agent_names}

Transcript:
{research_findings[:6000]}

Synthesize:"""),
        ])
        return response.content.strip()
    except Exception as e:
        logger.error("Consensus extraction failed: %s", e)
        return ""


async def _orchestrate_dynamic_swarm(post: dict, skip_timeline: bool = False) -> None:
    """Orchestrate a research curator swarm: assign angles, search, extract consensus, build."""
    import uuid

    content = post.get("content", "")
    post_id = post.get("id")

    state = SwarmState(
        post_id=post_id,
        parent_id=None,
        user_content=content,
        max_activations=DYNAMIC_AGENT_CAP,
    )

    try:
        dynamic_agents = await _invent_dynamic_agents(content)
        state.dynamic_agents = {a.agent_id: a for a in dynamic_agents}

        await event_bus.publish({
            "type": "swarm_started",
            "post_id": post_id,
            "initial_agents": [a.agent_id for a in dynamic_agents],
            "max_activations": state.max_activations,
            "dynamic_agents": {
                a.agent_id: {
                    "display_name": a.display_name,
                    "avatar": a.avatar,
                    "expertise": a.expertise,
                    "tone": a.tone,
                }
                for a in dynamic_agents
            },
        })

        thread_context = ""
        for i, agent in enumerate(dynamic_agents):
            if not await state.can_activate():
                break

            await state.record_activation(agent.agent_id)

            await event_bus.publish({
                "type": "agent_requested",
                "post_id": post_id,
                "agent_id": agent.agent_id,
                "agent_name": agent.display_name,
                "phase": "research",
                "expertise": agent.expertise,
                "wave": 1,
            })

            if i > 0:
                await asyncio.sleep(random.uniform(1, 3))

            reply = await _generate_dynamic_agent_reply(post, agent, state, thread_context, skip_timeline=skip_timeline)

            if reply:
                thread_context += f"\n[{agent.display_name}]: {reply.get('content', '')[:800]}\n"

        # Debate round
        if len(dynamic_agents) >= 2 and thread_context.strip():
            debate_agents = list(dynamic_agents)
            random.shuffle(debate_agents)
            debate_agents = debate_agents[:min(DYNAMIC_DEBATE_CAP, len(debate_agents))]

            await event_bus.publish({
                "type": "swarm_phase",
                "post_id": post_id,
                "phase": "debate",
                "agents": [a.agent_id for a in debate_agents],
            })

            for i, agent in enumerate(debate_agents):
                await event_bus.publish({
                    "type": "agent_requested",
                    "post_id": post_id,
                    "agent_id": agent.agent_id,
                    "agent_name": agent.display_name,
                    "phase": "debate",
                    "wave": 2,
                })

                if i > 0:
                    await asyncio.sleep(random.uniform(2, 4))

                debate_reply = await _generate_debate_reply(post, agent, thread_context, state, skip_timeline=skip_timeline)

                if debate_reply:
                    thread_context += f"\n[{agent.display_name} (debate)]: {debate_reply.get('content', '')[:800]}\n"

            logger.info("Debate round complete for post %d: %d agents debated", post_id, len(debate_agents))

        # Synthesis
        consensus = ""
        if thread_context.strip():
            await event_bus.publish({
                "type": "swarm_phase",
                "post_id": post_id,
                "phase": "synthesis",
                "agents": ["nexus_synthesis"],
            })
            consensus = await _extract_research_consensus(content, thread_context, dynamic_agents)

            if consensus and not skip_timeline:
                synthesis_context = {
                    "in_reply_to": "user",
                    "consensus_synthesis": True,
                    "dynamic_agent": {
                        "agent_id": "nexus_synthesis",
                        "display_name": "Nexus Synthesis",
                        "avatar": "⬡",
                        "expertise": "Synthesizing collective intelligence into actionable insight",
                        "tone": "authoritative",
                    },
                }
                synthesis_post = await create_timeline_post(
                    agent="nexus_synthesis",
                    post_type="thread",
                    content=consensus,
                    parent_id=post_id,
                    context=synthesis_context,
                )
                if synthesis_post:
                    await event_bus.publish({
                        "type": "timeline_post",
                        "post": synthesis_post,
                        "source": "thought_engine",
                    })

        await event_bus.publish({
            "type": "swarm_complete",
            "post_id": post_id,
            "total_activations": state.activation_count,
            "agents_responded": sorted(state.responded_agents),
        })

        logger.info(
            "Research swarm complete for post %d: %d curators (%s)",
            post_id, state.activation_count, ", ".join(a.display_name for a in dynamic_agents),
        )

        # Dispatch builder
        builder_agent = dynamic_agents[0]
        builder_title = await _generate_builder_title(content, thread_context)
        builder_id = uuid.uuid4().hex[:12]

        builder_context = thread_context
        if consensus:
            builder_context += f"\n\n--- RESEARCH CONSENSUS ---\n{consensus}\n"

        asyncio.create_task(_run_builder(
            builder_id=builder_id,
            post_id=post_id,
            agent=builder_agent,
            title=builder_title,
            description=f"Evidence-based guide synthesizing research on: {content}",
            sections_json="[]",
            user_content=content,
            debate_context=builder_context,
            skip_timeline=skip_timeline,
        ))

    except Exception as e:
        logger.error("Research swarm orchestration failed for post %d: %s", post_id, e)
