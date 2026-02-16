"""7-step pulse cycle that drives agent behavior.

Steps:
1. DECAY — Apply time-based confidence loss
2. LOAD GENOME — Read current gene state
3. SCAN INPUTS — Check for new inputs (timeline posts, feeds, workstreams)
4. ENZYME PASS — Run merge on similar genes, splice from other agents
5. EXPRESSION CHECK — Evaluate which genes cross expression threshold
6. ACT/WAIT — Execute actions for expressed genes or wait
7. LOG — Record what happened, write genome YAML
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from app.dna import db as dna_db
from app.dna.enzymes import decay_all, express, merge
from app.dna.embeddings import find_most_similar
from app.dna.genome_writer import write_genome_yaml
from app.dna.models import PulseLog

logger = logging.getLogger(__name__)


async def run_pulse(agent: str, user_id: str = "") -> PulseLog:
    """Execute the full 7-step pulse cycle for an agent.

    Returns a PulseLog with stats on what happened.
    """
    start_ms = time.monotonic_ns() // 1_000_000
    log = PulseLog(agent=agent, user_id=user_id)

    try:
        # Step 1: DECAY — apply time-based confidence loss
        log.genes_decayed = await decay_all(agent, user_id)

        # Step 2: LOAD GENOME
        genome = await dna_db.get_genome(agent, user_id)
        if not genome:
            log.actions_taken.append("no_genes")
            log.duration_ms = (time.monotonic_ns() // 1_000_000) - start_ms
            await _persist_log(log)
            return log

        # Step 3: SCAN INPUTS — check for splicing opportunities, feeds, workstreams
        splice_count = await _scan_for_splices(agent, user_id)
        log.genes_spliced = splice_count

        # Check knowledge feeds for new hunches
        try:
            from app.dna.feeds import check_feeds
            feed_genes = await check_feeds(agent, user_id)
            if feed_genes:
                log.actions_taken.append(f"feed_genes:{feed_genes}")
        except Exception as e:
            logger.debug("Feed check failed for %s: %s", agent, e)

        # Check for active Katalyst workstreams assigned to this agent
        try:
            from app.katalyst.work_executor import check_agent_workstreams
            ws_advanced = await check_agent_workstreams(agent, user_id)
            if ws_advanced:
                log.actions_taken.append(f"katalyst_workstreams_advanced:{ws_advanced}")
        except Exception as e:
            logger.debug("Katalyst workstream check failed for %s: %s", agent, e)

        # Process blockers (auto-resolve high-confidence ones)
        try:
            from app.katalyst import db as kat_db
            from app.katalyst.blocker_engine import process_blockers
            reactions = await kat_db.list_reactions(user_id=user_id, status="active")
            for reaction in reactions:
                resolved = await process_blockers(reaction["id"], user_id)
                if resolved:
                    log.actions_taken.append(f"blockers_resolved:{resolved}")
        except Exception as e:
            logger.debug("Blocker processing failed for %s: %s", agent, e)

        # Step 4: ENZYME PASS — merge similar genes
        merge_count = await _merge_similar_genes(agent, user_id)
        log.genes_merged = merge_count

        # Step 5-6: EXPRESSION CHECK + ACT — evaluate thresholds and execute actions
        try:
            from app.dna.expression import evaluate_expression
            pulse_config = await dna_db.get_pulse_config(agent, user_id)
            max_actions = pulse_config.get("max_actions_per_pulse", 3) if pulse_config else 3
            actions = await evaluate_expression(agent, user_id, max_actions=max_actions)
            log.genes_expressed = len(actions)
            for action in actions:
                log.actions_taken.append(f"{action.get('type', 'unknown')}:{action.get('gene', '')}")
        except Exception as e:
            logger.debug("Expression evaluation failed for %s: %s", agent, e)

        # Step 7: LOG — record and write genome YAML
        log.duration_ms = (time.monotonic_ns() // 1_000_000) - start_ms
        await _persist_log(log)
        await write_genome_yaml(agent, user_id)

        logger.info(
            "Pulse complete for %s: decayed=%d merged=%d expressed=%d spliced=%d (%dms)",
            agent, log.genes_decayed, log.genes_merged,
            log.genes_expressed, log.genes_spliced, log.duration_ms,
        )

    except Exception as e:
        logger.error("Pulse failed for %s: %s", agent, e)
        log.actions_taken.append(f"error:{str(e)[:100]}")
        log.duration_ms = (time.monotonic_ns() // 1_000_000) - start_ms
        try:
            await _persist_log(log)
        except Exception:
            pass

    return log


async def _merge_similar_genes(agent: str, user_id: str = "") -> int:
    """Find and merge genes with embedding similarity > 0.85."""
    try:
        genes_with_embeddings = await dna_db.find_similar_genes(agent, user_id)
        if len(genes_with_embeddings) < 2:
            return 0

        # We need actual embeddings for comparison — re-fetch with embeddings
        async with dna_db.get_conn() as conn:
            rows = await conn.fetch("""
                SELECT id, embedding, gene_type FROM agent_genes
                WHERE agent = $1 AND user_id = $2 AND archived = FALSE
                  AND embedding IS NOT NULL AND confidence >= 0.3
                ORDER BY confidence DESC
            """, agent, user_id)

        if len(rows) < 2:
            return 0

        # Find pairs with similarity > 0.85
        merged_ids: set[int] = set()
        merge_count = 0
        for i in range(len(rows)):
            if rows[i]["id"] in merged_ids:
                continue
            for j in range(i + 1, len(rows)):
                if rows[j]["id"] in merged_ids:
                    continue
                if rows[i]["gene_type"] != rows[j]["gene_type"]:
                    continue
                # Compute similarity
                from app.dna.embeddings import cosine_similarity
                sim = cosine_similarity(rows[i]["embedding"], rows[j]["embedding"])
                if sim >= 0.85:
                    await merge(rows[i]["id"], rows[j]["id"], user_id)
                    merged_ids.add(rows[j]["id"])
                    merge_count += 1
                    break  # One merge per gene per pulse

        return merge_count
    except Exception as e:
        logger.debug("Merge scan failed for %s: %s", agent, e)
        return 0


async def _scan_for_splices(agent: str, user_id: str = "") -> int:
    """Scan recent timeline posts for splice opportunities."""
    try:
        from app.db import get_timeline_posts
        from app.dna.splice import splice_from_timeline_post

        # Get recent posts from other agents (last 10)
        posts = await get_timeline_posts(limit=10, user_id=user_id)
        splice_count = 0
        for post in posts:
            if post.get("agent") == agent or post.get("agent") == "user":
                continue
            # Only splice from posts not already processed
            context = post.get("context", {})
            if context.get("spliced_by", {}).get(agent):
                continue
            count = await splice_from_timeline_post(
                post=post,
                target_agents=[agent],
                user_id=user_id,
            )
            splice_count += count

        return splice_count
    except Exception as e:
        logger.debug("Splice scan failed for %s: %s", agent, e)
        return 0


async def _persist_log(log: PulseLog) -> None:
    """Save pulse log to database."""
    await dna_db.create_pulse_log(
        agent=log.agent,
        user_id=log.user_id,
        genes_decayed=log.genes_decayed,
        genes_reinforced=log.genes_reinforced,
        genes_expressed=log.genes_expressed,
        genes_merged=log.genes_merged,
        genes_spliced=log.genes_spliced,
        actions_taken=log.actions_taken,
        duration_ms=log.duration_ms,
    )
