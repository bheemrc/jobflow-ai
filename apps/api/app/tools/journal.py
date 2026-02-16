"""Journal entry tool: add insights, recommendations, and notes."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def add_journal_entry(
    title: str,
    content: str,
    entry_type: str = "note",
    agent: str = "",
    priority: str = "medium",
    tags: str = "[]",
) -> str:
    """Write a journal entry to the Inbox/Journal page. Use this to record insights,
    recommendations, action items, or daily summaries that the user should see.

    Any agent or bot can call this tool to post standalone notes, insights, and
    recommendations that appear in the user's Journal tab.

    Args:
        title: A short, descriptive title for the entry.
        content: The full content in markdown format.
        entry_type: Type of entry — "insight", "recommendation", "summary", "note", or "action_item".
        agent: The name of the agent or bot creating this entry.
        priority: Priority level — "low", "medium", or "high".
        tags: JSON array of tag strings (e.g. '["interview", "amazon"]').

    Returns:
        JSON with saved status and entry_id.
    """
    valid_types = ("insight", "recommendation", "summary", "note", "action_item")
    if entry_type not in valid_types:
        return json.dumps({"error": f"Invalid entry_type. Must be one of: {', '.join(valid_types)}"})

    valid_priorities = ("low", "medium", "high")
    if priority not in valid_priorities:
        return json.dumps({"error": f"Invalid priority. Must be one of: {', '.join(valid_priorities)}"})

    try:
        try:
            tags_parsed = json.loads(tags) if isinstance(tags, str) else tags
            if not isinstance(tags_parsed, list):
                tags_parsed = []
        except json.JSONDecodeError:
            tags_parsed = []

        from app.db import create_journal_entry
        entry_id = await create_journal_entry(
            title=title[:500],
            content=content[:10000],
            entry_type=entry_type,
            agent=agent[:100] if agent else None,
            priority=priority,
            tags=tags_parsed,
        )

        return json.dumps({
            "saved": True,
            "entry_id": entry_id,
            "entry_type": entry_type,
            "title": title,
            "message": f"Journal entry '{title}' saved (id={entry_id})",
        })
    except Exception as e:
        logger.error("add_journal_entry error: %s", e)
        return json.dumps({"error": f"Failed to save journal entry: {e}"})
