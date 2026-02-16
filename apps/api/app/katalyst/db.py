"""Katalyst database tables and CRUD operations.

Tables: katalyst_reactions, katalyst_workstreams, katalyst_artifacts,
        katalyst_blockers, katalyst_events.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.db import get_conn

logger = logging.getLogger(__name__)


# ── Migrations ──

async def run_migrations(conn) -> None:
    """Create Katalyst tables. Called from app.db._run_migrations()."""

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS katalyst_reactions (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT '',
            goal TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'planning',
            lead_agent TEXT NOT NULL DEFAULT '',
            phases JSONB DEFAULT '[]',
            context JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_katalyst_reactions_user
        ON katalyst_reactions(user_id, status)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS katalyst_workstreams (
            id SERIAL PRIMARY KEY,
            reaction_id INT NOT NULL REFERENCES katalyst_reactions(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            agent TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            phase TEXT NOT NULL DEFAULT '',
            sort_order INT NOT NULL DEFAULT 0,
            progress INT NOT NULL DEFAULT 0,
            output TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_katalyst_workstreams_reaction
        ON katalyst_workstreams(reaction_id)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS katalyst_artifacts (
            id SERIAL PRIMARY KEY,
            reaction_id INT NOT NULL REFERENCES katalyst_reactions(id) ON DELETE CASCADE,
            workstream_id INT REFERENCES katalyst_workstreams(id),
            user_id TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            artifact_type TEXT NOT NULL DEFAULT 'document',
            content TEXT NOT NULL DEFAULT '',
            version INT NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'draft',
            agent TEXT NOT NULL DEFAULT '',
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_katalyst_artifacts_reaction
        ON katalyst_artifacts(reaction_id)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS katalyst_blockers (
            id SERIAL PRIMARY KEY,
            reaction_id INT NOT NULL REFERENCES katalyst_reactions(id) ON DELETE CASCADE,
            workstream_id INT REFERENCES katalyst_workstreams(id),
            user_id TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            severity TEXT NOT NULL DEFAULT 'medium',
            agent TEXT NOT NULL DEFAULT '',
            options JSONB DEFAULT '[]',
            auto_resolve_confidence FLOAT8 NOT NULL DEFAULT 0.0,
            resolution TEXT NOT NULL DEFAULT '',
            resolved_by TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            resolved_at TIMESTAMPTZ
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_katalyst_blockers_reaction
        ON katalyst_blockers(reaction_id)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS katalyst_events (
            id SERIAL PRIMARY KEY,
            reaction_id INT NOT NULL REFERENCES katalyst_reactions(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL DEFAULT '',
            event_type TEXT NOT NULL,
            agent TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            data JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_katalyst_events_reaction
        ON katalyst_events(reaction_id, created_at DESC)
    """)

    logger.info("Katalyst tables migration complete")


# ── Reaction CRUD ──

async def create_reaction(
    goal: str,
    lead_agent: str = "",
    phases: list[dict] | None = None,
    context: dict | None = None,
    user_id: str = "",
) -> dict:
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO katalyst_reactions (user_id, goal, lead_agent, phases, context)
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
            RETURNING *
        """, user_id, goal, lead_agent,
            json.dumps(phases or []), json.dumps(context or {}))
        return _serialize(dict(row))


async def get_reaction(reaction_id: int, user_id: str = "") -> dict | None:
    async with get_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM katalyst_reactions WHERE id = $1 AND user_id = $2",
            reaction_id, user_id)
        return _serialize(dict(row)) if row else None


async def list_reactions(user_id: str = "", status: str | None = None) -> list[dict]:
    async with get_conn() as conn:
        if status:
            rows = await conn.fetch("""
                SELECT * FROM katalyst_reactions
                WHERE user_id = $1 AND status = $2
                ORDER BY created_at DESC
            """, user_id, status)
        else:
            rows = await conn.fetch("""
                SELECT * FROM katalyst_reactions
                WHERE user_id = $1
                ORDER BY created_at DESC
            """, user_id)
        return [_serialize(dict(r)) for r in rows]


async def update_reaction(reaction_id: int, user_id: str = "", **kwargs) -> dict | None:
    if not kwargs:
        return await get_reaction(reaction_id, user_id)
    set_parts = []
    params = []
    idx = 1
    for key, val in kwargs.items():
        if key in ("phases", "context"):
            set_parts.append(f"{key} = ${idx}::jsonb")
            params.append(json.dumps(val))
        else:
            set_parts.append(f"{key} = ${idx}")
            params.append(val)
        idx += 1
    set_parts.append("updated_at = NOW()")
    params.extend([reaction_id, user_id])
    query = f"""
        UPDATE katalyst_reactions SET {', '.join(set_parts)}
        WHERE id = ${idx} AND user_id = ${idx + 1}
        RETURNING *
    """
    async with get_conn() as conn:
        row = await conn.fetchrow(query, *params)
        return _serialize(dict(row)) if row else None


# ── Workstream CRUD ──

async def create_workstream(
    reaction_id: int, title: str, description: str = "",
    agent: str = "", phase: str = "", order: int = 0, user_id: str = "",
) -> dict:
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO katalyst_workstreams
                (reaction_id, user_id, title, description, agent, phase, sort_order)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """, reaction_id, user_id, title, description, agent, phase, order)
        return _serialize(dict(row))


async def get_workstreams(reaction_id: int, user_id: str = "") -> list[dict]:
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM katalyst_workstreams
            WHERE reaction_id = $1 AND user_id = $2
            ORDER BY sort_order, created_at
        """, reaction_id, user_id)
        return [_serialize(dict(r)) for r in rows]


async def update_workstream(ws_id: int, user_id: str = "", **kwargs) -> dict | None:
    if not kwargs:
        return None
    set_parts = []
    params = []
    idx = 1
    for key, val in kwargs.items():
        set_parts.append(f"{key} = ${idx}")
        params.append(val)
        idx += 1
    set_parts.append("updated_at = NOW()")
    params.extend([ws_id, user_id])
    query = f"""
        UPDATE katalyst_workstreams SET {', '.join(set_parts)}
        WHERE id = ${idx} AND user_id = ${idx + 1}
        RETURNING *
    """
    async with get_conn() as conn:
        row = await conn.fetchrow(query, *params)
        return _serialize(dict(row)) if row else None


# ── Artifact CRUD ──

async def create_artifact(
    reaction_id: int, title: str, artifact_type: str = "document",
    content: str = "", agent: str = "", workstream_id: int | None = None,
    metadata: dict | None = None, user_id: str = "",
) -> dict:
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO katalyst_artifacts
                (reaction_id, workstream_id, user_id, title, artifact_type,
                 content, agent, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
            RETURNING *
        """, reaction_id, workstream_id, user_id, title, artifact_type,
            content, agent, json.dumps(metadata or {}))
        return _serialize(dict(row))


async def get_artifacts(reaction_id: int, user_id: str = "") -> list[dict]:
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM katalyst_artifacts
            WHERE reaction_id = $1 AND user_id = $2 AND status != 'superseded'
            ORDER BY created_at DESC
        """, reaction_id, user_id)
        return [_serialize(dict(r)) for r in rows]


async def get_artifact(artifact_id: int, user_id: str = "") -> dict | None:
    async with get_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM katalyst_artifacts WHERE id = $1 AND user_id = $2",
            artifact_id, user_id)
        return _serialize(dict(row)) if row else None


async def get_artifact_versions(artifact_id: int, user_id: str = "") -> list[dict]:
    """Get all versions of an artifact (including superseded)."""
    artifact = await get_artifact(artifact_id, user_id)
    if not artifact:
        return []
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM katalyst_artifacts
            WHERE reaction_id = $1 AND title = $2 AND user_id = $3
            ORDER BY version DESC
        """, artifact["reaction_id"], artifact["title"], user_id)
        return [_serialize(dict(r)) for r in rows]


async def update_artifact(artifact_id: int, user_id: str = "", **kwargs) -> dict | None:
    if not kwargs:
        return None
    set_parts = []
    params = []
    idx = 1
    for key, val in kwargs.items():
        if key == "metadata":
            set_parts.append(f"metadata = ${idx}::jsonb")
            params.append(json.dumps(val))
        else:
            set_parts.append(f"{key} = ${idx}")
            params.append(val)
        idx += 1
    set_parts.append("updated_at = NOW()")
    params.extend([artifact_id, user_id])
    query = f"""
        UPDATE katalyst_artifacts SET {', '.join(set_parts)}
        WHERE id = ${idx} AND user_id = ${idx + 1}
        RETURNING *
    """
    async with get_conn() as conn:
        row = await conn.fetchrow(query, *params)
        return _serialize(dict(row)) if row else None


# ── Blocker CRUD ──

async def create_blocker(
    reaction_id: int, title: str, description: str = "",
    severity: str = "medium", agent: str = "",
    options: list[dict] | None = None,
    auto_resolve_confidence: float = 0.0,
    workstream_id: int | None = None, user_id: str = "",
) -> dict:
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO katalyst_blockers
                (reaction_id, workstream_id, user_id, title, description,
                 severity, agent, options, auto_resolve_confidence)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
            RETURNING *
        """, reaction_id, workstream_id, user_id, title, description,
            severity, agent, json.dumps(options or []), auto_resolve_confidence)
        return _serialize(dict(row))


async def get_blockers(reaction_id: int, user_id: str = "", unresolved_only: bool = True) -> list[dict]:
    async with get_conn() as conn:
        if unresolved_only:
            rows = await conn.fetch("""
                SELECT * FROM katalyst_blockers
                WHERE reaction_id = $1 AND user_id = $2 AND resolved_at IS NULL
                ORDER BY severity DESC, created_at
            """, reaction_id, user_id)
        else:
            rows = await conn.fetch("""
                SELECT * FROM katalyst_blockers
                WHERE reaction_id = $1 AND user_id = $2
                ORDER BY created_at DESC
            """, reaction_id, user_id)
        return [_serialize(dict(r)) for r in rows]


async def resolve_blocker(
    blocker_id: int, resolution: str, resolved_by: str = "user", user_id: str = "",
) -> dict | None:
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            UPDATE katalyst_blockers
            SET resolution = $1, resolved_by = $2, resolved_at = NOW()
            WHERE id = $3 AND user_id = $4
            RETURNING *
        """, resolution, resolved_by, blocker_id, user_id)
        return _serialize(dict(row)) if row else None


# ── Event Feed ──

async def create_event(
    reaction_id: int, event_type: str, agent: str = "",
    message: str = "", data: dict | None = None, user_id: str = "",
) -> dict:
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO katalyst_events
                (reaction_id, user_id, event_type, agent, message, data)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            RETURNING *
        """, reaction_id, user_id, event_type, agent, message, json.dumps(data or {}))
        return _serialize(dict(row))


async def get_events(reaction_id: int, user_id: str = "", limit: int = 50) -> list[dict]:
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM katalyst_events
            WHERE reaction_id = $1 AND user_id = $2
            ORDER BY created_at DESC
            LIMIT $3
        """, reaction_id, user_id, limit)
        return [_serialize(dict(r)) for r in rows]


# ── Serialization ──

def _serialize(d: dict) -> dict:
    for key in ("created_at", "updated_at", "completed_at", "resolved_at"):
        if key in d and hasattr(d[key], "isoformat"):
            d[key] = d[key].isoformat() if d[key] else None
    for jkey in ("phases", "context", "options", "metadata", "data"):
        if jkey in d and isinstance(d[jkey], str):
            try:
                d[jkey] = json.loads(d[jkey])
            except Exception:
                pass
    return d
