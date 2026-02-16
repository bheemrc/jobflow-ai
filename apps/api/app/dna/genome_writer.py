"""Auto-write agent genome to YAML files for human readability.

After each pulse or bot execution, the agent's current genome is
written to ai-service/genomes/{agent_name}.yaml so users can
inspect and understand what each agent knows and believes.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.dna import db as dna_db

logger = logging.getLogger(__name__)

GENOMES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "genomes")


async def write_genome_yaml(agent: str, user_id: str = "") -> str | None:
    """Write the agent's current genome to a YAML file.

    Returns the file path on success, None on failure.
    """
    try:
        genes = await dna_db.get_genome(agent, user_id, include_archived=False)
        if not genes:
            return None

        # Group genes by type
        by_type: dict[str, list[dict]] = {}
        for gene in genes:
            gt = gene.get("gene_type", "FACT")
            by_type.setdefault(gt, []).append(gene)

        # Build YAML structure
        genome_data: dict = {
            "agent": agent,
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "total_genes": len(genes),
            "genes": {},
        }

        for gene_type in ["GOAL", "BELIEF", "FACT", "SKILL", "INSIGHT", "HUNCH"]:
            type_genes = by_type.get(gene_type, [])
            if not type_genes:
                continue
            genome_data["genes"][gene_type] = []
            for g in type_genes:
                entry: dict = {
                    "name": g.get("name", ""),
                    "description": g.get("description", ""),
                    "confidence": round(g.get("confidence", 0), 3),
                    "reinforcements": g.get("reinforcement_count", 0),
                    "source": g.get("source", ""),
                }
                tags = g.get("tags", [])
                if tags:
                    entry["tags"] = tags
                if g.get("expressed"):
                    entry["expressed"] = True
                genome_data["genes"][gene_type].append(entry)

        # Write to file
        os.makedirs(GENOMES_DIR, exist_ok=True)
        filepath = os.path.join(GENOMES_DIR, f"{agent}.yaml")

        yaml_content = f"# Genome for {agent}\n"
        yaml_content += f"# Auto-generated — do not edit directly\n"
        yaml_content += f"# Last updated: {genome_data['updated_at']}\n"
        yaml_content += f"# Total active genes: {genome_data['total_genes']}\n\n"
        yaml_content += yaml.dump(
            genome_data,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        )

        with open(filepath, "w") as f:
            f.write(yaml_content)

        logger.info("Wrote genome for %s: %d genes -> %s", agent, len(genes), filepath)
        return filepath

    except Exception as e:
        logger.error("Failed to write genome YAML for %s: %s", agent, e)
        return None


def read_seed_genes(agent: str) -> list[dict]:
    """Read seed gene definitions from the agent's genome YAML if it exists.

    Seed genes are used to initialize an agent's genome on first run.
    Returns list of gene dicts with keys: name, type, description, confidence, tags.
    """
    filepath = os.path.join(GENOMES_DIR, f"{agent}.yaml")
    if not os.path.exists(filepath):
        return []

    try:
        with open(filepath, "r") as f:
            data = yaml.safe_load(f)

        if not data or not isinstance(data, dict):
            return []

        seeds = []
        genes_section = data.get("genes", {})
        for gene_type, gene_list in genes_section.items():
            if not isinstance(gene_list, list):
                continue
            for g in gene_list:
                if not isinstance(g, dict) or not g.get("name"):
                    continue
                seeds.append({
                    "name": g["name"],
                    "type": gene_type,
                    "description": g.get("description", ""),
                    "confidence": g.get("confidence", 0.5),
                    "tags": g.get("tags", []),
                    "source": "seed",
                })
        return seeds
    except Exception as e:
        logger.warning("Failed to read seed genes for %s: %s", agent, e)
        return []
