"""Dynamic specialist agent creation with LLM-generated seed genes.

When a Katalyst reaction needs a specialist that doesn't exist,
this module creates a temporary agent with appropriate DNA.
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


async def spawn_specialist(
    role: str,
    context: str = "",
    reaction_id: int | None = None,
    user_id: str = "",
) -> dict:
    """Spawn a dynamic specialist agent for a Katalyst workstream.

    Creates seed genes appropriate for the role and registers the agent.
    Returns agent info dict.
    """
    agent_name = _make_agent_name(role)

    # Generate seed genes for the specialist
    seed_genes = await _generate_seed_genes(role, context)

    # Seed genes into DNA system
    try:
        from app.dna import db as dna_db
        from app.dna.models import DECAY_RATES

        for g in seed_genes:
            gene_type = g.get("type", "SKILL")
            await dna_db.create_gene(
                agent=agent_name,
                gene_type=gene_type,
                name=g.get("name", ""),
                description=g.get("description", ""),
                confidence=g.get("confidence", 0.6),
                decay_rate=DECAY_RATES.get(gene_type, 0.03),
                source=f"spawned:reaction_{reaction_id}" if reaction_id else "spawned",
                tags=g.get("tags", []),
                user_id=user_id,
            )
    except Exception as e:
        logger.warning("Failed to seed genes for specialist %s: %s", agent_name, e)

    return {
        "agent": agent_name,
        "role": role,
        "seed_genes": len(seed_genes),
        "reaction_id": reaction_id,
    }


async def _generate_seed_genes(role: str, context: str = "") -> list[dict]:
    """Use LLM to generate appropriate seed genes for a specialist role."""
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": """Generate 3-5 seed genes for a specialist AI agent.

Each gene should have:
- name: Plain English name (max 50 chars)
- type: SKILL or GOAL or BELIEF
- description: What this means for the agent
- confidence: 0.5-0.8
- tags: 2-3 relevant tags

Return: {"genes": [...]}"""},
                {"role": "user", "content": f"Role: {role}\nContext: {context[:500]}"},
            ],
        )

        data = json.loads(completion.choices[0].message.content)
        return data.get("genes", [])[:5]
    except Exception as e:
        logger.debug("Seed gene generation failed: %s", e)
        return [
            {"name": f"Specialized in {role}", "type": "SKILL",
             "description": f"Core competency in {role}", "confidence": 0.6, "tags": [role]},
        ]


def _make_agent_name(role: str) -> str:
    """Create a valid agent name from a role description."""
    import re
    name = re.sub(r"[^a-z0-9]+", "_", role.lower().strip())[:30]
    name = name.strip("_")
    return f"specialist_{name}" if name else "specialist"
