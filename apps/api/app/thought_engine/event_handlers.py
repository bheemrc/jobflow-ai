"""Event-driven thought triggers, thought generation, and mention handling."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from app.db import (
    create_timeline_post,
    get_thought_triggers,
    update_trigger_last_fired,
    store_agent_memory,
    recall_agent_memories,
)
from app.event_bus import event_bus

from .core import (
    MENTION_RE,
    MAX_THOUGHT_LENGTH,
    MAX_REPLY_LENGTH,
    _enforce_quality,
    _system_context,
    _build_agent_context,
    _get_tools_for_agent,
)
from .rate_limiting import _check_rate_limit, _record_post
from .personality import get_agent_personality, get_all_personalities

logger = logging.getLogger("app.thought_engine")

# In-memory cooldown tracker as safety net (DB cooldowns can be stale)
_trigger_last_fired: dict[str, float] = {}  # "agent:event" → monotonic time


async def handle_event(event_name: str, event_context: dict | None = None) -> list[dict]:
    """Process an event and generate timeline posts from matching triggers."""
    import time as _time
    triggers = await get_thought_triggers(enabled_only=True)
    now = datetime.now(timezone.utc)
    created_posts = []

    for trigger in triggers:
        if trigger.get("trigger_type") != "event":
            continue

        config = trigger.get("trigger_config", {})
        trigger_event = config.get("event", "")

        if trigger_event != event_name:
            continue

        agent = trigger.get("agent", "")
        cooldown = trigger.get("cooldown_minutes", 30)

        # In-memory cooldown check (safety net against DB staleness)
        cooldown_key = f"{agent}:{event_name}"
        last_mem = _trigger_last_fired.get(cooldown_key, 0)
        if _time.monotonic() - last_mem < cooldown * 60:
            logger.debug("Skipping trigger for %s on %s (in-memory cooldown)", agent, event_name)
            continue

        # DB-based cooldown check
        last_fired = trigger.get("last_triggered_at")
        if last_fired:
            try:
                last_dt = datetime.fromisoformat(last_fired) if isinstance(last_fired, str) else last_fired
                if now - last_dt < timedelta(minutes=cooldown):
                    logger.debug(
                        "Skipping trigger %d for %s (cooldown: %d min)",
                        trigger["id"], agent, cooldown,
                    )
                    continue
            except Exception:
                pass

        prompt_template = trigger["prompt_template"]
        post = await _generate_thought(agent, prompt_template, event_name, event_context)

        if post:
            created_posts.append(post)
            await update_trigger_last_fired(trigger["id"])
            _trigger_last_fired[cooldown_key] = _time.monotonic()

            await event_bus.publish({
                "type": "timeline_post",
                "post": post,
                "source": "thought_engine",
            })

            # Trigger DNA splice for new timeline posts (non-blocking)
            try:
                from app.dna.splice import splice_from_timeline_post
                import asyncio
                asyncio.create_task(splice_from_timeline_post(post))
            except Exception:
                pass

            mentions = MENTION_RE.findall(post.get("content", ""))
            for mentioned_agent in mentions:
                await _handle_mention(post, mentioned_agent)

    return created_posts


async def _generate_thought(
    agent: str,
    prompt_template: str,
    event_name: str,
    event_context: dict | None = None,
) -> dict | None:
    """Generate a short timeline post using LLM."""
    if not _check_rate_limit(agent):
        return None

    await event_bus.publish({
        "type": "agent_thinking",
        "agent": agent,
        "context": "thought",
    })

    personality = get_agent_personality(agent)
    voice = personality.get("voice", "professional")
    display_name = personality.get("display_name", agent)

    ctx_str = ""
    if event_context:
        ctx_parts = []
        for k, v in event_context.items():
            if v and k not in ("type", "source", "event_id", "timestamp"):
                ctx_parts.append(f"- {k}: {v}")
        if ctx_parts:
            ctx_str = "\nEvent context:\n" + "\n".join(ctx_parts)

    rich_context = await _build_agent_context()

    memory_context = ""
    try:
        memories = await recall_agent_memories(agent, limit=5, min_importance=0.3)
        if memories:
            memory_lines = [f"- [{m['memory_type']}] {m['content']}" for m in memories]
            memory_context = "\nYour recent memories/observations:\n" + "\n".join(memory_lines)
    except Exception:
        pass

    tools = _get_tools_for_agent(agent)

    system_prompt = f"""{_system_context()}

You are {display_name}, an AI agent on a job search team timeline.
Your personality: {voice}

{"You have tools available — use them to look up real data." if tools else ""}

{f"Current state:{chr(10)}{rich_context}" if rich_context else ""}
{memory_context}

Rules:
- Share like a real teammate — tips, tricks, links, data, techniques.
- Use markdown freely: bold, bullets, code snippets, tables if useful.
- Include specific data (company names, numbers, job titles) when available.
- @mention another agent to bring them into the conversation if relevant.
- Be in-character — match the personality voice.
- Reference your memories when relevant — show continuity.
- NO hashtags."""

    user_prompt = f"""Event: {event_name}
{ctx_str}

{prompt_template}"""

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        model = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.8,
            max_tokens=800,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        if tools:
            model = model.bind_tools(tools)
            from app.nodes.tool_executor import run_agent_with_tools
            final_message, _ = await run_agent_with_tools(
                model=model,
                messages=messages,
                tools=tools,
                config=None,
                max_rounds=2,
                min_tool_calls=0,
                max_reflections=0,
            )
            content = final_message.content.strip() if final_message else ""
        else:
            response = await model.ainvoke(messages)
            content = response.content.strip()

        if not content:
            return None

        content = _enforce_quality(content, MAX_THOUGHT_LENGTH)

        post_type = "thought"
        if "stage_" in event_name:
            post_type = "discovery"
        elif "bot_completed" in event_name:
            post_type = "reaction"

        post_context = {"event": event_name}
        if event_context:
            for key in ("company", "role", "job_id", "bot_name", "run_id", "title"):
                if key in event_context:
                    post_context[key] = event_context[key]

        post = await create_timeline_post(
            agent=agent,
            post_type=post_type,
            content=content,
            context=post_context,
        )
        _record_post(agent)
        logger.info("Generated thought for %s on event %s: %s", agent, event_name, content[:80])

        try:
            importance = 0.6 if "stage_" in event_name else 0.4
            if "offer" in event_name:
                importance = 0.9
            elif "interview" in event_name:
                importance = 0.7
            memory_content = f"Posted about {event_name}"
            if event_context:
                if event_context.get("company"):
                    memory_content += f" for {event_context['company']}"
                if event_context.get("title") or event_context.get("role"):
                    memory_content += f" ({event_context.get('title') or event_context.get('role')})"
            await store_agent_memory(
                agent=agent,
                memory_type="interaction",
                content=memory_content,
                context={"event": event_name, "post_id": post.get("id")},
                importance=importance,
            )
        except Exception:
            pass

        return post

    except Exception as e:
        logger.error("Failed to generate thought for %s: %s", agent, e)
        return None


async def _handle_mention(source_post: dict, mentioned_agent: str) -> None:
    """When a post mentions another agent, generate a reply in the thread."""
    if mentioned_agent == source_post.get("agent"):
        return

    known = get_all_personalities()
    if mentioned_agent not in known:
        return
    personality = known[mentioned_agent]

    parent_id = source_post.get("parent_id") or source_post["id"]

    if not _check_rate_limit(mentioned_agent, parent_id):
        return

    await event_bus.publish({
        "type": "agent_thinking",
        "agent": mentioned_agent,
        "thread_id": parent_id,
        "context": "mention",
    })

    display_name = personality.get("display_name", mentioned_agent)
    voice = personality.get("voice", "professional")
    source_agent = source_post.get("agent", "someone")

    sibling_context = ""
    try:
        from app.db import get_timeline_replies
        siblings = await get_timeline_replies(parent_id, limit=10)
        if siblings:
            known_all = get_all_personalities()
            sibling_lines = []
            for sib in siblings:
                sib_agent = sib.get("agent", "unknown")
                sib_name = known_all.get(sib_agent, {}).get("display_name", sib_agent)
                sib_content = sib.get("content", "")[:200]
                sibling_lines.append(f"  @{sib_name}: {sib_content}")
            if sibling_lines:
                sibling_context = "\n\nOther agents in this thread:\n" + "\n".join(sibling_lines[-5:])
    except Exception:
        pass

    memory_context = ""
    try:
        memories = await recall_agent_memories(mentioned_agent, limit=3, min_importance=0.3)
        if memories:
            memory_lines = [f"- {m['content']}" for m in memories]
            memory_context = "\n\nYour recent memories:\n" + "\n".join(memory_lines)
    except Exception:
        pass

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        model = ChatOpenAI(model="gpt-4o-mini", temperature=0.8, max_tokens=800)
        response = await model.ainvoke([
            SystemMessage(content=f"""{_system_context()}

You are {display_name}, a real team member on the Nexus collective timeline.
Your personality: {voice}

You were mentioned by a teammate. Jump in and contribute your expertise:
- Reference what other agents said when relevant (agree, challenge, build on it).
- Share your unique perspective, tips, techniques, or data.
- Use markdown freely if it helps communicate.
- Be in-character and genuinely helpful.
- @mention another agent if you want to bring more expertise in.
- NO hashtags.
{memory_context}"""),
            HumanMessage(content=f"""{source_agent} mentioned you:
"{source_post['content']}"
{sibling_context}

Jump in:"""),
        ])

        content = response.content.strip()
        if not content:
            return

        content = _enforce_quality(content, MAX_REPLY_LENGTH)

        reply = await create_timeline_post(
            agent=mentioned_agent,
            post_type="thread",
            content=content,
            parent_id=parent_id,
            context={"mentioned_by": source_agent},
        )

        if reply:
            _record_post(mentioned_agent, parent_id)
            await event_bus.publish({
                "type": "timeline_post",
                "post": reply,
                "source": "thought_engine",
            })
            logger.info("Mention reply from %s in thread %d", mentioned_agent, parent_id)

            try:
                await store_agent_memory(
                    agent=mentioned_agent,
                    memory_type="interaction",
                    content=f"Replied to @{source_agent} in thread {parent_id}",
                    context={"thread_id": parent_id, "source_agent": source_agent},
                    importance=0.5,
                )
            except Exception:
                pass

    except Exception as e:
        logger.error("Failed to generate mention reply from %s: %s", mentioned_agent, e)
