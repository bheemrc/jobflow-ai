"""Expression threshold evaluation and action execution per gene type.

When a gene crosses its expression threshold, it becomes "expressed" —
meaning it actively influences the agent's behavior.

Expression actions by type:
- FACT (conf > 0.5): Share as data in relevant contexts
- BELIEF (conf > 0.7, reinforced 3+): Shape voice/framing (passive)
- SKILL (conf > 0.6, reinforced 2+): Offer capability
- INSIGHT (conf > 0.7): Post analysis to timeline
- GOAL (conf > 0.3): Pursue with tools
- HUNCH (conf > 0.8): Ask another agent to verify
"""

from __future__ import annotations

import logging

from app.dna import db as dna_db
from app.dna.models import EXPRESSION_THRESHOLDS, EXPRESSION_MIN_REINFORCEMENTS

logger = logging.getLogger(__name__)


async def evaluate_expression(
    agent: str,
    user_id: str = "",
    max_actions: int = 3,
) -> list[dict]:
    """Evaluate all genes and execute expression actions.

    Returns list of actions taken.
    """
    genome = await dna_db.get_genome(agent, user_id)
    if not genome:
        return []

    actions: list[dict] = []

    for gene in genome:
        if len(actions) >= max_actions:
            break

        gene_type = gene.get("gene_type", "FACT")
        conf = gene.get("confidence", 0)
        reinforcements = gene.get("reinforcement_count", 0)
        threshold = EXPRESSION_THRESHOLDS.get(gene_type, 0.5)
        min_reinf = EXPRESSION_MIN_REINFORCEMENTS.get(gene_type, 0)

        if conf < threshold or reinforcements < min_reinf:
            continue

        if gene.get("expressed"):
            continue  # Already expressed

        # Mark as expressed
        from app.dna.enzymes import express
        await express(gene["id"], user_id)

        action = await _execute_expression(agent, gene, user_id)
        if action:
            actions.append(action)

            # Emit event so the activation router can wake matching bots
            try:
                from app.event_bus import event_bus
                await event_bus.publish({
                    "type": "pulse:gene_expressed",
                    "agent": agent,
                    "gene_type": gene_type,
                    "gene_name": gene.get("name", ""),
                    "tags": gene.get("tags", []),
                    "confidence": conf,
                })
            except Exception as e:
                logger.debug("Failed to emit gene expression event: %s", e)

    return actions


async def _execute_expression(
    agent: str,
    gene: dict,
    user_id: str = "",
) -> dict | None:
    """Execute the expression action for a gene based on its type."""
    gene_type = gene.get("gene_type", "FACT")
    gene_name = gene.get("name", "")

    try:
        if gene_type == "INSIGHT":
            # Post analysis to timeline
            return await _express_insight(agent, gene, user_id)
        elif gene_type == "HUNCH":
            # Ask another agent to verify
            return await _express_hunch(agent, gene, user_id)
        elif gene_type == "GOAL":
            # Log goal activation
            return {"type": "goal_activated", "gene": gene_name, "agent": agent}
        else:
            # FACT, BELIEF, SKILL — passive expression (affects prompts)
            return {"type": "passive_expression", "gene": gene_name, "agent": agent}

    except Exception as e:
        logger.warning("Expression action failed for gene %s: %s", gene_name, e)
        return None


async def _express_insight(agent: str, gene: dict, user_id: str = "") -> dict | None:
    """Post an insight to the timeline."""
    try:
        from app.db import create_timeline_post
        from app.event_bus import event_bus

        content = f"**Insight**: {gene['name']}"
        if gene.get("description"):
            content += f"\n\n{gene['description']}"

        post = await create_timeline_post(
            agent=agent,
            post_type="discovery",
            content=content,
            context={"source": "gene_expression", "gene_id": gene.get("id")},
            user_id=user_id,
        )

        await event_bus.publish({
            "type": "timeline_post",
            "post": post,
            "source": "dna_expression",
        })

        return {"type": "insight_posted", "gene": gene["name"], "post_id": post.get("id")}

    except Exception as e:
        logger.debug("Insight expression failed: %s", e)
        return None


async def _express_hunch(agent: str, gene: dict, user_id: str = "") -> dict | None:
    """Ask another agent to verify a hunch via timeline post."""
    try:
        from app.db import create_timeline_post
        from app.event_bus import event_bus

        # Pick a relevant agent to verify with
        verify_agent = _pick_verify_agent(agent, gene)
        content = (
            f"I have a hunch worth investigating: **{gene['name']}**\n\n"
            f"{gene.get('description', '')}\n\n"
            f"@{verify_agent} — can you look into this?"
        )

        post = await create_timeline_post(
            agent=agent,
            post_type="thought",
            content=content,
            context={"source": "gene_expression", "gene_id": gene.get("id"), "hunch_verify": True},
            user_id=user_id,
        )

        await event_bus.publish({
            "type": "timeline_post",
            "post": post,
            "source": "dna_expression",
        })

        return {"type": "hunch_verification_requested", "gene": gene["name"], "verify_agent": verify_agent}

    except Exception as e:
        logger.debug("Hunch expression failed: %s", e)
        return None


def _pick_verify_agent(requesting_agent: str, gene: dict) -> str:
    """Pick the best agent to verify a hunch based on gene tags."""
    tags = set(gene.get("tags", []))

    # Simple mapping of topic areas to agents
    agent_specialties = {
        "market_intel": {"market", "trends", "hiring", "layoffs", "industry"},
        "job_scout": {"jobs", "search", "backend", "frontend", "roles"},
        "network_mapper": {"contacts", "networking", "linkedin", "people"},
        "salary_tracker": {"salary", "compensation", "negotiation", "pay"},
        "interview_prep": {"interview", "prep", "questions", "behavioral"},
    }

    best_agent = "market_intel"  # Default fallback
    best_overlap = 0

    for agent_name, specialties in agent_specialties.items():
        if agent_name == requesting_agent:
            continue
        overlap = len(tags & specialties)
        if overlap > best_overlap:
            best_overlap = overlap
            best_agent = agent_name

    return best_agent
