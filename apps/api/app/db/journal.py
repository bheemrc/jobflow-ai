"""Journal entries CRUD queries."""

from __future__ import annotations

import json

from .core import get_conn


async def get_journal_entries(
    entry_type: str | None = None,
    is_read: bool | None = None,
    limit: int = 50,
    user_id: str = "",
) -> list[dict]:
    async with get_conn() as conn:
        conditions = ["user_id = $1"]
        params: list = [user_id]
        idx = 2
        if entry_type:
            conditions.append(f"entry_type = ${idx}")
            params.append(entry_type)
            idx += 1
        if is_read is not None:
            conditions.append(f"is_read = ${idx}")
            params.append(is_read)
            idx += 1
        where = " WHERE " + " AND ".join(conditions)
        params.append(limit)
        rows = await conn.fetch(f"""
            SELECT * FROM journal_entries{where}
            ORDER BY is_pinned DESC, created_at DESC LIMIT ${idx}
        """, *params)
        result = []
        for r in rows:
            d = dict(r)
            if "created_at" in d and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            if "tags" in d and isinstance(d["tags"], str):
                try:
                    d["tags"] = json.loads(d["tags"])
                except Exception:
                    pass
            result.append(d)
        return result


async def mark_journal_read(entry_id: int, user_id: str = "") -> None:
    async with get_conn() as conn:
        await conn.execute("UPDATE journal_entries SET is_read = TRUE WHERE id = $1 AND user_id = $2", entry_id, user_id)


async def pin_journal_entry(entry_id: int, pinned: bool, user_id: str = "") -> None:
    async with get_conn() as conn:
        await conn.execute("UPDATE journal_entries SET is_pinned = $1 WHERE id = $2 AND user_id = $3", pinned, entry_id, user_id)


async def create_journal_entry(
    title: str,
    content: str,
    entry_type: str = "note",
    agent: str | None = None,
    priority: str = "medium",
    tags: list | None = None,
    user_id: str = "",
) -> int:
    """Create a journal entry and return its ID."""
    tags_str = json.dumps(tags or [])

    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO journal_entries (entry_type, title, content, agent, priority, tags, user_id)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
            RETURNING id
        """, entry_type, title, content, agent, priority, tags_str, user_id)
        return row["id"]


async def delete_journal_entry(entry_id: int, user_id: str = "") -> None:
    async with get_conn() as conn:
        await conn.execute("DELETE FROM journal_entries WHERE id = $1 AND user_id = $2", entry_id, user_id)
