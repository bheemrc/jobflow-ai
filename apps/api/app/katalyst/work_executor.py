"""Pulse-driven workstream execution.

Each pulse, agents check for active Katalyst workstreams assigned to them
and advance them through stages: research → draft artifact → refine → review.
"""

from __future__ import annotations

import json
import logging
import os

from app.katalyst import db as kat_db
from app.katalyst.artifact_engine import create_artifact, update_artifact_content
from app.event_bus import event_bus

logger = logging.getLogger(__name__)


async def execute_workstream_step(
    ws: dict,
    agent: str,
    user_id: str = "",
) -> dict | None:
    """Execute the next step for a workstream based on its current status.

    Returns updated workstream dict or None if no action taken.
    """
    status = ws.get("status", "pending")
    ws_id = ws["id"]
    reaction_id = ws["reaction_id"]

    if status == "pending":
        # Activate workstream → research
        return await _start_research(ws, agent, user_id)
    elif status == "research":
        # Research → drafting (produce initial artifact)
        return await _draft_artifact(ws, agent, user_id)
    elif status == "drafting":
        # Drafting → refining
        return await _refine_artifact(ws, agent, user_id)
    elif status == "refining":
        # Refining → review
        return await _advance_to_review(ws, agent, user_id)
    elif status == "review":
        # Review → completed
        return await _complete_workstream(ws, agent, user_id)

    return None


async def check_agent_workstreams(agent: str, user_id: str = "") -> int:
    """Check all active workstreams for an agent and execute next steps.

    Called during pulse Step 3 (scan inputs) or Step 6 (act).
    Returns number of workstreams advanced.
    """
    # Find active reactions for this user
    reactions = await kat_db.list_reactions(user_id=user_id, status="active")
    advanced = 0

    for reaction in reactions:
        workstreams = await kat_db.get_workstreams(reaction["id"], user_id)
        for ws in workstreams:
            if ws.get("agent") != agent:
                continue
            if ws.get("status") in ("completed",):
                continue

            try:
                result = await execute_workstream_step(ws, agent, user_id)
                if result:
                    advanced += 1
            except Exception as e:
                logger.warning(
                    "Workstream %d step failed: %s", ws["id"], e
                )

    return advanced


async def _start_research(ws: dict, agent: str, user_id: str) -> dict | None:
    """Move workstream from pending to research stage."""
    updated = await kat_db.update_workstream(
        ws["id"], user_id, status="research", progress=20
    )

    await kat_db.create_event(
        reaction_id=ws["reaction_id"],
        event_type="workstream_started",
        agent=agent,
        message=f"Starting research: {ws['title']}",
        data={"workstream_id": ws["id"]},
        user_id=user_id,
    )

    await event_bus.publish({
        "type": "katalyst_workstream_advanced",
        "reaction_id": ws["reaction_id"],
        "workstream_id": ws["id"],
        "status": "research",
    })

    return updated


async def _draft_artifact(ws: dict, agent: str, user_id: str) -> dict | None:
    """Research phase complete — generate initial artifact draft."""
    # Use LLM to generate artifact content based on workstream description
    content = await _generate_artifact_content(
        ws["title"], ws.get("description", ""), agent, stage="draft"
    )

    if content:
        # Create the artifact
        await create_artifact(
            reaction_id=ws["reaction_id"],
            title=f"{ws['title']} — Draft",
            content=content,
            artifact_type="document",
            agent=agent,
            workstream_id=ws["id"],
            user_id=user_id,
        )

        # Detect blockers from the draft content
        try:
            from app.katalyst.blocker_engine import detect_blockers, try_auto_resolve
            blockers = await detect_blockers(
                reaction_id=ws["reaction_id"],
                workstream_id=ws["id"],
                context=f"Workstream: {ws['title']}\n\n{content[:2000]}",
                agent=agent,
                user_id=user_id,
            )
            for blocker in blockers:
                await try_auto_resolve(blocker, user_id)
        except Exception as e:
            logger.debug("Blocker detection failed for ws %d: %s", ws["id"], e)

    # Advance to drafting stage
    updated = await kat_db.update_workstream(
        ws["id"], user_id, status="drafting", progress=40
    )

    await event_bus.publish({
        "type": "katalyst_workstream_advanced",
        "reaction_id": ws["reaction_id"],
        "workstream_id": ws["id"],
        "status": "drafting",
    })

    return updated


async def _refine_artifact(ws: dict, agent: str, user_id: str) -> dict | None:
    """Drafting phase complete — refine existing artifact."""
    # Find the current artifact for this workstream
    artifacts = await kat_db.get_artifacts(ws["reaction_id"], user_id)
    ws_artifacts = [a for a in artifacts if a.get("workstream_id") == ws["id"]]

    if ws_artifacts:
        latest = ws_artifacts[0]  # Most recent (DESC order)
        refined = await _generate_artifact_content(
            ws["title"], latest.get("content", ""), agent, stage="refine"
        )
        if refined:
            await update_artifact_content(
                artifact_id=latest["id"],
                new_content=refined,
                agent=agent,
                user_id=user_id,
            )

    updated = await kat_db.update_workstream(
        ws["id"], user_id, status="refining", progress=60
    )

    await event_bus.publish({
        "type": "katalyst_workstream_advanced",
        "reaction_id": ws["reaction_id"],
        "workstream_id": ws["id"],
        "status": "refining",
    })

    return updated


async def _advance_to_review(ws: dict, agent: str, user_id: str) -> dict | None:
    """Refining complete — move to review stage."""
    updated = await kat_db.update_workstream(
        ws["id"], user_id, status="review", progress=80
    )

    await kat_db.create_event(
        reaction_id=ws["reaction_id"],
        event_type="workstream_review",
        agent=agent,
        message=f"Ready for review: {ws['title']}",
        data={"workstream_id": ws["id"]},
        user_id=user_id,
    )

    await event_bus.publish({
        "type": "katalyst_workstream_advanced",
        "reaction_id": ws["reaction_id"],
        "workstream_id": ws["id"],
        "status": "review",
    })

    return updated


async def _complete_workstream(ws: dict, agent: str, user_id: str) -> dict | None:
    """Review complete — mark workstream as done."""
    from app.katalyst.orchestrator import advance_workstream
    return await advance_workstream(ws["id"], user_id)


async def _generate_artifact_content(
    title: str, context: str, agent: str, stage: str = "draft"
) -> str:
    """Use LLM to generate or refine artifact content."""
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        if stage == "draft":
            system_msg = f"""You are {agent}, an AI specialist. Generate a thorough first draft for the following workstream.
Write in clear, actionable prose. Use markdown formatting. Be specific and practical."""
            user_msg = f"Title: {title}\nDescription: {context[:2000]}\n\nGenerate the initial draft."
        else:
            system_msg = f"""You are {agent}, an AI specialist. Refine and improve the following draft.
Fix errors, add detail, improve structure. Keep the same format."""
            user_msg = f"Title: {title}\n\nCurrent draft:\n{context[:3000]}\n\nRefine and improve this."

        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.4,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
        )

        return completion.choices[0].message.content or ""
    except Exception as e:
        logger.warning("Artifact generation failed: %s", e)
        return ""
