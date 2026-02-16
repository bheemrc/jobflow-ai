"""Bridge between Nexus (timeline) and Katalyst (reactions).

- Spawn reactions from Nexus posts with [goal] tags or detected goal intent
- Post reaction summaries back to Nexus timeline
"""

from __future__ import annotations

import json
import logging
import os

from app.event_bus import event_bus

logger = logging.getLogger(__name__)


async def maybe_spawn_from_post(post: dict) -> dict | None:
    """Check if a timeline post should trigger a Katalyst reaction.

    Posts with [goal] prefix or natural-language goal intent are converted
    to Katalyst reactions automatically.
    """
    content = post.get("content", "")
    agent = post.get("agent", "")
    user_id = post.get("user_id", "")

    # Only spawn from user posts
    if agent != "user":
        return None

    # Skip @mention posts — those are conversations, not goals
    import re
    if re.search(r"@\w+", content) and not content.strip().lower().startswith(("[goal]", "goal:", "[katalyst]")):
        return None

    # Fast path: explicit markers
    goal = _extract_goal_marker(content)

    # Slow path: LLM intent detection for natural language goals
    if not goal:
        goal = await _detect_goal_intent(content)

    if not goal:
        return None

    try:
        from app.katalyst.orchestrator import spawn_reaction
        reaction = await spawn_reaction(goal=goal, user_id=user_id)

        # Post back to timeline
        await _post_reaction_spawned(reaction, post.get("id"), user_id)

        logger.info("Bridge: spawned reaction %d from post %s", reaction["id"], post.get("id"))
        return reaction
    except Exception as e:
        logger.warning("Bridge spawn failed: %s", e)
        return None


async def post_reaction_summary(reaction_id: int, user_id: str = "") -> dict | None:
    """Post a reaction completion summary to the Nexus timeline."""
    try:
        from app.katalyst import db as kat_db
        reaction = await kat_db.get_reaction(reaction_id, user_id)
        if not reaction:
            return None

        workstreams = await kat_db.get_workstreams(reaction_id, user_id)
        artifacts = await kat_db.get_artifacts(reaction_id, user_id)

        ws_summary = "\n".join(
            f"- **{ws['title']}**: {ws['status']} ({ws['progress']}%)"
            for ws in workstreams
        )
        artifact_summary = "\n".join(
            f"- {a['title']} (v{a['version']})"
            for a in artifacts[:5]
        )

        content = f"""**Katalyst Reaction Complete**

Goal: {reaction['goal']}

**Workstreams:**
{ws_summary or "None"}

**Artifacts produced:**
{artifact_summary or "None"}

View full details in [Katalyst](/katalyst/{reaction_id})."""

        from app.db import create_timeline_post
        post = await create_timeline_post(
            agent=reaction.get("lead_agent", "pathfinder"),
            post_type="katalyst_summary",
            content=content,
            context={"reaction_id": reaction_id, "type": "katalyst_bridge"},
            user_id=user_id,
        )

        await event_bus.publish({
            "type": "timeline_post",
            "post": post,
        })

        return post
    except Exception as e:
        logger.warning("Bridge summary post failed: %s", e)
        return None


async def _post_reaction_spawned(reaction: dict, source_post_id: int | None, user_id: str) -> None:
    """Post a notification that a reaction was spawned from a post."""
    try:
        from app.db import create_timeline_post

        content = f"Katalyst reaction launched: **{reaction['goal'][:100]}**\n\nLed by {reaction.get('lead_agent', 'pathfinder')}. Track progress in [Katalyst](/katalyst/{reaction['id']})."

        post = await create_timeline_post(
            agent=reaction.get("lead_agent", "pathfinder"),
            post_type="katalyst_launch",
            content=content,
            context={
                "reaction_id": reaction["id"],
                "source_post_id": source_post_id,
                "type": "katalyst_bridge",
            },
            user_id=user_id,
        )

        await event_bus.publish({
            "type": "timeline_post",
            "post": post,
        })
    except Exception as e:
        logger.debug("Bridge launch post failed: %s", e)


def _extract_goal_marker(content: str) -> str:
    """Extract a goal from explicit markers: [goal], goal:, [katalyst]."""
    content = content.strip()
    lower = content.lower()

    for prefix, length in [("[goal]", 6), ("goal:", 5), ("[katalyst]", 10)]:
        if lower.startswith(prefix):
            return content[length:].strip()

    return ""


async def _detect_goal_intent(content: str) -> str:
    """Use LLM to detect if a post contains an actionable goal.

    Returns the extracted goal string if the post expresses a clear,
    actionable project intent. Returns empty string for casual posts,
    questions, or status updates.
    """
    content = content.strip()
    # Skip very short or very long posts
    if len(content) < 20 or len(content) > 2000:
        return ""

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=200,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": """Analyze if this post contains a clear, actionable PROJECT GOAL that an AI agent team should decompose into workstreams and produce deliverables for.

IS a goal (requires multi-step project work):
- "Prepare for a senior frontend role at Stripe" → yes, needs research + resume + prep
- "Build a networking strategy for breaking into fintech" → yes, needs mapping + outreach
- "Research the top 10 companies hiring Go developers in NYC" → yes, needs systematic research

NOT a goal (handle as conversation instead):
- Questions: "What is the difference between REST and GraphQL?" → no, just a Q&A
- Advice requests: "How should I negotiate my offer?" → no, just needs a response
- Status updates: "Just had my interview, went well" → no, just sharing
- Emotional: "Feeling discouraged today" → no, support needed not a project
- Simple asks: "Can you find me salary data?" → no, single-tool task

The key distinction: a goal requires DECOMPOSITION into phases and workstreams. If a simple agent reply would suffice, it is NOT a goal.

Return JSON:
{"is_goal": true/false, "goal": "extracted goal text if is_goal, else empty string", "confidence": 0.0-1.0}

Only return is_goal:true if confidence >= 0.8."""},
                {"role": "user", "content": content[:1000]},
            ],
        )

        data = json.loads(completion.choices[0].message.content)
        if data.get("is_goal") and data.get("confidence", 0) >= 0.8:
            return data.get("goal", "").strip()
        return ""
    except Exception as e:
        logger.debug("Goal intent detection failed: %s", e)
        return ""
