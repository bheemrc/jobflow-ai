"""DNA (agent genome) endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request

from app.user_context import get_user_id

router = APIRouter(prefix="/dna", tags=["dna"])


@router.get("/{agent}/genome")
async def get_agent_genome(agent: str, user_id: str = Depends(get_user_id)):
    """Get the full genome for an agent."""
    from app.dna import db as dna_db
    genome = await dna_db.get_genome(agent, user_id)
    # Group by type for readability
    by_type: dict[str, list] = {}
    for gene in genome:
        gt = gene.get("gene_type", "FACT")
        by_type.setdefault(gt, []).append(gene)
    return {"agent": agent, "total_genes": len(genome), "genes": genome, "by_type": by_type}


@router.get("/{agent}/pulse-log")
async def get_agent_pulse_log(
    agent: str,
    limit: int = 20,
    user_id: str = Depends(get_user_id),
):
    """Get recent pulse logs for an agent."""
    from app.dna import db as dna_db
    logs = await dna_db.get_pulse_logs(agent, user_id, limit)
    return {"agent": agent, "logs": logs}


@router.get("/{agent}/gene/{gene_id}/lineage")
async def get_gene_lineage_endpoint(agent: str, gene_id: int, user_id: str = Depends(get_user_id)):
    """Get the mutation history (lineage) for a specific gene."""
    from app.dna import db as dna_db
    gene = await dna_db.get_gene(gene_id, user_id)
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")
    lineage = await dna_db.get_gene_lineage(gene_id, user_id)
    return {"gene": gene, "lineage": lineage}


@router.post("/{agent}/gene")
async def inject_gene(agent: str, request: Request, user_id: str = Depends(get_user_id)):
    """Admin: Manually inject a gene into an agent's genome."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Gene name is required")

    from app.dna import db as dna_db
    from app.dna.models import DECAY_RATES

    gene_type = body.get("type", "FACT").upper()
    valid_types = {"FACT", "BELIEF", "SKILL", "INSIGHT", "GOAL", "HUNCH"}
    if gene_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid gene type: {gene_type}")

    gene = await dna_db.create_gene(
        agent=agent,
        gene_type=gene_type,
        name=name,
        description=body.get("description", ""),
        content=body.get("content", ""),
        confidence=max(0.1, min(1.0, float(body.get("confidence", 0.5)))),
        decay_rate=DECAY_RATES.get(gene_type, 0.03),
        source="admin_inject",
        tags=body.get("tags", []),
        user_id=user_id,
    )

    # Write updated genome YAML
    from app.dna.genome_writer import write_genome_yaml
    await write_genome_yaml(agent, user_id)

    return {"ok": True, "gene": gene}


@router.post("/{agent}/pulse")
async def trigger_pulse(agent: str, user_id: str = Depends(get_user_id)):
    """Manually trigger a pulse cycle for an agent (returns immediately)."""
    from app.dna.pulse import run_pulse
    log = await run_pulse(agent, user_id)
    return {
        "ok": True,
        "agent": agent,
        "genes_decayed": log.genes_decayed,
        "genes_merged": log.genes_merged,
        "genes_expressed": log.genes_expressed,
        "genes_spliced": log.genes_spliced,
        "actions_taken": log.actions_taken,
        "duration_ms": log.duration_ms,
    }


@router.get("/status")
async def dna_status(user_id: str = Depends(get_user_id)):
    """Full DNA system status — all agents, genes, pulse logs, genome YAML paths."""
    from app.dna import db as dna_db

    agents = await dna_db.get_all_agents_with_genes(user_id)
    result = []
    for agent in agents:
        genome = await dna_db.get_genome(agent, user_id)
        pulse_config = await dna_db.get_pulse_config(agent, user_id)
        pulse_logs = await dna_db.get_pulse_logs(agent, user_id, limit=3)

        # Check for YAML file
        yaml_path = os.path.join("genomes", f"{agent}.yaml")
        yaml_exists = os.path.exists(yaml_path)

        by_type: dict[str, list] = {}
        for g in genome:
            gt = g.get("gene_type", "FACT")
            by_type.setdefault(gt, []).append({
                "id": g["id"],
                "name": g["name"],
                "confidence": g.get("confidence", 0),
                "reinforcements": g.get("reinforcements", 0),
                "source": g.get("source", ""),
            })

        result.append({
            "agent": agent,
            "total_genes": len(genome),
            "by_type": {k: {"count": len(v), "genes": v} for k, v in by_type.items()},
            "pulse_config": pulse_config,
            "recent_pulse_logs": pulse_logs,
            "yaml_file": yaml_path if yaml_exists else None,
        })

    return {"agents": result, "total_agents": len(result)}
