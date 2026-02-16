"""Cross-agent gene splicing from timeline posts.

When an agent posts to the timeline, other agents can "splice" useful
knowledge from that post into their own genome at reduced trust (0.5x).

This enables organic knowledge transfer between agents without
direct coupling.
"""

from __future__ import annotations

import logging

from app.dna import db as dna_db
from app.dna.enzymes import splice, reinforce
from app.dna.gene_extractor import extract_genes_from_output

logger = logging.getLogger(__name__)


async def splice_from_timeline_post(
    post: dict,
    target_agents: list[str] | None = None,
    user_id: str = "",
) -> int:
    """Extract genes from a timeline post and splice into other agents.

    Args:
        post: Timeline post dict with 'agent', 'content', 'context'
        target_agents: Which agents should absorb. None = all DNA-enabled agents.
        user_id: User scope

    Returns:
        Number of genes spliced
    """
    source_agent = post.get("agent", "")
    content = post.get("content", "")

    if not content or len(content) < 30:
        return 0

    if source_agent == "user":
        return 0  # Don't splice user posts (they become dossier genes instead)

    # Extract genes from the post content
    extracted = await extract_genes_from_output(
        agent=source_agent,
        output=content,
        run_context={"source": "timeline_post", "post_id": post.get("id")},
    )

    if not extracted:
        return 0

    # Determine target agents
    if target_agents is None:
        target_agents = await _get_dna_enabled_agents(source_agent, user_id)

    splice_count = 0
    for target in target_agents:
        if target == source_agent:
            continue  # Don't splice into self

        for gene_data in extracted:
            # Check if target already has a similar gene
            existing = await _find_existing_gene(target, gene_data["name"], user_id)
            if existing:
                # Reinforce existing gene instead of creating duplicate
                await reinforce(
                    existing["id"],
                    reason=f"Reinforced by {source_agent}'s post",
                    boost=0.05,
                    user_id=user_id,
                )
            else:
                # Splice new gene at 0.5x confidence
                await splice(
                    source_agent=source_agent,
                    target_agent=target,
                    gene_name=gene_data["name"],
                    gene_description=gene_data.get("description", ""),
                    gene_type=gene_data.get("type", "INSIGHT"),
                    content=content[:300],
                    source_confidence=gene_data.get("confidence", 0.5),
                    tags=gene_data.get("tags", []),
                    user_id=user_id,
                )
                splice_count += 1

    if splice_count > 0:
        logger.info(
            "Spliced %d genes from %s post to %d agents",
            splice_count, source_agent, len(target_agents),
        )

    return splice_count


async def _get_dna_enabled_agents(exclude: str, user_id: str = "") -> list[str]:
    """Get all agents with DNA enabled, excluding the source."""
    try:
        from app.bot_config import get_bots_config
        config = get_bots_config()
        return [
            name for name, cfg in config.bots.items()
            if cfg.dna.enabled and name != exclude
        ]
    except Exception:
        return []


async def _find_existing_gene(agent: str, gene_name: str, user_id: str = "") -> dict | None:
    """Check if agent already has a gene with a similar name."""
    try:
        genome = await dna_db.get_genome(agent, user_id)
        name_lower = gene_name.lower()
        for gene in genome:
            if gene.get("name", "").lower() == name_lower:
                return gene
        return None
    except Exception:
        return None
