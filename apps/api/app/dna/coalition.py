"""Coalition detection via tag overlap + embedding clustering.

Identifies groups of agents with overlapping knowledge areas.
Coalitions can be used for collaborative workstreams and
cross-pollination of genes.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from app.dna import db as dna_db

logger = logging.getLogger(__name__)


async def detect_coalitions(user_id: str = "", min_overlap: int = 3) -> list[dict]:
    """Find groups of agents with significant tag overlap.

    Returns list of coalition dicts with members and shared tags.
    """
    all_agents = await dna_db.get_all_agents_with_genes(user_id)
    if len(all_agents) < 2:
        return []

    # Collect tags per agent
    agent_tags: dict[str, set[str]] = {}
    for agent in all_agents:
        genome = await dna_db.get_genome(agent, user_id)
        tags: set[str] = set()
        for gene in genome:
            for tag in gene.get("tags", []):
                tags.add(tag.lower())
        agent_tags[agent] = tags

    # Find overlapping pairs
    agents = list(agent_tags.keys())
    coalitions: list[dict] = []
    seen_pairs: set[frozenset[str]] = set()

    for i in range(len(agents)):
        for j in range(i + 1, len(agents)):
            pair = frozenset({agents[i], agents[j]})
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            shared = agent_tags[agents[i]] & agent_tags[agents[j]]
            if len(shared) >= min_overlap:
                coalitions.append({
                    "members": [agents[i], agents[j]],
                    "shared_tags": sorted(shared),
                    "overlap_count": len(shared),
                })

    # Merge overlapping coalitions (if A-B and B-C share tags, merge)
    merged = _merge_coalitions(coalitions)
    return sorted(merged, key=lambda c: -c["overlap_count"])


def _merge_coalitions(coalitions: list[dict]) -> list[dict]:
    """Merge coalitions that share members."""
    if not coalitions:
        return []

    # Group by shared members
    groups: list[dict] = []
    for c in coalitions:
        members = set(c["members"])
        merged = False
        for group in groups:
            if members & set(group["members"]):
                group["members"] = sorted(set(group["members"]) | members)
                group["shared_tags"] = sorted(set(group["shared_tags"]) & set(c["shared_tags"]))
                group["overlap_count"] = len(group["shared_tags"])
                merged = True
                break
        if not merged:
            groups.append({
                "members": sorted(members),
                "shared_tags": c["shared_tags"],
                "overlap_count": c["overlap_count"],
            })

    return groups
