"""Admin DNA management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.user_context import get_user_id

router = APIRouter(prefix="/admin/dna", tags=["admin", "dna"])


@router.get("/agents")
async def admin_list_dna_agents(user_id: str = Depends(get_user_id)):
    """List all agents that have DNA genes."""
    from app.dna import db as dna_db
    agents = await dna_db.get_all_agents_with_genes(user_id)
    result = []
    for agent in agents:
        genome = await dna_db.get_genome(agent, user_id)
        by_type: dict[str, int] = {}
        for g in genome:
            gt = g.get("gene_type", "FACT")
            by_type[gt] = by_type.get(gt, 0) + 1
        result.append({
            "agent": agent,
            "total_genes": len(genome),
            "by_type": by_type,
        })
    return {"agents": result}


@router.get("/agents/{agent}/genes")
async def admin_get_agent_genes(agent: str, user_id: str = Depends(get_user_id)):
    """Get all genes for an agent (admin view)."""
    from app.dna import db as dna_db
    genome = await dna_db.get_genome(agent, user_id)
    return {"agent": agent, "genes": genome}


@router.post("/agents/{agent}/inject-gene")
async def admin_inject_gene(agent: str, request: Request, user_id: str = Depends(get_user_id)):
    """Inject a gene into an agent's genome (admin)."""
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
    gene = await dna_db.create_gene(
        agent=agent,
        gene_type=gene_type,
        name=name,
        description=body.get("description", ""),
        content=body.get("content", ""),
        confidence=max(0.1, min(1.0, float(body.get("confidence", 0.7)))),
        decay_rate=DECAY_RATES.get(gene_type, 0.03),
        source="admin_inject",
        tags=body.get("tags", []),
        user_id=user_id,
    )

    from app.dna.genome_writer import write_genome_yaml
    await write_genome_yaml(agent, user_id)

    return {"ok": True, "gene": gene}


@router.post("/agents/{agent}/kill-pulse")
async def admin_kill_pulse(agent: str, user_id: str = Depends(get_user_id)):
    """Disable pulse for an agent by updating pulse config."""
    from app.dna import db as dna_db
    await dna_db.upsert_pulse_config(
        agent=agent,
        user_id=user_id,
        enabled=False,
    )
    return {"ok": True, "agent": agent, "pulse": "disabled"}


@router.get("/coalitions")
async def admin_get_coalitions(user_id: str = Depends(get_user_id)):
    """Detect agent coalitions based on shared knowledge."""
    from app.dna.coalition import detect_coalitions
    coalitions = await detect_coalitions(user_id)
    return {"coalitions": coalitions}
