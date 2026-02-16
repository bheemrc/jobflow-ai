"""DNA database tables and CRUD operations.

Tables: agent_genes, agent_mutations, agent_pulse_config, agent_pulse_log.
All operations use asyncpg via the shared connection pool.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.db import get_conn

logger = logging.getLogger(__name__)


# ── Migrations ──

async def run_migrations(conn) -> None:
    """Create DNA tables. Called from app.db._run_migrations()."""

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_genes (
            id SERIAL PRIMARY KEY,
            agent TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT '',
            gene_type TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            confidence FLOAT8 NOT NULL DEFAULT 0.5,
            reinforcement_count INT NOT NULL DEFAULT 0,
            decay_rate FLOAT8 NOT NULL DEFAULT 0.03,
            parent_gene_id INT REFERENCES agent_genes(id),
            source TEXT NOT NULL DEFAULT '',
            tags JSONB DEFAULT '[]',
            embedding FLOAT8[],
            expressed BOOLEAN NOT NULL DEFAULT FALSE,
            archived BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_reinforced_at TIMESTAMPTZ
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_genes_agent_user
        ON agent_genes(agent, user_id)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_genes_type
        ON agent_genes(gene_type)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_genes_confidence
        ON agent_genes(confidence DESC)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_genes_active
        ON agent_genes(agent, user_id, archived) WHERE archived = FALSE
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_mutations (
            id SERIAL PRIMARY KEY,
            gene_id INT NOT NULL REFERENCES agent_genes(id) ON DELETE CASCADE,
            agent TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT '',
            enzyme TEXT NOT NULL,
            old_confidence FLOAT8 NOT NULL DEFAULT 0,
            new_confidence FLOAT8 NOT NULL DEFAULT 0,
            reason TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_mutations_gene
        ON agent_mutations(gene_id)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_pulse_config (
            agent TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT '',
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            frequency_minutes INT NOT NULL DEFAULT 60,
            active_hours_start INT NOT NULL DEFAULT 6,
            active_hours_end INT NOT NULL DEFAULT 22,
            cooldown_minutes INT NOT NULL DEFAULT 5,
            max_actions_per_pulse INT NOT NULL DEFAULT 3,
            expression_bias FLOAT8 NOT NULL DEFAULT 0.5,
            PRIMARY KEY (agent, user_id)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_pulse_log (
            id SERIAL PRIMARY KEY,
            agent TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT '',
            genes_decayed INT NOT NULL DEFAULT 0,
            genes_reinforced INT NOT NULL DEFAULT 0,
            genes_expressed INT NOT NULL DEFAULT 0,
            genes_merged INT NOT NULL DEFAULT 0,
            genes_spliced INT NOT NULL DEFAULT 0,
            actions_taken JSONB DEFAULT '[]',
            duration_ms INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_pulse_log_agent
        ON agent_pulse_log(agent, user_id, created_at DESC)
    """)

    # Knowledge feeds table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_feeds (
            id SERIAL PRIMARY KEY,
            agent TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT '',
            feed_type TEXT NOT NULL,
            name TEXT NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            config JSONB DEFAULT '{}',
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            last_checked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    logger.info("DNA tables migration complete")


# ── Gene CRUD ──

async def create_gene(
    agent: str,
    gene_type: str,
    name: str,
    description: str = "",
    content: str = "",
    confidence: float = 0.5,
    decay_rate: float = 0.03,
    parent_gene_id: int | None = None,
    source: str = "",
    tags: list[str] | None = None,
    embedding: list[float] | None = None,
    user_id: str = "",
) -> dict:
    """Create a new gene and return the full record."""
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO agent_genes
                (agent, user_id, gene_type, name, description, content,
                 confidence, decay_rate, parent_gene_id, source, tags, embedding)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12)
            RETURNING *
        """,
            agent, user_id, gene_type, name, description, content,
            confidence, decay_rate, parent_gene_id, source,
            json.dumps(tags or []), embedding,
        )
        return _serialize_gene(dict(row))


async def get_gene(gene_id: int, user_id: str = "") -> dict | None:
    """Get a single gene by ID."""
    async with get_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM agent_genes WHERE id = $1 AND user_id = $2",
            gene_id, user_id,
        )
        return _serialize_gene(dict(row)) if row else None


async def get_genome(agent: str, user_id: str = "", include_archived: bool = False) -> list[dict]:
    """Get all active genes for an agent, ordered by confidence DESC."""
    async with get_conn() as conn:
        if include_archived:
            rows = await conn.fetch("""
                SELECT * FROM agent_genes
                WHERE agent = $1 AND user_id = $2
                ORDER BY confidence DESC
            """, agent, user_id)
        else:
            rows = await conn.fetch("""
                SELECT * FROM agent_genes
                WHERE agent = $1 AND user_id = $2 AND archived = FALSE
                ORDER BY confidence DESC
            """, agent, user_id)
        return [_serialize_gene(dict(r)) for r in rows]


async def update_gene(
    gene_id: int,
    user_id: str = "",
    **kwargs: Any,
) -> dict | None:
    """Update gene fields. Only provided kwargs are updated."""
    if not kwargs:
        return await get_gene(gene_id, user_id)

    set_parts = []
    params: list[Any] = []
    idx = 1
    for key, val in kwargs.items():
        if key == "tags":
            set_parts.append(f"tags = ${idx}::jsonb")
            params.append(json.dumps(val))
        elif key == "embedding":
            set_parts.append(f"embedding = ${idx}")
            params.append(val)
        else:
            set_parts.append(f"{key} = ${idx}")
            params.append(val)
        idx += 1

    set_parts.append(f"updated_at = NOW()")
    params.extend([gene_id, user_id])

    query = f"""
        UPDATE agent_genes SET {', '.join(set_parts)}
        WHERE id = ${idx} AND user_id = ${idx + 1}
        RETURNING *
    """
    async with get_conn() as conn:
        row = await conn.fetchrow(query, *params)
        return _serialize_gene(dict(row)) if row else None


async def archive_gene(gene_id: int, user_id: str = "") -> None:
    """Soft-delete a gene by archiving it."""
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE agent_genes SET archived = TRUE, updated_at = NOW() WHERE id = $1 AND user_id = $2",
            gene_id, user_id,
        )


# ── Mutation Log ──

async def log_mutation(
    gene_id: int,
    agent: str,
    enzyme: str,
    old_confidence: float,
    new_confidence: float,
    reason: str = "",
    user_id: str = "",
) -> int:
    """Record a gene mutation event."""
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO agent_mutations
                (gene_id, agent, user_id, enzyme, old_confidence, new_confidence, reason)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """, gene_id, agent, user_id, enzyme, old_confidence, new_confidence, reason)
        return row["id"]


async def get_gene_lineage(gene_id: int, user_id: str = "") -> list[dict]:
    """Get mutation history for a gene, oldest first."""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM agent_mutations
            WHERE gene_id = $1 AND user_id = $2
            ORDER BY created_at ASC
        """, gene_id, user_id)
        result = []
        for r in rows:
            d = dict(r)
            if "created_at" in d and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            result.append(d)
        return result


# ── Pulse Config ──

async def get_pulse_config(agent: str, user_id: str = "") -> dict | None:
    """Get pulse configuration for an agent."""
    async with get_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM agent_pulse_config WHERE agent = $1 AND user_id = $2",
            agent, user_id,
        )
        return dict(row) if row else None


async def upsert_pulse_config(
    agent: str,
    user_id: str = "",
    **kwargs: Any,
) -> None:
    """Create or update pulse config for an agent."""
    defaults = {
        "enabled": True,
        "frequency_minutes": 60,
        "active_hours_start": 6,
        "active_hours_end": 22,
        "cooldown_minutes": 5,
        "max_actions_per_pulse": 3,
        "expression_bias": 0.5,
    }
    config = {**defaults, **kwargs}
    async with get_conn() as conn:
        await conn.execute("""
            INSERT INTO agent_pulse_config
                (agent, user_id, enabled, frequency_minutes, active_hours_start,
                 active_hours_end, cooldown_minutes, max_actions_per_pulse, expression_bias)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (agent, user_id) DO UPDATE SET
                enabled = $3, frequency_minutes = $4, active_hours_start = $5,
                active_hours_end = $6, cooldown_minutes = $7,
                max_actions_per_pulse = $8, expression_bias = $9
        """,
            agent, user_id, config["enabled"], config["frequency_minutes"],
            config["active_hours_start"], config["active_hours_end"],
            config["cooldown_minutes"], config["max_actions_per_pulse"],
            config["expression_bias"],
        )


# ── Pulse Log ──

async def create_pulse_log(
    agent: str,
    user_id: str = "",
    genes_decayed: int = 0,
    genes_reinforced: int = 0,
    genes_expressed: int = 0,
    genes_merged: int = 0,
    genes_spliced: int = 0,
    actions_taken: list[str] | None = None,
    duration_ms: int = 0,
) -> int:
    """Log a pulse cycle execution."""
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO agent_pulse_log
                (agent, user_id, genes_decayed, genes_reinforced, genes_expressed,
                 genes_merged, genes_spliced, actions_taken, duration_ms)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
            RETURNING id
        """,
            agent, user_id, genes_decayed, genes_reinforced, genes_expressed,
            genes_merged, genes_spliced, json.dumps(actions_taken or []), duration_ms,
        )
        return row["id"]


async def get_pulse_logs(
    agent: str,
    user_id: str = "",
    limit: int = 20,
) -> list[dict]:
    """Get recent pulse logs for an agent."""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM agent_pulse_log
            WHERE agent = $1 AND user_id = $2
            ORDER BY created_at DESC
            LIMIT $3
        """, agent, user_id, limit)
        result = []
        for r in rows:
            d = dict(r)
            if "created_at" in d and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            if "actions_taken" in d and isinstance(d["actions_taken"], str):
                try:
                    d["actions_taken"] = json.loads(d["actions_taken"])
                except Exception:
                    pass
            result.append(d)
        return result


# ── Batch Operations ──

async def decay_all_genes(agent: str, user_id: str = "") -> int:
    """Apply decay to all active genes for an agent. Returns count of decayed genes.

    Pure SQL for performance — no need to load genes into Python.
    """
    async with get_conn() as conn:
        result = await conn.execute("""
            UPDATE agent_genes
            SET confidence = GREATEST(0.0, confidence - decay_rate),
                updated_at = NOW()
            WHERE agent = $1 AND user_id = $2 AND archived = FALSE
              AND confidence > 0.0
        """, agent, user_id)
        # result is like "UPDATE 42"
        try:
            return int(result.split()[-1])
        except (ValueError, IndexError):
            return 0


async def get_genes_by_type(
    agent: str,
    gene_type: str,
    user_id: str = "",
    min_confidence: float = 0.0,
    limit: int = 50,
) -> list[dict]:
    """Get genes of a specific type for an agent."""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM agent_genes
            WHERE agent = $1 AND user_id = $2 AND gene_type = $3
              AND archived = FALSE AND confidence >= $4
            ORDER BY confidence DESC
            LIMIT $5
        """, agent, user_id, gene_type, min_confidence, limit)
        return [_serialize_gene(dict(r)) for r in rows]


async def find_similar_genes(
    agent: str,
    user_id: str = "",
    min_confidence: float = 0.3,
) -> list[dict]:
    """Get all active genes with embeddings for similarity comparison."""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM agent_genes
            WHERE agent = $1 AND user_id = $2 AND archived = FALSE
              AND embedding IS NOT NULL AND confidence >= $3
            ORDER BY confidence DESC
        """, agent, user_id, min_confidence)
        return [_serialize_gene(dict(r)) for r in rows]


async def get_all_agents_with_genes(user_id: str = "") -> list[str]:
    """Get list of all agents that have genes."""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT DISTINCT agent FROM agent_genes
            WHERE user_id = $1 AND archived = FALSE
        """, user_id)
        return [r["agent"] for r in rows]


# ── Serialization ──

def _serialize_gene(d: dict) -> dict:
    """Normalize a gene dict for JSON serialization."""
    for key in ("created_at", "updated_at", "last_reinforced_at"):
        if key in d and hasattr(d[key], "isoformat"):
            d[key] = d[key].isoformat() if d[key] else None
    if "tags" in d and isinstance(d["tags"], str):
        try:
            d["tags"] = json.loads(d["tags"])
        except Exception:
            pass
    # Convert embedding from list to None for API responses (too large)
    if "embedding" in d and d["embedding"]:
        d["has_embedding"] = True
        del d["embedding"]
    else:
        d["has_embedding"] = False
        d.pop("embedding", None)
    return d
