"""Timeline posts, votes, reactions, and analytics queries."""

from __future__ import annotations

import json

from .core import get_conn


def _resolve_user_id(user_id: str) -> str:
    """Use context var if user_id not explicitly provided."""
    if not user_id:
        from app.user_context import current_user_id
        user_id = current_user_id.get()
    return user_id


async def create_timeline_post(
    agent: str,
    post_type: str,
    content: str,
    parent_id: int | None = None,
    context: dict | None = None,
    visibility: str = "all",
    user_id: str = "",
) -> dict:
    """Create a timeline post and return the full record."""
    user_id = _resolve_user_id(user_id)
    context_data = context or {}

    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO timeline_posts (agent, post_type, content, parent_id, context, visibility, user_id)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
            RETURNING *
        """, agent, post_type, content, parent_id, json.dumps(context_data), visibility, user_id)
        return _serialize_timeline_post(dict(row))


async def get_timeline_posts(
    limit: int = 50,
    offset: int = 0,
    agent: str | None = None,
    post_type: str | None = None,
    parent_id: int | None = None,
    top_level_only: bool = True,
    user_id: str = "",
) -> list[dict]:
    """Get timeline posts with optional filters. top_level_only=True excludes replies."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        # Show posts owned by this user OR system-level posts (user_id='')
        conditions = ["(user_id = $1 OR user_id = '')"]
        params: list = [user_id]
        idx = 2
        if agent:
            conditions.append(f"agent = ${idx}")
            params.append(agent)
            idx += 1
        if post_type:
            conditions.append(f"post_type = ${idx}")
            params.append(post_type)
            idx += 1
        if parent_id is not None:
            conditions.append(f"parent_id = ${idx}")
            params.append(parent_id)
            idx += 1
        elif top_level_only:
            conditions.append("parent_id IS NULL")

        where = " WHERE " + " AND ".join(conditions)
        params.extend([limit, offset])
        rows = await conn.fetch(f"""
            SELECT * FROM timeline_posts{where}
            ORDER BY pinned DESC, created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """, *params)
        return [_serialize_timeline_post(dict(r)) for r in rows]


async def get_timeline_post_by_id(post_id: int, user_id: str = "") -> dict | None:
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM timeline_posts WHERE id = $1 AND (user_id = $2 OR user_id = '')",
            post_id, user_id,
        )
        return _serialize_timeline_post(dict(row)) if row else None


async def get_timeline_replies(post_id: int, limit: int = 50, user_id: str = "") -> list[dict]:
    """Get replies to a post in chronological order (oldest first)."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM timeline_posts
            WHERE parent_id = $1 AND (user_id = $2 OR user_id = '')
            ORDER BY created_at ASC
            LIMIT $3
        """, post_id, user_id, limit)
        return [_serialize_timeline_post(dict(r)) for r in rows]


async def add_timeline_reaction(post_id: int, agent: str, emoji: str, user_id: str = "") -> dict:
    """Add or update a reaction on a post."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            UPDATE timeline_posts
            SET reactions = reactions || $1::jsonb
            WHERE id = $2 AND user_id = $3
            RETURNING *
        """, json.dumps({agent: emoji}), post_id, user_id)
        return _serialize_timeline_post(dict(row)) if row else {}


async def pin_timeline_post(post_id: int, pinned: bool, user_id: str = "") -> None:
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        await conn.execute("UPDATE timeline_posts SET pinned = $1 WHERE id = $2 AND user_id = $3", pinned, post_id, user_id)


async def delete_timeline_post(post_id: int, user_id: str = "") -> None:
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        await conn.execute("DELETE FROM timeline_posts WHERE id = $1 AND user_id = $2", post_id, user_id)


async def get_timeline_reply_counts(post_ids: list[int], user_id: str = "") -> dict[int, int]:
    """Get reply counts for a list of post IDs."""
    user_id = _resolve_user_id(user_id)
    if not post_ids:
        return {}
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT parent_id, COUNT(*) as cnt
            FROM timeline_posts
            WHERE parent_id = ANY($1) AND (user_id = $2 OR user_id = '')
            GROUP BY parent_id
        """, post_ids, user_id)
        return {r["parent_id"]: r["cnt"] for r in rows}


async def vote_timeline_post(post_id: int, voter: str, direction: int, user_id: str = "") -> dict:
    """Cast or update a vote on a post. direction: 1 (up), -1 (down), 0 (remove).

    Returns {"post_id": ..., "votes": ..., "user_vote": ...}
    """
    user_id = _resolve_user_id(user_id)
    direction = max(-1, min(1, direction))  # clamp

    async with get_conn() as conn:
        if direction == 0:
            await conn.execute(
                "DELETE FROM timeline_votes WHERE post_id = $1 AND voter = $2 AND user_id = $3",
                post_id, voter, user_id,
            )
        else:
            await conn.execute("""
                INSERT INTO timeline_votes (post_id, voter, direction, user_id)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (post_id, voter) DO UPDATE SET direction = $3
            """, post_id, voter, direction, user_id)
        # Get total
        row = await conn.fetchrow(
            "SELECT COALESCE(SUM(direction), 0) AS total FROM timeline_votes WHERE post_id = $1 AND user_id = $2",
            post_id, user_id,
        )
        total = row["total"] if row else 0
        return {"post_id": post_id, "votes": total, "user_vote": direction}


async def get_timeline_vote_counts(post_ids: list[int], voter: str = "user", user_id: str = "") -> dict[int, dict]:
    """Get vote totals and user's vote for a list of post IDs.

    Returns {post_id: {"votes": total, "user_vote": direction}}
    """
    user_id = _resolve_user_id(user_id)
    if not post_ids:
        return {}

    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT post_id,
                   COALESCE(SUM(direction), 0) AS votes,
                   COALESCE(MAX(CASE WHEN voter = $2 THEN direction END), 0) AS user_vote
            FROM timeline_votes
            WHERE post_id = ANY($1) AND user_id = $3
            GROUP BY post_id
        """, post_ids, voter, user_id)

        result = {r["post_id"]: {"votes": r["votes"], "user_vote": r["user_vote"]} for r in rows}
        return {
            pid: result.get(pid, {"votes": 0, "user_vote": 0})
            for pid in post_ids
        }


async def get_agent_reputation(agent: str, user_id: str = "") -> dict:
    """Get cumulative vote score for an agent across all their posts.

    Returns {"agent": ..., "total_votes": ..., "post_count": ..., "avg_score": ...}
    """
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            SELECT
                COUNT(DISTINCT p.id) AS post_count,
                COALESCE(SUM(v.direction), 0) AS total_votes
            FROM timeline_posts p
            LEFT JOIN timeline_votes v ON v.post_id = p.id
            WHERE p.agent = $1 AND p.user_id = $2
        """, agent, user_id)
        post_count = row["post_count"] if row else 0
        total_votes = row["total_votes"] if row else 0
        return {
            "agent": agent,
            "total_votes": total_votes,
            "post_count": post_count,
            "avg_score": round(total_votes / post_count, 2) if post_count else 0.0,
        }


async def get_agent_vote_stats(days: int = 7, user_id: str = "") -> list[dict]:
    """Get average vote score per agent over the last N days.

    Returns [{"agent": ..., "avg_score": ..., "post_count": ...}] sorted by avg_score DESC.
    """
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT
                p.agent,
                ROUND(AVG(COALESCE(v.total, 0))::numeric, 2) AS avg_score,
                COUNT(p.id) AS post_count
            FROM timeline_posts p
            LEFT JOIN (
                SELECT post_id, SUM(direction) AS total
                FROM timeline_votes
                WHERE user_id = $2
                GROUP BY post_id
            ) v ON v.post_id = p.id
            WHERE p.agent != 'user'
              AND p.created_at >= NOW() - make_interval(days => $1)
              AND p.user_id = $2
            GROUP BY p.agent
            ORDER BY avg_score DESC
        """, days, user_id)
        return [{"agent": r["agent"], "avg_score": float(r["avg_score"]), "post_count": r["post_count"]} for r in rows]


def _serialize_timeline_post(d: dict) -> dict:
    """Normalize a timeline post dict for JSON serialization."""
    if "created_at" in d and hasattr(d["created_at"], "isoformat"):
        d["created_at"] = d["created_at"].isoformat()
    for jkey in ("context", "reactions"):
        if jkey in d and isinstance(d[jkey], str):
            try:
                d[jkey] = json.loads(d[jkey])
            except Exception:
                pass
    return d
