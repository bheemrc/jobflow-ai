"""Blocker detection and resolution.

During workstream execution, agents may encounter situations that need
human input. Blockers are created with options and confidence scores.
High-confidence blockers can be auto-resolved; low-confidence ones
are escalated to the user.
"""

from __future__ import annotations

import json
import logging
import os

from app.katalyst import db as kat_db
from app.event_bus import event_bus

logger = logging.getLogger(__name__)

AUTO_RESOLVE_THRESHOLD = 0.8


async def detect_blockers(
    reaction_id: int,
    workstream_id: int,
    context: str,
    agent: str = "",
    user_id: str = "",
) -> list[dict]:
    """Use LLM to detect potential blockers from workstream context.

    Returns list of created blocker dicts.
    """
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=800,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": """Analyze the workstream context for blockers — things that need human decision or input before work can proceed.

For each blocker, provide:
- title: Short description of the blocker
- description: Why this blocks progress
- severity: "low", "medium", or "high"
- options: 2-3 possible resolutions, each with "label" and "description"
- auto_resolve_confidence: 0.0-1.0 how confident you are in the best option

Return: {"blockers": [...]}
If no blockers found, return: {"blockers": []}"""},
                {"role": "user", "content": f"Workstream context:\n{context[:2000]}"},
            ],
        )

        data = json.loads(completion.choices[0].message.content)
        blockers_data = data.get("blockers", [])[:3]
    except Exception as e:
        logger.debug("Blocker detection failed: %s", e)
        return []

    created = []
    for b in blockers_data:
        blocker = await kat_db.create_blocker(
            reaction_id=reaction_id,
            title=b.get("title", "Unknown blocker"),
            description=b.get("description", ""),
            severity=b.get("severity", "medium"),
            agent=agent,
            options=b.get("options", []),
            auto_resolve_confidence=b.get("auto_resolve_confidence", 0.0),
            workstream_id=workstream_id,
            user_id=user_id,
        )
        created.append(blocker)

        await kat_db.create_event(
            reaction_id=reaction_id,
            event_type="blocker_created",
            agent=agent,
            message=f"Blocker detected: {blocker['title']}",
            data={"blocker_id": blocker["id"], "severity": blocker.get("severity")},
            user_id=user_id,
        )

        await event_bus.publish({
            "type": "katalyst_blocker_created",
            "reaction_id": reaction_id,
            "blocker_id": blocker["id"],
            "severity": blocker.get("severity"),
        })

    return created


async def try_auto_resolve(blocker: dict, user_id: str = "") -> dict | None:
    """Attempt to auto-resolve a blocker if confidence is high enough.

    Returns resolved blocker dict if auto-resolved, None otherwise.
    """
    confidence = blocker.get("auto_resolve_confidence", 0.0)
    if confidence < AUTO_RESOLVE_THRESHOLD:
        return None

    options = blocker.get("options", [])
    if not options:
        return None

    # Pick the first option (highest confidence)
    best_option = options[0]
    resolution = f"Auto-resolved: {best_option.get('label', 'Option 1')} — {best_option.get('description', '')}"

    resolved = await kat_db.resolve_blocker(
        blocker_id=blocker["id"],
        resolution=resolution,
        resolved_by=blocker.get("agent", "system"),
        user_id=user_id,
    )

    if resolved:
        await kat_db.create_event(
            reaction_id=blocker["reaction_id"],
            event_type="blocker_auto_resolved",
            agent=blocker.get("agent", "system"),
            message=f"Auto-resolved: {blocker['title']} (confidence: {confidence:.0%})",
            data={
                "blocker_id": blocker["id"],
                "resolution": resolution,
                "confidence": confidence,
            },
            user_id=user_id,
        )

        await event_bus.publish({
            "type": "katalyst_blocker_resolved",
            "reaction_id": blocker["reaction_id"],
            "blocker_id": blocker["id"],
            "auto": True,
        })

        logger.info(
            "Auto-resolved blocker %d (confidence=%.2f): %s",
            blocker["id"], confidence, blocker["title"],
        )

    return resolved


async def process_blockers(reaction_id: int, user_id: str = "") -> int:
    """Process all unresolved blockers for a reaction.

    Attempts auto-resolution on high-confidence blockers.
    Returns number of blockers auto-resolved.
    """
    blockers = await kat_db.get_blockers(reaction_id, user_id, unresolved_only=True)
    resolved_count = 0

    for blocker in blockers:
        result = await try_auto_resolve(blocker, user_id)
        if result:
            resolved_count += 1

    return resolved_count
