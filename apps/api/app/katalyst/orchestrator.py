"""Reaction lifecycle: spawn (decompose + recruit + plan), advance, complete.

When a user posts a goal, the orchestrator:
1. Decomposes the goal into phases and workstreams using LLM
2. Assigns agents to each workstream
3. Creates the reaction with full plan
4. Advances workstreams through stages as agents complete work
"""

from __future__ import annotations

import json
import logging
import os

from app.katalyst import db as kat_db
from app.event_bus import event_bus

logger = logging.getLogger(__name__)


async def spawn_reaction(goal: str, user_id: str = "") -> dict:
    """Spawn a new reaction from a user goal.

    Uses LLM to decompose the goal into phases, workstreams, and agent assignments.
    """
    # 1. Decompose goal into plan
    plan = await _decompose_goal(goal)

    # 2. Create reaction
    reaction = await kat_db.create_reaction(
        goal=goal,
        lead_agent=plan.get("lead_agent", "pathfinder"),
        phases=plan.get("phases", []),
        context={"original_goal": goal},
        user_id=user_id,
    )
    reaction_id = reaction["id"]

    # 3. Create workstreams
    for i, ws in enumerate(plan.get("workstreams", [])):
        await kat_db.create_workstream(
            reaction_id=reaction_id,
            title=ws.get("title", f"Workstream {i+1}"),
            description=ws.get("description", ""),
            agent=ws.get("agent", "pathfinder"),
            phase=ws.get("phase", ""),
            order=i,
            user_id=user_id,
        )

    # 4. Log event
    await kat_db.create_event(
        reaction_id=reaction_id,
        event_type="reaction_spawned",
        agent=plan.get("lead_agent", "system"),
        message=f"Reaction spawned: {goal}",
        data=plan,
        user_id=user_id,
    )

    # 5. Activate reaction
    reaction = await kat_db.update_reaction(reaction_id, user_id, status="active")

    # 6. Publish SSE event
    await event_bus.publish({
        "type": "katalyst_reaction_spawned",
        "reaction_id": reaction_id,
        "goal": goal,
    })

    logger.info("Spawned reaction %d: %s", reaction_id, goal[:80])

    # 7. Kick off initial workstream execution immediately (non-blocking)
    import asyncio
    asyncio.create_task(_execute_initial_workstreams(reaction_id, user_id))

    return reaction


async def _execute_initial_workstreams(reaction_id: int, user_id: str) -> None:
    """Execute workstreams through multiple stages after spawn.

    Runs each workstream through: pending → research → drafting (producing an artifact).
    Subsequent stages (refining, review, complete) happen via pulse or manual trigger.
    """
    try:
        from app.katalyst.work_executor import execute_workstream_step
        workstreams = await kat_db.get_workstreams(reaction_id, user_id)
        for ws in workstreams:
            try:
                agent = ws.get("agent", "")
                # Step 1: pending → research
                await execute_workstream_step(ws, agent, user_id)
                # Refresh workstream state from DB
                async with kat_db.get_conn() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM katalyst_workstreams WHERE id = $1 AND user_id = $2",
                        ws["id"], user_id)
                if not row:
                    continue
                updated_ws = kat_db._serialize(dict(row))

                # Step 2: research → drafting (generates initial artifact)
                if updated_ws.get("status") == "research":
                    await execute_workstream_step(updated_ws, agent, user_id)
            except Exception as e:
                logger.warning("Initial execution failed for workstream %d: %s", ws["id"], e)
    except Exception as e:
        logger.warning("Initial workstream execution failed for reaction %d: %s", reaction_id, e)


async def advance_workstream(ws_id: int, user_id: str = "") -> dict | None:
    """Advance a workstream to its next stage."""
    stage_order = ["pending", "research", "drafting", "refining", "review", "completed"]

    async with kat_db.get_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM katalyst_workstreams WHERE id = $1 AND user_id = $2",
            ws_id, user_id)
    if not row:
        return None

    ws = kat_db._serialize(dict(row))
    current = ws.get("status", "pending")
    try:
        idx = stage_order.index(current)
        next_status = stage_order[min(idx + 1, len(stage_order) - 1)]
    except ValueError:
        next_status = "research"

    progress_map = {"pending": 0, "research": 20, "drafting": 40, "refining": 60, "review": 80, "completed": 100}
    updated = await kat_db.update_workstream(
        ws_id, user_id,
        status=next_status,
        progress=progress_map.get(next_status, 0),
    )

    if updated:
        await kat_db.create_event(
            reaction_id=ws["reaction_id"],
            event_type="workstream_advanced",
            agent=ws.get("agent", ""),
            message=f"{ws['title']}: {current} -> {next_status}",
            data={"workstream_id": ws_id, "from": current, "to": next_status},
            user_id=user_id,
        )

    # Check if all workstreams completed
    await _check_reaction_completion(ws["reaction_id"], user_id)

    return updated


async def complete_reaction(reaction_id: int, user_id: str = "") -> dict | None:
    """Mark a reaction as completed."""
    from datetime import datetime, timezone
    reaction = await kat_db.update_reaction(
        reaction_id, user_id,
        status="completed",
        completed_at=datetime.now(timezone.utc),
    )
    if reaction:
        await kat_db.create_event(
            reaction_id=reaction_id,
            event_type="reaction_completed",
            agent="system",
            message="Reaction completed",
            user_id=user_id,
        )
        await event_bus.publish({
            "type": "katalyst_reaction_completed",
            "reaction_id": reaction_id,
        })
        # Post completion summary to Nexus timeline
        try:
            from app.katalyst.bridge import post_reaction_summary
            await post_reaction_summary(reaction_id, user_id)
        except Exception as e:
            logger.debug("Failed to post reaction summary to timeline: %s", e)
    return reaction


async def _check_reaction_completion(reaction_id: int, user_id: str = "") -> None:
    """Check if all workstreams are completed and auto-complete the reaction."""
    workstreams = await kat_db.get_workstreams(reaction_id, user_id)
    if not workstreams:
        return
    all_done = all(ws.get("status") == "completed" for ws in workstreams)
    if all_done:
        await complete_reaction(reaction_id, user_id)


async def _decompose_goal(goal: str) -> dict:
    """Use LLM to decompose a goal into phases and workstreams."""
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.4,
            max_tokens=1500,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": """You decompose user goals into executable project plans.

Available agents and their specialties:
- job_scout: Finding and saving job opportunities
- resume_tailor: Customizing resumes for specific roles
- application_prep: Drafting cover letters and applications
- outreach: Networking messages and recruiter outreach
- interview_prep: Interview preparation and mock questions
- market_intel: Industry news, trends, salary data
- salary_tracker: Compensation research and negotiation
- network_mapper: Finding contacts at target companies
- pathfinder: General research and coordination

Return JSON with this structure:
{
  "lead_agent": "agent_name",
  "phases": [{"name": "Phase Name", "status": "pending", "order": 0}],
  "workstreams": [
    {
      "title": "Clear workstream title",
      "description": "What this workstream produces",
      "agent": "best_agent_for_this",
      "phase": "Phase Name"
    }
  ]
}

Rules:
- 2-4 phases maximum
- 2-6 workstreams total
- Assign the most relevant agent to each workstream
- Workstream titles should be clear and actionable"""},
                {"role": "user", "content": f"Decompose this goal into a project plan:\n\n{goal}"},
            ],
        )

        return json.loads(completion.choices[0].message.content)

    except Exception as e:
        logger.warning("Goal decomposition failed: %s", e)
        # Fallback plan
        return {
            "lead_agent": "pathfinder",
            "phases": [
                {"name": "Research", "status": "pending", "order": 0},
                {"name": "Execute", "status": "pending", "order": 1},
            ],
            "workstreams": [
                {
                    "title": "Research and plan",
                    "description": f"Research: {goal}",
                    "agent": "pathfinder",
                    "phase": "Research",
                },
                {
                    "title": "Execute and deliver",
                    "description": f"Execute: {goal}",
                    "agent": "pathfinder",
                    "phase": "Execute",
                },
            ],
        }
