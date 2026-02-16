"""Agent state, activity, memory, and trigger queries."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .core import get_conn


# ── Agent state queries ──

async def get_all_agent_states(user_id: str = "") -> list[dict]:
    async with get_conn() as conn:
        rows = await conn.fetch("SELECT * FROM agent_states WHERE user_id = $1 ORDER BY agent_id", user_id)
        return [dict(r) for r in rows]


async def update_agent_state(agent_id: str, status: str, current_task: str | None = None, user_id: str = "") -> None:
    async with get_conn() as conn:
        if status == "running":
            await conn.execute("""
                UPDATE agent_states
                SET status = $1, current_task = $2, last_run = NOW()
                WHERE agent_id = $3 AND user_id = $4
            """, status, current_task, agent_id, user_id)
        elif status == "idle":
            await conn.execute("""
                UPDATE agent_states
                SET status = $1, current_task = NULL, tasks_completed = tasks_completed + 1
                WHERE agent_id = $2 AND user_id = $3
            """, status, agent_id, user_id)
        else:
            await conn.execute("""
                UPDATE agent_states SET status = $1, current_task = $2
                WHERE agent_id = $3 AND user_id = $4
            """, status, current_task, agent_id, user_id)


# ── Activity log ──

async def log_activity(agent: str, action: str, detail: str | None = None, user_id: str = "") -> None:
    async with get_conn() as conn:
        await conn.execute("""
            INSERT INTO activity_log (agent, action, detail, user_id) VALUES ($1, $2, $3, $4)
        """, agent, action, detail, user_id)


async def get_recent_activity(limit: int = 20, user_id: str = "") -> list[dict]:
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM activity_log WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2
        """, user_id, limit)
        return [dict(r) for r in rows]


# ── Thought Triggers ──

async def get_thought_triggers(enabled_only: bool = True, user_id: str = "") -> list[dict]:
    async with get_conn() as conn:
        if enabled_only:
            rows = await conn.fetch("SELECT * FROM thought_triggers WHERE enabled = TRUE AND user_id = $1", user_id)
        else:
            rows = await conn.fetch("SELECT * FROM thought_triggers WHERE user_id = $1", user_id)
        return [_serialize_thought_trigger(dict(r)) for r in rows]


async def upsert_thought_trigger(
    trigger_type: str,
    trigger_config: dict,
    agent: str,
    prompt_template: str,
    cooldown_minutes: int = 30,
    enabled: bool = True,
    user_id: str = "",
) -> int:
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO thought_triggers (trigger_type, trigger_config, agent, prompt_template, cooldown_minutes, enabled, user_id)
            VALUES ($1, $2::jsonb, $3, $4, $5, $6, $7)
            RETURNING id
        """, trigger_type, json.dumps(trigger_config), agent, prompt_template, cooldown_minutes, enabled, user_id)
        return row["id"]


async def update_trigger_last_fired(trigger_id: int, user_id: str = "") -> None:
    now = datetime.now(timezone.utc)
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE thought_triggers SET last_triggered_at = $1 WHERE id = $2 AND user_id = $3", now, trigger_id, user_id
        )


# ── Agent Memory ──

async def store_agent_memory(
    agent: str,
    memory_type: str,
    content: str,
    context: dict | None = None,
    importance: float = 0.5,
    user_id: str = "",
) -> int:
    """Store an agent memory/observation.

    memory_type: "observation", "preference", "pattern", "interaction", "insight"
    importance: 0.0 (trivial) to 1.0 (critical)
    """
    context_data = context or {}
    importance = max(0.0, min(1.0, importance))

    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO agent_memories (agent, memory_type, content, context, importance, user_id)
            VALUES ($1, $2, $3, $4::jsonb, $5, $6)
            RETURNING id
        """, agent, memory_type, content, json.dumps(context_data), importance, user_id)
        return row["id"]


async def recall_agent_memories(
    agent: str,
    memory_type: str | None = None,
    limit: int = 10,
    min_importance: float = 0.0,
    user_id: str = "",
) -> list[dict]:
    """Recall memories for an agent, ordered by importance then recency."""
    async with get_conn() as conn:
        conditions = ["agent = $1", "importance >= $2", "user_id = $3"]
        params: list = [agent, min_importance, user_id]
        idx = 4
        if memory_type:
            conditions.append(f"memory_type = ${idx}")
            params.append(memory_type)
            idx += 1
        params.append(limit)
        where = " AND ".join(conditions)
        rows = await conn.fetch(f"""
            SELECT * FROM agent_memories
            WHERE {where}
            ORDER BY importance DESC, created_at DESC
            LIMIT ${idx}
        """, *params)
        return [_serialize_agent_memory(dict(r)) for r in rows]


async def get_agent_memory_stats(user_id: str = "") -> dict[str, dict]:
    """Get memory count and average importance per agent."""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT agent, COUNT(*) as count, AVG(importance) as avg_importance
            FROM agent_memories
            WHERE user_id = $1
            GROUP BY agent
        """, user_id)
        return {
            r["agent"]: {
                "count": r["count"],
                "avg_importance": round(float(r["avg_importance"] or 0), 2),
            }
            for r in rows
        }


# ── Serializers ──

def _serialize_agent_memory(d: dict) -> dict:
    if "created_at" in d and hasattr(d["created_at"], "isoformat"):
        d["created_at"] = d["created_at"].isoformat()
    if "context" in d and isinstance(d["context"], str):
        try:
            d["context"] = json.loads(d["context"])
        except Exception:
            pass
    return d


def _serialize_thought_trigger(d: dict) -> dict:
    if "last_triggered_at" in d and hasattr(d["last_triggered_at"], "isoformat"):
        d["last_triggered_at"] = d["last_triggered_at"].isoformat() if d["last_triggered_at"] else None
    if "trigger_config" in d and isinstance(d["trigger_config"], str):
        try:
            d["trigger_config"] = json.loads(d["trigger_config"])
        except Exception:
            pass
    return d
