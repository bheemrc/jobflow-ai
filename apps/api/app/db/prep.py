"""Prep materials CRUD queries."""

from __future__ import annotations

import json

from .core import get_conn


async def get_prep_materials(
    material_type: str | None = None,
    company: str | None = None,
    limit: int = 50,
    user_id: str = "",
) -> list[dict]:
    async with get_conn() as conn:
        conditions = ["user_id = $1"]
        params: list = [user_id]
        idx = 2
        if material_type:
            conditions.append(f"material_type = ${idx}")
            params.append(material_type)
            idx += 1
        if company:
            conditions.append(f"company = ${idx}")
            params.append(company)
            idx += 1
        where = " WHERE " + " AND ".join(conditions)
        params.append(limit)
        rows = await conn.fetch(f"""
            SELECT * FROM prep_materials{where}
            ORDER BY created_at DESC LIMIT ${idx}
        """, *params)
        result = []
        for r in rows:
            d = dict(r)
            for key in ("created_at", "updated_at", "scheduled_date"):
                if key in d and hasattr(d[key], "isoformat"):
                    d[key] = d[key].isoformat() if d[key] else None
            for jkey in ("content", "resources"):
                if jkey in d and isinstance(d[jkey], str):
                    try:
                        d[jkey] = json.loads(d[jkey])
                    except Exception:
                        pass
            result.append(d)
        return result


async def get_prep_material_by_id(material_id: int, user_id: str = "") -> dict | None:
    async with get_conn() as conn:
        row = await conn.fetchrow("SELECT * FROM prep_materials WHERE id = $1 AND user_id = $2", material_id, user_id)
        if not row:
            return None
        d = dict(row)
        for key in ("created_at", "updated_at", "scheduled_date"):
            if key in d and hasattr(d[key], "isoformat"):
                d[key] = d[key].isoformat() if d[key] else None
        for jkey in ("content", "resources"):
            if jkey in d and isinstance(d[jkey], str):
                try:
                    d[jkey] = json.loads(d[jkey])
                except Exception:
                    pass
        return d


async def create_prep_material(
    material_type: str,
    title: str,
    content: dict | str,
    company: str | None = None,
    role: str | None = None,
    agent_source: str | None = None,
    resources: list | None = None,
    scheduled_date: str | None = None,
    user_id: str = "",
) -> int:
    """Create a prep material and return its ID."""
    content_str = json.dumps(content) if isinstance(content, dict) else content
    resources_str = json.dumps(resources or [])

    async with get_conn() as conn:
        # Upsert: if same title + type exists, update content; otherwise insert
        existing = await conn.fetchrow("""
            SELECT id FROM prep_materials
            WHERE title = $1 AND material_type = $2 AND user_id = $3
        """, title, material_type, user_id)
        if existing:
            await conn.execute("""
                UPDATE prep_materials
                SET content = $1::jsonb, resources = $2::jsonb, agent_source = $3,
                    company = $4, role = $5, scheduled_date = $6, updated_at = NOW()
                WHERE id = $7
            """, content_str, resources_str, agent_source, company, role, scheduled_date, existing["id"])
            return existing["id"]
        row = await conn.fetchrow("""
            INSERT INTO prep_materials (material_type, title, company, role, agent_source, content, resources, scheduled_date, user_id)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9)
            RETURNING id
        """, material_type, title, company, role, agent_source, content_str, resources_str, scheduled_date, user_id)
        return row["id"]


async def delete_prep_material(material_id: int, user_id: str = "") -> None:
    async with get_conn() as conn:
        await conn.execute("DELETE FROM prep_materials WHERE id = $1 AND user_id = $2", material_id, user_id)
