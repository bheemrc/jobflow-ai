"""User action → dossier gene recording.

When users perform key actions (search, save, customize resume),
agents record FACT genes about user preferences and behavior.
This builds a "dossier" that informs future agent behavior.
"""

from __future__ import annotations

import logging

from app.dna import db as dna_db
from app.dna.models import DECAY_RATES

logger = logging.getLogger(__name__)

# Map user actions to which agents should learn from them
ACTION_AGENTS: dict[str, list[str]] = {
    "search": ["job_scout", "market_intel"],
    "save_job": ["job_scout", "resume_tailor", "application_prep"],
    "apply": ["application_prep", "outreach"],
    "upload_resume": ["resume_tailor"],
    "prep_material": ["interview_prep"],
    "salary_search": ["salary_tracker", "market_intel"],
    "network_action": ["network_mapper", "outreach"],
}


async def record_user_action(
    action: str,
    details: dict,
    user_id: str = "",
) -> int:
    """Record a user action as FACT genes for relevant agents.

    Returns number of genes created.
    """
    agents = ACTION_AGENTS.get(action, ["pathfinder"])
    created = 0

    gene_name, gene_desc = _action_to_gene(action, details)
    if not gene_name:
        return 0

    tags = [action] + details.get("tags", [])

    for agent in agents:
        try:
            # Check if a similar gene already exists (avoid duplicates)
            genome = await dna_db.get_genome(agent, user_id)
            existing = [g for g in genome if g.get("name") == gene_name and g.get("source", "").startswith("dossier:")]
            if existing:
                # Reinforce existing gene instead
                from app.dna.enzymes import reinforce
                await reinforce(
                    existing[0]["id"],
                    user_id,
                    reason=f"User repeated: {action}",
                    boost=0.05,
                )
            else:
                await dna_db.create_gene(
                    agent=agent,
                    gene_type="FACT",
                    name=gene_name[:60],
                    description=gene_desc,
                    confidence=0.7,
                    decay_rate=DECAY_RATES["FACT"],
                    source=f"dossier:{action}",
                    tags=tags[:5],
                    user_id=user_id,
                )
                created += 1
        except Exception as e:
            logger.debug("Dossier gene creation failed for %s/%s: %s", agent, action, e)

    return created


def _action_to_gene(action: str, details: dict) -> tuple[str, str]:
    """Convert a user action into a gene name and description."""
    if action == "search":
        query = details.get("query", "")
        if not query:
            return "", ""
        return f"User searches for: {query[:40]}", f"User performed a job search for '{query}'"

    elif action == "save_job":
        title = details.get("title", "")
        company = details.get("company", "")
        if not title:
            return "", ""
        return f"User interested in: {title[:30]}", f"User saved job '{title}' at {company}"

    elif action == "apply":
        title = details.get("title", "")
        company = details.get("company", "")
        return f"User applied to: {company[:30]}", f"User applied for '{title}' at {company}"

    elif action == "upload_resume":
        filename = details.get("filename", "resume")
        return f"User uploaded resume: {filename[:30]}", f"User uploaded or updated their resume ({filename})"

    elif action == "prep_material":
        topic = details.get("topic", "")
        return f"User prepping: {topic[:40]}", f"User requested prep material for '{topic}'"

    elif action == "salary_search":
        role = details.get("role", "")
        return f"User checking salary: {role[:30]}", f"User researched salary data for '{role}'"

    elif action == "network_action":
        company = details.get("company", "")
        return f"User networking: {company[:30]}", f"User explored networking at {company}"

    return "", ""
