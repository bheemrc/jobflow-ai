"""Resume storage backed by PostgreSQL.

Resumes are stored in the `resumes` table so they persist across deployments
(Railway containers have ephemeral filesystems).
"""

from __future__ import annotations

import uuid

from app.db import get_conn


async def save_resume(text: str, user_id: str, resume_id: str | None = None) -> str:
    """Save resume text to the database. Returns the resume ID."""
    if not resume_id:
        resume_id = uuid.uuid4().hex[:12]
    async with get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO resumes (id, user_id, content)
            VALUES ($1, $2, $3)
            ON CONFLICT (id, user_id) DO UPDATE SET content = $3, updated_at = NOW()
            """,
            resume_id, user_id, text,
        )
    return resume_id


async def get_resume(resume_id: str, user_id: str) -> str | None:
    """Retrieve resume text by ID. Returns None if not found."""
    async with get_conn() as conn:
        row = await conn.fetchrow(
            "SELECT content FROM resumes WHERE id = $1 AND user_id = $2",
            resume_id, user_id,
        )
    return row["content"] if row else None


async def delete_resume(resume_id: str, user_id: str) -> bool:
    """Delete a resume by ID. Returns True if deleted."""
    async with get_conn() as conn:
        result = await conn.execute(
            "DELETE FROM resumes WHERE id = $1 AND user_id = $2",
            resume_id, user_id,
        )
    return result.split()[-1] != "0"


async def list_resumes(user_id: str) -> list[str]:
    """List all resume IDs for a user."""
    async with get_conn() as conn:
        rows = await conn.fetch(
            "SELECT id FROM resumes WHERE user_id = $1 ORDER BY created_at DESC",
            user_id,
        )
    return [row["id"] for row in rows]
