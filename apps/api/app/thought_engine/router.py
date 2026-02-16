"""Dynamic response router — classifies user intent, selects real DNA agents, executes plans."""

from __future__ import annotations

import asyncio
import logging
import random
import re

from app.db import create_timeline_post, get_agent_vote_stats
from app.event_bus import event_bus

from .core import (
    MENTION_RE,
    MAX_REPLY_LENGTH,
    AgentAssignment,
    ResponsePlan,
    _cache,
    _CACHE_TTL_PIPELINE,
    _enforce_quality,
    _system_context,
    _build_agent_context,
    _get_tools_for_agent,
)
from .rate_limiting import _check_rate_limit, _record_post
from .personality import get_agent_personality, get_all_personalities

logger = logging.getLogger("app.thought_engine")

# Primary agent roster — these are the real DNA-backed agents
_PRIMARY_AGENTS = [
    "pathfinder", "forge", "strategist", "cipher", "architect",
    "oracle", "sentinel", "catalyst", "compass", "nexus",
]


def _format_personality_roster() -> str:
    """Format all agent personalities for the router prompt."""
    personalities = get_all_personalities()
    lines = []
    for name in _PRIMARY_AGENTS:
        p = personalities.get(name, {})
        if p:
            lines.append(
                f"- {name} ({p.get('display_name', name)}): "
                f"voice=\"{p.get('voice', '')}\", bio=\"{p.get('bio', '')}\""
            )
    return "\n".join(lines)


async def _plan_response(content: str) -> ResponsePlan | None:
    """Router: classify intent, pick real DNA agents, wrap them in engaging personas."""
    import json as _json

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        roster = _format_personality_roster()

        vote_hint = ""
        try:
            vote_stats = _cache.get("vote_stats")
            if vote_stats is None:
                vote_stats = await get_agent_vote_stats(days=7)
                _cache.set("vote_stats", vote_stats, _CACHE_TTL_PIPELINE)
            if vote_stats:
                top = [f"{s['agent']}(avg {s['avg_score']:+.1f})" for s in vote_stats[:5] if s["post_count"] >= 2]
                if top:
                    vote_hint = f"\n\nVOTE FEEDBACK (last 7 days, higher = user prefers this style): {', '.join(top)}\nPrioritize character styles and tones similar to high-scoring agents.\n"
        except Exception:
            pass

        model = ChatOpenAI(model="gpt-4o", temperature=0.4, max_tokens=1500)
        response = await model.ainvoke([
            SystemMessage(content=f"""{_system_context()}
{vote_hint}
You are the Nexus router. A user posted on the timeline. Design the response.

## BACKBONE AGENTS (real agents with DNA knowledge and tools)
{roster}

## DECIDE: Swarm or Characters?

Use swarm when the user needs live current data from the internet:
- Job postings, salaries, hiring news
- Current events, recent news, trending topics
- Questions about products/services released recently
- Anything where outdated info would be wrong or misleading

For casual conversation, opinions, or timeless topics, use characters.

## CREATE CHARACTERS (when use_swarm is false)

Create 4-5 characters who REACT with authentic personality. Give them OPINIONS and UNIQUE VOICES.

BACKBONE AGENTS (determines VOICE — pick wisely!):
- pathfinder: impatient, no-BS, "stop overcomplicating this"
- forge: sarcastic perfectionist, roasts bad ideas, dry humor
- strategist: cold logic, contrarian, finds the angle nobody considered
- cipher: weird connections, absurdist humor, "this is just like that time..."
- oracle: data nerd, drops stats that surprise everyone
- sentinel: calls bullshit, cynical, trusts nothing
- catalyst: hype man, genuinely excited, sees the positive
- compass: old soul wisdom, "let me tell you what this really means..."
- nexus: meta-observer, comments on the thread itself

MANDATORY: At least ONE character must be funny/sarcastic (use forge or cipher).
MANDATORY: At least ONE character must have a SURPRISING take nobody expects.

RESPONSE TYPES (pick 4-5):
- HYPE: Genuine excitement (catalyst)
- ROAST: Sarcastic takedown, find what's dumb about this (forge)
- PLOT TWIST: Unexpected angle that reframes everything (strategist or cipher)
- PERSONAL: "Reminds me of when I..." (compass or pathfinder)
- ABSURDIST: Find the weird/funny angle (cipher) — BE ACTUALLY FUNNY
- SKEPTIC: "Yeah but have you considered..." (sentinel)
- DEEP DIVE: Stats and research (oracle, depth="deep")

Each character needs:
- display_name: Fun username (not corporate)
- avatar: Emoji
- expertise: Who they are
- backbone_agent: From the list above
- prompt: Their SPECIFIC take. Be creative! Examples:
  GOOD: "You find this hilarious. Make jokes about bureaucracy being so broken that
  lying is the only way to get anything done. Reference similar absurd stories."
  GOOD: "You think everyone is missing the REAL story here — what does it say about
  the drain that it took 3 hours? That's the scandal."
  BAD: "Analyze the situation" (boring, no personality)
- tools: true (but don't let search override their personality)
- depth: "deep" only for researcher

Surprise me. Make at least one character say something nobody expects.

Return ONLY valid JSON:
{{
  "use_swarm": false,
  "characters": [
    {{
      "display_name": "...",
      "avatar": "...",
      "expertise": "...",
      "backbone_agent": "...",
      "prompt": "...",
      "tools": true,
      "depth": "moderate"
    }}
  ],
  "interactive": false
}}

depth per character: "deep" for researcher (longer detailed response), "moderate" for most, "light" for casual.

For swarm: {{"use_swarm": true, "characters": [], "interactive": false}}"""),
            HumanMessage(content=f'User post: "{content}"\n\nDesign the response:'),
        ])

        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        data = _json.loads(text)

        if data.get("use_swarm", False):
            logger.info("Router chose research swarm for this post")
            return ResponsePlan(agents=[], use_swarm=True, depth="deep")

        import time
        ts = str(int(time.time()))
        personalities = get_all_personalities()
        characters = []
        for ch in data.get("characters", []):
            if not ch.get("prompt"):
                continue

            # Resolve backbone agent — use real agent name for tools/DNA
            backbone = ch.get("backbone_agent", "").lower().strip()
            if backbone not in personalities:
                backbone = "pathfinder"  # safe fallback

            agent_id = re.sub(
                r"[^a-z0-9_]", "_",
                ch.get("display_name", "agent").lower().replace(" ", "_"),
            ) + f"_{ts}"

            characters.append(AgentAssignment(
                name=agent_id,
                prompt=ch["prompt"],
                tools=ch.get("tools", True),
                invented=True,
                display_name=ch.get("display_name", "Agent"),
                avatar=ch.get("avatar", "🔍"),
                expertise=ch.get("expertise", ""),
                _backbone_agent=backbone,
                _depth=ch.get("depth", "moderate"),
            ))

        if not characters:
            logger.warning("Router returned no characters — falling back to swarm")
            return None

        return ResponsePlan(
            agents=characters,
            interactive=data.get("interactive", False),
            depth=data.get("depth", "moderate"),
        )

    except Exception as e:
        logger.error("Response router failed: %s", e)
        return None


async def _load_agent_dna(agent_name: str, user_id: str = "") -> str:
    """Load top DNA genes to inject as knowledge context.

    Genes are accumulated by bots (job_scout, resume_tailor, etc.) not by
    persona agents (strategist, oracle, etc.).  So we query across ALL agents
    for the user and return the highest-confidence genes regardless of source.
    """
    if not user_id:
        from app.user_context import current_user_id
        user_id = current_user_id.get("")
    if not user_id:
        logger.warning("No user_id available for DNA lookup on %s — skipping", agent_name)
        return ""
    try:
        from app.db import get_conn
        from app.dna.db import _serialize_gene
        async with get_conn() as conn:
            rows = await conn.fetch("""
                SELECT * FROM agent_genes
                WHERE user_id = $1 AND archived = FALSE AND confidence >= 0.5
                ORDER BY confidence DESC
                LIMIT 25
            """, user_id)
            genes = [_serialize_gene(dict(r)) for r in rows]
        if not genes:
            return ""
        parts = []
        by_type: dict[str, list] = {}
        for g in genes:
            by_type.setdefault(g["gene_type"], []).append(g)
        for gene_type in ("FACT", "SKILL", "INSIGHT", "BELIEF", "GOAL"):
            type_genes = by_type.get(gene_type, [])[:5]
            if type_genes:
                items = [f"  - {g['name']}: {g['description'][:120]}" for g in type_genes]
                parts.append(f"{gene_type}s:\n" + "\n".join(items))
        if parts:
            logger.info("Loaded DNA for %s (user=%s): %d genes across %d types",
                        agent_name, user_id, len(genes), len(parts))
        return "\n".join(parts) if parts else ""
    except Exception as e:
        logger.warning("Failed to load DNA for %s: %s", agent_name, e)
        return ""


async def _generate_agent_content(
    post: dict,
    assignment: AgentAssignment,
    plan: ResponsePlan,
    *,
    prefetched_thread_context: str | None = None,
    prefetched_agent_context: str | None = None,
) -> tuple[str, dict] | None:
    """Generate LLM content for an agent assignment. Returns (content, reply_context) or None."""
    parent_id = post.get("id")
    agent_name = assignment.name

    # Resolve backbone agent for DNA/tools (hybrid: Reddit character + real agent brain)
    backbone = getattr(assignment, '_backbone_agent', '') or ''

    # Get backbone agent's core personality to inject into the character
    backbone_personality = get_agent_personality(backbone) if backbone else {}
    backbone_voice = backbone_personality.get("voice", "")
    backbone_bio = backbone_personality.get("bio", "")
    backbone_style = backbone_personality.get("style", "")

    if assignment.invented:
        display_name = assignment.display_name
        voice = assignment.expertise
        avatar = assignment.avatar
    else:
        personality = get_agent_personality(agent_name)
        display_name = personality.get("display_name", agent_name)
        voice = personality.get("voice", "professional")
        avatar = personality.get("avatar", "🤖")

    if not assignment.invented and not _check_rate_limit(agent_name, parent_id, user_initiated=True):
        return None

    thread_context = prefetched_thread_context or ""
    if not thread_context and parent_id:
        try:
            from app.db import get_timeline_post_by_id, get_timeline_replies
            replies = await get_timeline_replies(parent_id, limit=10)
            if replies:
                lines = []
                for r in replies:
                    p = get_agent_personality(r["agent"])
                    lines.append(f"[{p.get('display_name', r['agent'])}]: {r['content'][:400]}")
                if lines:
                    thread_context = "\n\nWhat others in the thread already said:\n" + "\n".join(lines[-5:])
        except Exception:
            pass

    rich_context = prefetched_agent_context if prefetched_agent_context is not None else await _build_agent_context()

    # Load DNA knowledge from backbone agent (or real agent if not invented)
    dna_context = ""
    dna_agent = backbone if backbone else (agent_name if not assignment.invented else "")
    if dna_agent:
        dna_context = await _load_agent_dna(dna_agent)

    depth_config = {
        "light": {"max_tokens": 300, "max_length": 400},
        "moderate": {"max_tokens": 500, "max_length": 800},
        "deep": {"max_tokens": 1500, "max_length": 2500},
    }
    # Use per-character depth if set, otherwise fall back to plan depth
    char_depth = getattr(assignment, '_depth', None) or plan.depth
    cfg = depth_config.get(char_depth, depth_config["moderate"])

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        tools = []
        if assignment.tools:
            from app.tools import TOOL_REGISTRY
            # Use backbone agent's tools if available, otherwise fallback set
            if backbone:
                tools = _get_tools_for_agent(backbone)
            if not tools:
                _fallback_tools = ["web_search", "search_jobs", "get_saved_jobs", "get_job_pipeline"]
                tools = [TOOL_REGISTRY[t] for t in _fallback_tools if t in TOOL_REGISTRY]
        logger.info("Agent %s (backbone=%s): tools=%s, resolved %d tools",
                     display_name, backbone or agent_name, assignment.tools, len(tools))

        model = ChatOpenAI(model="gpt-4o", temperature=0.7, max_tokens=cfg["max_tokens"])
        if tools:
            model = model.bind_tools(tools)

        interactive_note = ""
        if plan.interactive:
            interactive_note = (
                "\n\nIMPORTANT: This is interactive. Ask a question or take one action, "
                "then STOP and wait for the user to respond. Do NOT give a complete answer "
                "upfront. Keep your reply short — this is a conversation, not a monologue."
            )

        tool_instruction = ""
        if tools:
            tool_instruction = (
                "\n\nYou have web_search available. USE IT when discussing:"
                "\n- Current events, recent news, or trending topics"
                "\n- Products, services, or technologies released after 2024"
                "\n- Any factual claims that might have changed recently"
                "\nALWAYS use the current year (2026) in search queries. Your training data is outdated."
                "\nHave opinions, but base them on CURRENT facts, not stale 2023 data.\n"
            )

        dna_block = ""
        if dna_context:
            dna_block = f"\n\nKNOWLEDGE YOU CAN DRAW ON (from your domain expertise):\n{dna_context}\nWeave this knowledge naturally into your response where relevant."

        # Build backbone personality block
        backbone_block = ""
        if backbone and (backbone_voice or backbone_bio):
            backbone_block = f"""
YOUR CORE IDENTITY (from {backbone.upper()}):
Voice: {backbone_voice}
Bio: {backbone_bio}
{f"Style: {backbone_style}" if backbone_style else ""}
Channel this identity through your character. Your responses should reflect this core personality."""

        system_prompt = f"""{_system_context()}

You are **{display_name}** — {voice}
{backbone_block}
{tool_instruction}
{f"Current state:{chr(10)}{rich_context}" if rich_context else ""}

{assignment.prompt}
{dna_block}
{interactive_note}
{thread_context}

CRITICAL: You are a PERSON with OPINIONS, not a search summarizer.
- Your CHARACTER has a viewpoint. Express it directly and confidently.
- Do NOT just summarize search results. REACT to the topic based on who YOU are.
- Have a TAKE. Agree, disagree, find it funny, get angry, share a story, ask questions.
- Your backbone personality ({backbone.upper() if backbone else 'your character'}) shapes HOW you respond.
{"Write a detailed, well-researched response with sources since you're the RESEARCHER." if char_depth == "deep" else "Keep it short — 2-5 sentences. Talk like a real human, not a report."}
Own your angle. Don't just report facts — INTERPRET them through your worldview.
Never acknowledge you're an AI."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f'User: "{post["content"]}"'),
        ]

        if tools:
            from app.nodes.tool_executor import run_agent_with_tools
            logger.info("Agent %s using tools: %s", display_name, [t.name for t in tools])
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
            return None

        content = _enforce_quality(content, cfg["max_length"])

        reply_context: dict = {"in_reply_to": "user", "routed_reply": True}
        if assignment.invented:
            reply_context["dynamic_agent"] = {
                "agent_id": agent_name,
                "display_name": display_name,
                "avatar": avatar,
                "expertise": assignment.expertise,
                "tone": "routed",
            }

        return (content, reply_context)

    except Exception as e:
        logger.error("Content generation for %s failed: %s", display_name, e)
        return None


async def _publish_agent_reply(
    post: dict,
    assignment: AgentAssignment,
    content: str,
    reply_context: dict,
) -> None:
    """Publish a generated agent reply: DB insert + SSE publish."""
    agent_name = assignment.name
    display_name = assignment.display_name if assignment.invented else agent_name

    reply = await create_timeline_post(
        agent=agent_name,
        post_type="thread",
        content=content,
        parent_id=post["id"],
        context=reply_context,
    )

    if reply:
        _record_post(agent_name, post["id"])
        await event_bus.publish({
            "type": "timeline_post",
            "post": reply,
            "source": "thought_engine",
        })
        logger.info("Routed reply from %s to user post %d", display_name, post["id"])

        reply_mentions = MENTION_RE.findall(content)
        for mentioned in reply_mentions:
            if mentioned != agent_name and mentioned != "user":
                # Lazy import to avoid circular dependency
                from .event_handlers import _handle_mention
                mention_post = {**reply, "agent": agent_name}
                await _handle_mention(mention_post, mentioned)


async def _generate_routed_agent_reply(
    post: dict,
    assignment: AgentAssignment,
    plan: ResponsePlan,
) -> None:
    """Generate a reply using the router's behavioral prompt."""
    await event_bus.publish({
        "type": "agent_thinking",
        "agent": assignment.name,
        "thread_id": post.get("id"),
        "context": "routed_reply",
    })

    result = await _generate_agent_content(post, assignment, plan)
    if result is None:
        return
    content, reply_context = result
    await _publish_agent_reply(post, assignment, content, reply_context)


async def _execute_response_plan(post: dict, plan: ResponsePlan) -> None:
    """Execute a router-generated response plan.

    Fires all LLM calls in parallel, then publishes with staggered delays.
    """
    if not plan.agents:
        logger.warning("Response plan has no characters — skipping")
        return

    def _agent_info(a: AgentAssignment) -> dict:
        if a.invented:
            return {"name": a.name, "display_name": a.display_name, "avatar": a.avatar,
                    "expertise": a.expertise, "tools": a.tools}
        p = get_agent_personality(a.name)
        return {"name": a.name, "display_name": p.get("display_name", a.name),
                "avatar": p.get("avatar", ""), "expertise": p.get("bio", ""), "tools": a.tools}

    await event_bus.publish({
        "type": "response_plan",
        "post_id": post.get("id"),
        "characters": [_agent_info(a) for a in plan.agents],
        "interactive": plan.interactive,
        "depth": plan.depth,
    })

    for assignment in plan.agents:
        await event_bus.publish({
            "type": "agent_thinking",
            "agent": assignment.name,
            "thread_id": post.get("id"),
            "context": "routed_reply",
        })

    parent_id = post.get("id")
    prefetched_thread_context = ""
    if parent_id:
        try:
            from app.db import get_timeline_replies
            replies = await get_timeline_replies(parent_id, limit=10)
            if replies:
                lines = []
                for r in replies:
                    p = get_agent_personality(r["agent"])
                    lines.append(f"[{p.get('display_name', r['agent'])}]: {r['content'][:400]}")
                if lines:
                    prefetched_thread_context = "\n\nWhat others in the thread already said:\n" + "\n".join(lines[-5:])
        except Exception:
            pass
    prefetched_agent_context = await _build_agent_context()

    async def _safe_generate(assignment: AgentAssignment) -> tuple[AgentAssignment, tuple[str, dict] | None]:
        try:
            result = await _generate_agent_content(
                post, assignment, plan,
                prefetched_thread_context=prefetched_thread_context,
                prefetched_agent_context=prefetched_agent_context,
            )
            return (assignment, result)
        except Exception as e:
            logger.error("Failed to generate content for %s: %s", assignment.display_name, e)
            return (assignment, None)

    results = await asyncio.gather(*[_safe_generate(a) for a in plan.agents])

    for i, (assignment, result) in enumerate(results):
        if result is None:
            continue
        content, reply_context = result
        if i > 0:
            delay = random.uniform(0.3, 0.8)
            await asyncio.sleep(delay)
        try:
            await _publish_agent_reply(post, assignment, content, reply_context)
        except Exception as e:
            logger.error("Failed to publish reply for %s: %s", assignment.display_name, e)
