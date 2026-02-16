"""Approval queries."""

from __future__ import annotations

from datetime import datetime, timezone

from .core import get_conn


async def create_approval(
    thread_id: str,
    type: str,
    title: str,
    agent: str,
    content: str,
    priority: str = "medium",
    user_id: str = "",
) -> int:
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO approvals (thread_id, type, title, agent, content, priority, user_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """, thread_id, type, title, agent, content, priority, user_id)
        return row["id"]


async def get_pending_approvals(user_id: str = "") -> list[dict]:
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT id, thread_id, type, title, agent, content, priority, status, created_at
            FROM approvals
            WHERE user_id = $1
            ORDER BY created_at DESC
        """, user_id)
        return [dict(r) for r in rows]


async def get_approval_by_id(approval_id: int) -> dict | None:
    """Fetch a single approval by ID."""
    async with get_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM approvals WHERE id = $1", approval_id
        )
        return dict(row) if row else None


async def resolve_approval(approval_id: int, decision: str) -> None:
    async with get_conn() as conn:
        await conn.execute("""
            UPDATE approvals SET status = $1, resolved_at = $2
            WHERE id = $3
        """, decision, datetime.now(timezone.utc), approval_id)


async def get_resolved_approvals_for_thread(thread_id: str) -> list[dict]:
    """Get all resolved (non-pending) approvals for a given thread."""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM approvals
            WHERE thread_id = $1 AND status != 'pending'
            ORDER BY resolved_at DESC
        """, thread_id)
        return [dict(r) for r in rows]
