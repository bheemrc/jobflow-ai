"""Knowledge feed checking and HUNCH gene creation.

During pulse Step 3 (scan inputs), agents check configured feeds
for new information and create HUNCH genes from relevant items.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from app.dna import db as dna_db
from app.dna.models import DECAY_RATES

logger = logging.getLogger(__name__)


async def check_feeds(agent: str, user_id: str = "") -> int:
    """Check knowledge feeds for new items and create HUNCH genes.

    Returns number of new genes created.
    """
    feeds = await _get_agent_feeds(agent, user_id)
    if not feeds:
        return 0

    created = 0
    for feed in feeds:
        try:
            items = await _fetch_feed_items(feed, agent, user_id)
            for item in items:
                gene = await dna_db.create_gene(
                    agent=agent,
                    gene_type="HUNCH",
                    name=item["name"][:60],
                    description=item.get("description", ""),
                    content=item.get("content", ""),
                    confidence=item.get("confidence", 0.4),
                    decay_rate=DECAY_RATES["HUNCH"],
                    source=f"feed:{feed.get('name', 'unknown')}",
                    tags=item.get("tags", []),
                    user_id=user_id,
                )
                created += 1
                logger.debug("Feed gene created for %s: %s", agent, gene.get("name"))
        except Exception as e:
            logger.debug("Feed %s check failed for %s: %s", feed.get("name"), agent, e)

    return created


async def _get_agent_feeds(agent: str, user_id: str = "") -> list[dict]:
    """Get configured feeds for an agent from the knowledge_feeds table."""
    try:
        async with dna_db.get_conn() as conn:
            rows = await conn.fetch("""
                SELECT * FROM knowledge_feeds
                WHERE agent = $1 AND user_id = $2 AND active = TRUE
                ORDER BY last_checked NULLS FIRST
                LIMIT 5
            """, agent, user_id)
            return [dict(r) for r in rows]
    except Exception:
        return []


async def _fetch_feed_items(feed: dict, agent: str, user_id: str = "") -> list[dict]:
    """Fetch and analyze new items from a feed source.

    Uses LLM to extract relevant insights as potential HUNCH genes.
    """
    feed_type = feed.get("feed_type", "")
    feed_config = feed.get("config", {})
    if isinstance(feed_config, str):
        try:
            feed_config = json.loads(feed_config)
        except Exception:
            feed_config = {}

    # Update last_checked timestamp
    try:
        async with dna_db.get_conn() as conn:
            await conn.execute(
                "UPDATE knowledge_feeds SET last_checked = NOW() WHERE id = $1",
                feed["id"],
            )
    except Exception:
        pass

    # For now, feeds are analyzed via LLM
    # Future: direct RSS, API, or scraping integrations
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": f"""You are {agent}. Analyze feed context and extract 1-3 relevant hunches — things worth investigating or verifying.

Each hunch:
- name: Plain English description (max 60 chars)
- description: Why this matters
- confidence: 0.3-0.5 (these are hunches, not facts)
- tags: 2-3 relevant tags

Return: {{"items": [...]}}"""},
                {"role": "user", "content": f"Feed: {feed.get('name', '')}\nType: {feed_type}\nContext: {json.dumps(feed_config)[:1000]}"},
            ],
        )

        data = json.loads(completion.choices[0].message.content)
        return data.get("items", [])[:3]
    except Exception as e:
        logger.debug("Feed item extraction failed: %s", e)
        return []
