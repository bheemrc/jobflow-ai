"""Six enzyme functions that modify genes.

REINFORCE — Strengthen a gene when evidence confirms it
MUTATE    — Create a new gene from contradiction, linking to parent
DECAY     — Apply time-based confidence loss (batch SQL)
MERGE     — Combine similar genes (embedding similarity > 0.85)
EXPRESS   — Evaluate if a gene should influence behavior
SPLICE    — Absorb knowledge from another agent's output at reduced trust
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.dna import db as dna_db
from app.dna.models import DECAY_RATES, Gene

logger = logging.getLogger(__name__)


async def reinforce(
    gene_id: int,
    reason: str = "",
    boost: float = 0.1,
    user_id: str = "",
) -> dict | None:
    """REINFORCE: Increase gene confidence when evidence confirms it.

    Formula: confidence += boost * (1 - current_confidence)
    This gives diminishing returns as confidence approaches 1.0.
    Also slows decay rate by 10%.
    """
    gene = await dna_db.get_gene(gene_id, user_id)
    if not gene or gene.get("archived"):
        return None

    old_conf = gene["confidence"]
    new_conf = min(1.0, old_conf + boost * (1.0 - old_conf))
    old_decay = gene.get("decay_rate", 0.03)
    new_decay = max(0.005, old_decay * 0.9)  # Slow decay by 10%, min 0.005

    updated = await dna_db.update_gene(
        gene_id, user_id,
        confidence=new_conf,
        decay_rate=new_decay,
        reinforcement_count=gene["reinforcement_count"] + 1,
        last_reinforced_at=datetime.now(timezone.utc),
    )

    await dna_db.log_mutation(
        gene_id=gene_id,
        agent=gene["agent"],
        enzyme="REINFORCE",
        old_confidence=old_conf,
        new_confidence=new_conf,
        reason=reason,
        user_id=user_id,
    )

    logger.debug("Reinforced gene %d: %.3f -> %.3f (%s)", gene_id, old_conf, new_conf, reason)
    return updated


async def mutate(
    parent_gene_id: int,
    new_name: str,
    new_description: str,
    new_content: str = "",
    reason: str = "",
    user_id: str = "",
) -> dict | None:
    """MUTATE: Create a new gene from contradiction, linking to parent.

    The parent gene's confidence is halved. The new gene starts at 0.5.
    """
    parent = await dna_db.get_gene(parent_gene_id, user_id)
    if not parent:
        return None

    # Halve parent confidence
    old_conf = parent["confidence"]
    new_parent_conf = old_conf * 0.5
    await dna_db.update_gene(parent_gene_id, user_id, confidence=new_parent_conf)
    await dna_db.log_mutation(
        gene_id=parent_gene_id,
        agent=parent["agent"],
        enzyme="MUTATE",
        old_confidence=old_conf,
        new_confidence=new_parent_conf,
        reason=f"Mutated: {reason}",
        user_id=user_id,
    )

    # Create child gene
    decay_rate = DECAY_RATES.get(parent["gene_type"], 0.03)
    child = await dna_db.create_gene(
        agent=parent["agent"],
        gene_type=parent["gene_type"],
        name=new_name,
        description=new_description,
        content=new_content,
        confidence=0.5,
        decay_rate=decay_rate,
        parent_gene_id=parent_gene_id,
        source=f"mutation:{parent_gene_id}",
        tags=parent.get("tags", []),
        user_id=user_id,
    )

    logger.info("Mutated gene %d -> new gene %d: %s", parent_gene_id, child["id"], new_name)
    return child


async def decay_all(agent: str, user_id: str = "") -> int:
    """DECAY: Apply time-based confidence loss to all active genes.

    Uses batch SQL for performance. Genes with confidence <= 0 are archived.
    """
    count = await dna_db.decay_all_genes(agent, user_id)

    # Archive genes that dropped to 0
    async with dna_db.get_conn() as conn:
        archived = await conn.execute("""
            UPDATE agent_genes
            SET archived = TRUE, updated_at = NOW()
            WHERE agent = $1 AND user_id = $2
              AND archived = FALSE AND confidence <= 0.0
        """, agent, user_id)
        try:
            archived_count = int(archived.split()[-1])
        except (ValueError, IndexError):
            archived_count = 0

    if archived_count > 0:
        logger.info("Archived %d zero-confidence genes for %s", archived_count, agent)

    return count


async def merge(
    gene_a_id: int,
    gene_b_id: int,
    user_id: str = "",
) -> dict | None:
    """MERGE: Combine two similar genes into one stronger gene.

    The surviving gene gets the higher confidence + 0.1 boost.
    The weaker gene is archived with a mutation log pointing to the survivor.
    """
    gene_a = await dna_db.get_gene(gene_a_id, user_id)
    gene_b = await dna_db.get_gene(gene_b_id, user_id)
    if not gene_a or not gene_b:
        return None

    # Keep the stronger gene
    if gene_a["confidence"] >= gene_b["confidence"]:
        survivor, absorbed = gene_a, gene_b
    else:
        survivor, absorbed = gene_b, gene_a

    old_conf = survivor["confidence"]
    new_conf = min(1.0, max(survivor["confidence"], absorbed["confidence"]) + 0.1)

    # Merge tags
    merged_tags = list(set(survivor.get("tags", []) + absorbed.get("tags", [])))

    updated = await dna_db.update_gene(
        survivor["id"], user_id,
        confidence=new_conf,
        reinforcement_count=survivor["reinforcement_count"] + absorbed["reinforcement_count"],
        tags=merged_tags,
        description=f"{survivor['description']} (merged with: {absorbed['name']})",
    )

    # Archive the absorbed gene
    await dna_db.archive_gene(absorbed["id"], user_id)

    # Log mutations
    await dna_db.log_mutation(
        gene_id=survivor["id"],
        agent=survivor["agent"],
        enzyme="MERGE",
        old_confidence=old_conf,
        new_confidence=new_conf,
        reason=f"Merged with gene {absorbed['id']}: {absorbed['name']}",
        user_id=user_id,
    )
    await dna_db.log_mutation(
        gene_id=absorbed["id"],
        agent=absorbed["agent"],
        enzyme="MERGE",
        old_confidence=absorbed["confidence"],
        new_confidence=0.0,
        reason=f"Absorbed into gene {survivor['id']}: {survivor['name']}",
        user_id=user_id,
    )

    logger.info("Merged genes %d + %d -> %d", gene_a_id, gene_b_id, survivor["id"])
    return updated


async def express(gene_id: int, user_id: str = "") -> dict | None:
    """EXPRESS: Mark a gene as expressed (actively influencing behavior).

    Only marks expression flag — actual behavior is driven by pulse.py.
    """
    gene = await dna_db.get_gene(gene_id, user_id)
    if not gene:
        return None

    # Check expression criteria from models
    from app.dna.models import EXPRESSION_THRESHOLDS, EXPRESSION_MIN_REINFORCEMENTS
    threshold = EXPRESSION_THRESHOLDS.get(gene["gene_type"], 0.5)
    min_reinf = EXPRESSION_MIN_REINFORCEMENTS.get(gene["gene_type"], 0)

    if gene["confidence"] < threshold or gene["reinforcement_count"] < min_reinf:
        return None

    if gene.get("expressed"):
        return gene  # Already expressed

    updated = await dna_db.update_gene(gene_id, user_id, expressed=True)

    await dna_db.log_mutation(
        gene_id=gene_id,
        agent=gene["agent"],
        enzyme="EXPRESS",
        old_confidence=gene["confidence"],
        new_confidence=gene["confidence"],
        reason=f"Gene expressed: {gene['name']}",
        user_id=user_id,
    )

    logger.info("Gene %d expressed: %s (conf=%.3f)", gene_id, gene["name"], gene["confidence"])
    return updated


async def splice(
    source_agent: str,
    target_agent: str,
    gene_name: str,
    gene_description: str,
    gene_type: str = "INSIGHT",
    content: str = "",
    source_confidence: float = 0.5,
    tags: list[str] | None = None,
    user_id: str = "",
) -> dict | None:
    """SPLICE: Absorb knowledge from another agent's output at 0.5x trust.

    Creates a new gene in the target agent's genome with halved confidence.
    """
    spliced_confidence = min(1.0, source_confidence * 0.5)

    gene = await dna_db.create_gene(
        agent=target_agent,
        gene_type=gene_type,
        name=gene_name,
        description=gene_description,
        content=content,
        confidence=spliced_confidence,
        decay_rate=DECAY_RATES.get(gene_type, 0.05),
        source=f"splice:{source_agent}",
        tags=tags or [],
        user_id=user_id,
    )

    await dna_db.log_mutation(
        gene_id=gene["id"],
        agent=target_agent,
        enzyme="SPLICE",
        old_confidence=0.0,
        new_confidence=spliced_confidence,
        reason=f"Spliced from {source_agent}: {gene_name}",
        user_id=user_id,
    )

    logger.info(
        "Spliced gene from %s -> %s: %s (conf=%.3f)",
        source_agent, target_agent, gene_name, spliced_confidence,
    )
    return gene
