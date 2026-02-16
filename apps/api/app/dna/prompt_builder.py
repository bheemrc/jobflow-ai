"""Format genome context for bot system prompts.

Builds a concise genome summary (~1500 tokens max) that gets injected
into the bot's system prompt so its behavior reflects learned knowledge.
"""

from __future__ import annotations

import logging
from typing import Sequence

from app.dna import db as dna_db
from app.dna.models import EXPRESSION_THRESHOLDS, EXPRESSION_MIN_REINFORCEMENTS

logger = logging.getLogger(__name__)

# Approximate token budget for genome context
MAX_GENOME_TOKENS = 1500
# Rough chars-per-token estimate
CHARS_PER_TOKEN = 4
MAX_GENOME_CHARS = MAX_GENOME_TOKENS * CHARS_PER_TOKEN


async def build_genome_prompt(agent: str, user_id: str = "") -> str:
    """Build a genome context string for injection into bot system prompts.

    Includes:
    - Top 5 active beliefs (shape voice/framing)
    - Active goals (what to pursue)
    - Recent insights (analysis to reference)
    - Key facts (verified knowledge)
    - Active hunches (things to verify)

    Capped at ~1500 tokens.
    """
    genome = await dna_db.get_genome(agent, user_id)
    if not genome:
        return ""

    sections: list[str] = []
    total_chars = 0

    # Active goals (highest priority — what to pursue)
    goals = [
        g for g in genome
        if g["gene_type"] == "GOAL" and g["confidence"] >= EXPRESSION_THRESHOLDS["GOAL"]
    ][:3]
    if goals:
        lines = ["## Active Goals"]
        for g in goals:
            line = f"- {g['name']} (confidence: {g['confidence']:.0%})"
            if g.get("description"):
                line += f" — {g['description'][:80]}"
            lines.append(line)
        section = "\n".join(lines)
        total_chars += len(section)
        sections.append(section)

    # Core beliefs (shape voice and framing)
    beliefs = [
        g for g in genome
        if g["gene_type"] == "BELIEF"
        and g["confidence"] >= EXPRESSION_THRESHOLDS["BELIEF"]
        and g["reinforcement_count"] >= EXPRESSION_MIN_REINFORCEMENTS["BELIEF"]
    ][:5]
    if beliefs:
        lines = ["## Core Beliefs"]
        for g in beliefs:
            line = f"- {g['name']} (reinforced {g['reinforcement_count']}x)"
            lines.append(line)
        section = "\n".join(lines)
        if total_chars + len(section) < MAX_GENOME_CHARS:
            total_chars += len(section)
            sections.append(section)

    # Key insights
    insights = [
        g for g in genome
        if g["gene_type"] == "INSIGHT" and g["confidence"] >= EXPRESSION_THRESHOLDS["INSIGHT"]
    ][:3]
    if insights:
        lines = ["## Recent Insights"]
        for g in insights:
            line = f"- {g['name']}"
            if g.get("description"):
                line += f": {g['description'][:100]}"
            lines.append(line)
        section = "\n".join(lines)
        if total_chars + len(section) < MAX_GENOME_CHARS:
            total_chars += len(section)
            sections.append(section)

    # Key facts
    facts = [
        g for g in genome
        if g["gene_type"] == "FACT" and g["confidence"] >= EXPRESSION_THRESHOLDS["FACT"]
    ][:5]
    if facts:
        lines = ["## Known Facts"]
        for g in facts:
            lines.append(f"- {g['name']}")
        section = "\n".join(lines)
        if total_chars + len(section) < MAX_GENOME_CHARS:
            total_chars += len(section)
            sections.append(section)

    # Skills
    skills = [
        g for g in genome
        if g["gene_type"] == "SKILL"
        and g["confidence"] >= EXPRESSION_THRESHOLDS["SKILL"]
        and g["reinforcement_count"] >= EXPRESSION_MIN_REINFORCEMENTS["SKILL"]
    ][:3]
    if skills:
        lines = ["## Skills"]
        for g in skills:
            lines.append(f"- {g['name']}")
        section = "\n".join(lines)
        if total_chars + len(section) < MAX_GENOME_CHARS:
            total_chars += len(section)
            sections.append(section)

    # Hunches (things to investigate)
    hunches = [
        g for g in genome
        if g["gene_type"] == "HUNCH" and g["confidence"] >= EXPRESSION_THRESHOLDS["HUNCH"]
    ][:2]
    if hunches:
        lines = ["## Hunches to Verify"]
        for g in hunches:
            lines.append(f"- {g['name']}: {g.get('description', '')[:80]}")
        section = "\n".join(lines)
        if total_chars + len(section) < MAX_GENOME_CHARS:
            sections.append(section)

    if not sections:
        return ""

    header = "# Your Genome (learned knowledge)\nUse this knowledge to inform your work:\n"
    return header + "\n\n".join(sections)
