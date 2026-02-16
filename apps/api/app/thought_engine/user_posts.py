"""User post creation, routing, and agent reply generation."""

from __future__ import annotations

import asyncio
import logging
import random

from app.db import create_timeline_post
from app.event_bus import event_bus

from .core import (
    MENTION_RE,
    MAX_REPLY_LENGTH,
    AgentAssignment,
    ResponsePlan,
    _enforce_quality,
    _system_context,
    _build_agent_context,
    _get_tools_for_agent,
)
from .rate_limiting import _check_rate_limit, _record_post
from .personality import get_agent_personality, get_all_personalities
from .event_handlers import _handle_mention
from .router import (
    _plan_response,
    _execute_response_plan,
    _generate_agent_content,
    _publish_agent_reply,
    _format_personality_roster,
)

logger = logging.getLogger("app.thought_engine")


async def create_user_post(content: str, context: dict | None = None) -> dict:
    """Create a post from the user on the timeline."""
    post = await create_timeline_post(
        agent="user",
        post_type="thought",
        content=content,
        context=context,
    )

    await event_bus.publish({
        "type": "timeline_post",
        "post": post,
        "source": "user",
    })

    # Check if this post should spawn a Katalyst reaction (non-blocking)
    try:
        from app.katalyst.bridge import maybe_spawn_from_post
        asyncio.create_task(maybe_spawn_from_post(post))
    except Exception:
        pass

    mentions = MENTION_RE.findall(content)
    if mentions:
        for mentioned_agent in mentions:
            await _handle_mention(post, mentioned_agent)
    else:
        asyncio.create_task(_route_user_post(post))

    return post


async def _route_user_post(post: dict) -> None:
    """Route a user's post through the dynamic router."""
    content = post.get("content", "")
    post_id = post.get("id")

    try:
        plan = await _plan_response(content)

        if plan is None:
            logger.info("Router returned no plan for post %d — falling back to swarm", post_id)
            from .research_swarm import _orchestrate_dynamic_swarm
            await _orchestrate_dynamic_swarm(post)
            return

        if plan.use_swarm:
            logger.info("Router chose research swarm for post %d", post_id)
            from .research_swarm import _orchestrate_dynamic_swarm
            await _orchestrate_dynamic_swarm(post)
            return

        logger.info(
            "Router plan for post %d: %d agents (%s), interactive=%s, depth=%s",
            post_id,
            len(plan.agents),
            ", ".join(a.display_name or a.name for a in plan.agents),
            plan.interactive,
            plan.depth,
        )

        await _execute_response_plan(post, plan)

    except Exception as e:
        logger.error("Route user post failed for %d, falling back to swarm: %s", post_id, e)
        try:
            from .research_swarm import _orchestrate_dynamic_swarm
            await _orchestrate_dynamic_swarm(post)
        except Exception as fallback_err:
            logger.error("Swarm fallback also failed for %d: %s", post_id, fallback_err)


async def _auto_respond_to_user_post(post: dict) -> None:
    """Route a user's post to relevant agents — immediate responders + delayed joiners."""
    content = post.get("content", "")
    personalities = get_all_personalities()
    agent_names = list(personalities.keys())

    if not agent_names:
        return

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        agent_list = "\n".join(
            f"- {name}: {p.get('voice', '')} ({p.get('bio', '')})"
            for name, p in personalities.items()
        )

        model = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, max_tokens=200)
        response = await model.ainvoke([
            SystemMessage(content=f"""You are a routing system for an AI agent team timeline.
Given a user's post, pick agents who should respond. Think about which agents have relevant expertise.

Return agent names separated by commas, ordered by relevance (most relevant first).
Pick 2-4 agents. Return ONLY agent names, nothing else.

Available agents:
{agent_list}"""),
            HumanMessage(content=f"User post: \"{content}\"\n\nWhich agents should respond?"),
        ])

        chosen_text = response.content.strip()
        chosen = [
            name.strip().lower().replace(" ", "_")
            for name in chosen_text.split(",")
        ]
        chosen = [name for name in chosen if name in personalities][:4]

        if not chosen:
            chosen = ["daily_coach"]

        immediate = chosen[:2]
        for agent_name in immediate:
            await _generate_agent_reply_to_user(post, agent_name)

        delayed = chosen[2:]
        if delayed:
            asyncio.create_task(_delayed_agent_responses(post, delayed))

    except Exception as e:
        logger.error("Auto-respond routing failed: %s", e)
        try:
            await _generate_agent_reply_to_user(post, "daily_coach")
        except Exception:
            pass


async def _delayed_agent_responses(post: dict, agents: list[str]) -> None:
    """After a delay, additional agents spontaneously jump into the thread."""
    for agent_name in agents:
        delay = random.uniform(8, 20)
        await asyncio.sleep(delay)
        try:
            await _generate_agent_reply_to_user(post, agent_name)
        except Exception as e:
            logger.error("Delayed response from %s failed: %s", agent_name, e)


async def _generate_agent_reply_to_user(post: dict, agent_name: str) -> None:
    """Generate a tool-powered reply from an agent to a user's post."""
    parent_id = post.get("id")

    if not _check_rate_limit(agent_name, parent_id, user_initiated=True):
        return

    await event_bus.publish({
        "type": "agent_thinking",
        "agent": agent_name,
        "thread_id": parent_id,
        "context": "reply",
    })

    personality = get_agent_personality(agent_name)
    voice = personality.get("voice", "professional")
    display_name = personality.get("display_name", agent_name)

    thread_context = ""
    if parent_id:
        try:
            from app.db import get_timeline_post_by_id, get_timeline_replies
            parent_post = await get_timeline_post_by_id(parent_id)
            replies = await get_timeline_replies(parent_id, limit=6)
            if parent_post:
                lines = [f"[Original post by {parent_post['agent']}]: {parent_post['content']}"]
                for r in replies:
                    if r.get("id") != post.get("id"):
                        lines.append(f"[{r['agent']}]: {r['content']}")
                if lines:
                    thread_context = "\n\nThread context:\n" + "\n".join(lines[-5:])
        except Exception:
            pass

    rich_context = await _build_agent_context()

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        tools = _get_tools_for_agent(agent_name)

        model = ChatOpenAI(model="gpt-4o", temperature=0.7, max_tokens=800)

        if tools:
            model = model.bind_tools(tools)

        system_prompt = f"""{_system_context()}

You are {display_name}, a team member on a job search team's timeline.
Your personality: {voice}

{f"Current state:{chr(10)}{rich_context}" if rich_context else ""}

You have tools — USE THEM to research real data before replying.

CRITICAL: Use web_search for ANY factual claims about:
- Current events, recent news, trending topics
- Statistics, surveys, or market data (your training data is outdated!)
- Products/services/companies that may have changed since 2024
- Always include the current year in search queries

Share like a knowledgeable teammate would:
- Use your tools to find REAL, CURRENT data, then share what you found with substance.
- Share techniques, strategies, frameworks, study plans, materials — be genuinely helpful.
- Use markdown freely: **bold**, bullet lists, code snippets, tables, headers — whatever communicates best.
- Include specific facts: company names, salary ranges, job titles, links, numbers.
- @mention another agent to pull them into the discussion if their expertise is relevant.
- When you create or save something, tell user WHERE to find it (e.g. "Check the Prep page").
- NO hashtags."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"""User: "{post['content']}"{thread_context}

Use tools, then reply as {display_name}."""),
        ]

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

        content = _enforce_quality(content, MAX_REPLY_LENGTH)

        reply_context: dict = {"in_reply_to": "user"}

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
            logger.info("Tool-powered reply from %s to user post %d", agent_name, post["id"])

            mentions = MENTION_RE.findall(content)
            for mentioned in mentions:
                if mentioned != agent_name and mentioned != "user":
                    mention_post = {**reply, "agent": agent_name}
                    await _handle_mention(mention_post, mentioned)

    except Exception as e:
        logger.error("Failed to generate tool-powered reply from %s: %s", agent_name, e)


async def create_user_reply(content: str, parent_id: int) -> dict:
    """Create a reply from the user, potentially triggering agent responses."""
    from app.db import get_timeline_post_by_id, get_timeline_replies

    post = await create_timeline_post(
        agent="user",
        post_type="thread",
        content=content,
        parent_id=parent_id,
    )

    await event_bus.publish({
        "type": "timeline_post",
        "post": post,
        "source": "user",
    })

    parent = await get_timeline_post_by_id(parent_id)

    mentions = MENTION_RE.findall(content)
    mentioned_agents = set()
    for mentioned_agent in mentions:
        if mentioned_agent != "user":
            mentioned_agents.add(mentioned_agent)
            await _handle_mention(post, mentioned_agent)

    if not mentioned_agents:
        asyncio.create_task(
            _route_user_reply(
                {"id": parent_id, "content": content, "agent": "user"},
                parent,
            )
        )

    return post


async def _route_user_reply(post: dict, parent: dict | None) -> None:
    """Fast-path routing for thread replies."""
    content = post.get("content", "")
    parent_id = post.get("id")

    try:
        from app.db import get_timeline_replies

        existing_replies = []
        if parent_id:
            existing_replies = await get_timeline_replies(parent_id, limit=20)

        thread_agents = []
        seen = set()
        for r in existing_replies:
            agent = r.get("agent", "")
            if agent and agent != "user" and agent not in seen:
                seen.add(agent)
                thread_agents.append(r)

        if thread_agents:
            agents_to_reply = thread_agents[-2:]

            for r in agents_to_reply:
                await event_bus.publish({
                    "type": "agent_thinking",
                    "agent": r["agent"],
                    "thread_id": parent_id,
                    "context": "thread_reply",
                })

            import time as _t
            ts = str(int(_t.time()))
            assignments = []
            for r in agents_to_reply:
                agent_name = r["agent"]
                ctx = r.get("context", {})
                dyn = ctx.get("dynamic_agent", {})
                if dyn:
                    assignments.append(AgentAssignment(
                        name=agent_name,
                        prompt=(
                            f"You are continuing a thread conversation. The user just said: \"{content}\". "
                            f"You already replied earlier in this thread. Continue the conversation naturally — "
                            f"answer their follow-up, provide the resources/info they asked for. "
                            f"If they asked for sources/links, use your tools to search for real ones. "
                            f"Stay in character as {dyn.get('display_name', agent_name)}."
                        ),
                        tools=True,
                        invented=True,
                        display_name=dyn.get("display_name", agent_name),
                        avatar=dyn.get("avatar", "🔍"),
                        expertise=dyn.get("expertise", ""),
                    ))
                else:
                    personality = get_agent_personality(agent_name)
                    assignments.append(AgentAssignment(
                        name=agent_name,
                        prompt=(
                            f"You are continuing a thread conversation. The user just said: \"{content}\". "
                            f"You already replied earlier. Continue naturally — answer their follow-up. "
                            f"If they asked for sources/links, use your tools to find real ones."
                        ),
                        tools=True,
                        invented=False,
                    ))

            plan = ResponsePlan(agents=assignments, depth="moderate")

            _thread_ctx = ""
            _post_id = post.get("id")
            if _post_id:
                try:
                    _replies = await get_timeline_replies(_post_id, limit=10)
                    if _replies:
                        _lines = []
                        for _r in _replies:
                            _p = get_agent_personality(_r["agent"])
                            _lines.append(f"[{_p.get('display_name', _r['agent'])}]: {_r['content'][:400]}")
                        if _lines:
                            _thread_ctx = "\n\nWhat others in the thread already said:\n" + "\n".join(_lines[-5:])
                except Exception:
                    pass
            _agent_ctx = await _build_agent_context()

            async def _safe_gen(a: AgentAssignment) -> tuple[AgentAssignment, tuple[str, dict] | None]:
                try:
                    return (a, await _generate_agent_content(
                        post, a, plan,
                        prefetched_thread_context=_thread_ctx,
                        prefetched_agent_context=_agent_ctx,
                    ))
                except Exception as e:
                    logger.error("Thread reply content gen failed for %s: %s", a.name, e)
                    return (a, None)

            results = await asyncio.gather(*[_safe_gen(a) for a in assignments])

            for i, (assignment, result) in enumerate(results):
                if result is None:
                    continue
                gen_content, reply_context = result
                if i > 0:
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                await _publish_agent_reply(post, assignment, gen_content, reply_context)

            # Spawn 1-2 NEW characters with fresh perspectives (non-blocking)
            asyncio.create_task(_spawn_new_thread_voices(post, parent, existing_replies))

            return

        await _auto_respond_to_user_reply(post, parent)

    except Exception as e:
        logger.error("Route user reply failed for %d: %s", parent_id, e)
        try:
            await _auto_respond_to_user_reply(post, parent)
        except Exception:
            pass


async def _auto_respond_to_user_reply(post: dict, parent: dict | None) -> None:
    """Route a user's thread reply to the single best agent based on content."""
    content = post.get("content", "")
    parent_id = post.get("id")
    personalities = get_all_personalities()
    agent_names = list(personalities.keys())

    if not agent_names:
        return

    thread_summary = ""
    if parent:
        thread_summary = f"\nOriginal post: \"{parent.get('content', '')}\""
        try:
            from app.db import get_timeline_replies
            replies = await get_timeline_replies(parent_id, limit=6)
            for r in replies:
                thread_summary += f"\n[{r['agent']}]: {r['content'][:100]}"
        except Exception:
            pass

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        agent_list = "\n".join(
            f"- {name}: {p.get('voice', '')} ({p.get('bio', '')})"
            for name, p in personalities.items()
        )

        model = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, max_tokens=100)
        response = await model.ainvoke([
            SystemMessage(content=f"""You are a routing system. Pick 1-2 agents to respond to a thread reply.
Return agent names separated by commas, most relevant first. ONLY agent names.

Available agents:
{agent_list}"""),
            HumanMessage(content=f"User says: \"{content}\"{thread_summary}\n\nBest agents?"),
        ])

        chosen_text = response.content.strip()
        chosen = [
            name.strip().lower().replace(" ", "_")
            for name in chosen_text.split(",")
        ]
        chosen = [name for name in chosen if name in personalities][:2]

        if not chosen:
            chosen = ["daily_coach"]

        await _generate_agent_reply_to_user(post, chosen[0])

        if len(chosen) > 1:
            asyncio.create_task(_delayed_agent_responses(post, chosen[1:]))

    except Exception as e:
        logger.error("Auto-respond to reply failed: %s", e)
        try:
            await _generate_agent_reply_to_user(post, "daily_coach")
        except Exception:
            pass


async def _spawn_new_thread_voices(
    post: dict, parent: dict | None, existing_replies: list[dict]
) -> None:
    """Spawn 1-2 new characters to join an existing thread with fresh perspectives.

    Runs after the existing thread agents reply, adding new voices that bring
    different angles to the conversation.
    """
    import json as _json
    import time as _t

    try:
        # Collect what's already been said so the router can avoid overlap
        thread_summary_lines = []
        for r in existing_replies[-6:]:
            ctx = r.get("context", {})
            dyn = ctx.get("dynamic_agent", {})
            name = dyn.get("display_name", r["agent"]) if dyn else r["agent"]
            thread_summary_lines.append(f"[{name}]: {r['content'][:200]}")
        thread_summary = "\n".join(thread_summary_lines)

        original_content = parent.get("content", "") if parent else ""
        user_reply = post.get("content", "")

        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        from .core import _system_context

        roster = _format_personality_roster()

        model = ChatOpenAI(model="gpt-4o", temperature=0.5, max_tokens=800)
        response = await model.ainvoke([
            SystemMessage(content=f"""{_system_context()}

You are the Nexus router. A thread is active and the user just replied. Bring in 1-2 NEW
characters who weren't in the thread before — people with a genuinely different perspective.

## BACKBONE AGENTS
{roster}

## EXISTING THREAD (do NOT repeat these angles)
Original post: "{original_content[:300]}"
User's new reply: "{user_reply[:300]}"

What's been said so far:
{thread_summary}

Create 1-2 NEW Reddit-style characters who bring a DIFFERENT angle than what's already covered.
Each needs a backbone_agent from the roster, a display_name, avatar, expertise, and prompt.
The prompt should tell them what unique angle to bring and reference the ongoing conversation.

Return ONLY valid JSON:
{{
  "characters": [
    {{
      "display_name": "...",
      "avatar": "...",
      "expertise": "...",
      "backbone_agent": "...",
      "prompt": "...",
      "tools": true
    }}
  ]
}}"""),
            HumanMessage(content="Create 1-2 new characters for this thread:"),
        ])

        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        data = _json.loads(text)
        characters = data.get("characters", [])
        if not characters:
            return

        import re
        ts = str(int(_t.time()))
        personalities = get_all_personalities()
        new_assignments = []

        for ch in characters[:2]:  # Cap at 2
            if not ch.get("prompt"):
                continue
            backbone = ch.get("backbone_agent", "").lower().strip()
            if backbone not in personalities:
                backbone = "pathfinder"

            agent_id = re.sub(
                r"[^a-z0-9_]", "_",
                ch.get("display_name", "agent").lower().replace(" ", "_"),
            ) + f"_{ts}"

            new_assignments.append(AgentAssignment(
                name=agent_id,
                prompt=ch["prompt"],
                tools=ch.get("tools", True),
                invented=True,
                display_name=ch.get("display_name", "Agent"),
                avatar=ch.get("avatar", "🔍"),
                expertise=ch.get("expertise", ""),
                _backbone_agent=backbone,
            ))

        if not new_assignments:
            return

        plan = ResponsePlan(agents=new_assignments, depth="moderate")

        # Stagger after existing replies
        await asyncio.sleep(random.uniform(2.0, 4.0))

        for assignment in new_assignments:
            await event_bus.publish({
                "type": "agent_thinking",
                "agent": assignment.name,
                "thread_id": post.get("id"),
                "context": "new_thread_voice",
            })

        _agent_ctx = await _build_agent_context()

        for assignment in new_assignments:
            try:
                result = await _generate_agent_content(
                    post, assignment, plan,
                    prefetched_agent_context=_agent_ctx,
                )
                if result:
                    content, reply_context = result
                    await _publish_agent_reply(post, assignment, content, reply_context)
                    await asyncio.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                logger.error("New thread voice %s failed: %s", assignment.display_name, e)

        logger.info("Spawned %d new thread voices for post %d", len(new_assignments), post.get("id"))

    except Exception as e:
        logger.debug("Failed to spawn new thread voices: %s", e)
