"""Bot registry, runs, logs, and token usage queries."""

from __future__ import annotations

import json
from datetime import datetime

from .core import get_conn


# ── Bot CRUD queries ──

async def upsert_bot_record(name: str, display_name: str, config: dict, user_id: str = "") -> None:
    """Create or update a bot record."""
    async with get_conn() as conn:
        await conn.execute("""
            INSERT INTO bots (name, display_name, config, user_id)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (name) DO UPDATE SET
                display_name = $2, config = $3
        """, name, display_name, json.dumps(config), user_id)


async def get_all_bots(user_id: str = "") -> list[dict]:
    async with get_conn() as conn:
        rows = await conn.fetch("SELECT * FROM bots WHERE user_id = $1 ORDER BY name", user_id)
        result = []
        for r in rows:
            d = dict(r)
            for key in ("last_run_at", "next_run_at"):
                if key in d and hasattr(d[key], "isoformat"):
                    d[key] = d[key].isoformat() if d[key] else None
            result.append(d)
        return result


async def get_bot_by_name(name: str, user_id: str = "") -> dict | None:
    async with get_conn() as conn:
        row = await conn.fetchrow("SELECT * FROM bots WHERE name = $1 AND user_id = $2", name, user_id)
        if not row:
            return None
        d = dict(row)
        for key in ("last_run_at", "next_run_at"):
            if key in d and hasattr(d[key], "isoformat"):
                d[key] = d[key].isoformat() if d[key] else None
        return d


async def update_bot_state(name: str, status: str, last_run_at: datetime | None = None, user_id: str = "") -> None:
    async with get_conn() as conn:
        if last_run_at:
            await conn.execute("""
                UPDATE bots SET status = $1, last_run_at = $2, total_runs = total_runs + 1
                WHERE name = $3 AND user_id = $4
            """, status, last_run_at, name, user_id)
        else:
            await conn.execute(
                "UPDATE bots SET status = $1 WHERE name = $2 AND user_id = $3", status, name, user_id
            )


# ── Bot Runs ──

async def create_bot_run(
    run_id: str, bot_name: str, trigger_type: str, started_at: datetime,
    user_id: str = "",
) -> None:
    async with get_conn() as conn:
        await conn.execute("""
            INSERT INTO bot_runs (run_id, bot_name, status, trigger_type, started_at, user_id)
            VALUES ($1, $2, 'running', $3, $4, $5)
        """, run_id, bot_name, trigger_type, started_at, user_id)


async def complete_bot_run(
    run_id: str, status: str, output: str,
    input_tokens: int, output_tokens: int, cost: float,
    user_id: str = "",
) -> None:
    async with get_conn() as conn:
        await conn.execute("""
            UPDATE bot_runs SET status = $1, output = $2, completed_at = NOW(),
                input_tokens = $3, output_tokens = $4, cost = $5
            WHERE run_id = $6 AND user_id = $7
        """, status, output, input_tokens, output_tokens, cost, run_id, user_id)


async def get_bot_runs(
    bot_name: str,
    limit: int = 20,
    status_filter: str | None = None,
    search_query: str | None = None,
    user_id: str = "",
) -> list[dict]:
    async with get_conn() as conn:
        conditions = ["bot_name = $1", "user_id = $2"]
        params: list = [bot_name, user_id]
        idx = 3
        if status_filter:
            conditions.append(f"status = ${idx}")
            params.append(status_filter)
            idx += 1
        if search_query:
            conditions.append(f"output ILIKE ${idx}")
            params.append(f"%{search_query}%")
            idx += 1
        where = " AND ".join(conditions)
        params.append(limit)
        rows = await conn.fetch(f"""
            SELECT * FROM bot_runs WHERE {where}
            ORDER BY started_at DESC LIMIT ${idx}
        """, *params)
        result = []
        for r in rows:
            d = dict(r)
            for key in ("started_at", "completed_at"):
                if key in d and hasattr(d[key], "isoformat"):
                    d[key] = d[key].isoformat() if d[key] else None
            result.append(d)
        return result


async def get_bot_run_by_id(run_id: str, user_id: str = "") -> dict | None:
    async with get_conn() as conn:
        row = await conn.fetchrow("SELECT * FROM bot_runs WHERE run_id = $1 AND user_id = $2", run_id, user_id)
        if not row:
            return None
        d = dict(row)
        for key in ("started_at", "completed_at"):
            if key in d and hasattr(d[key], "isoformat"):
                d[key] = d[key].isoformat() if d[key] else None
        return d


async def get_bot_analytics(bot_name: str, user_id: str = "") -> dict:
    """Aggregate analytics for a bot: success rate, avg duration/cost, totals."""
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            SELECT
                COUNT(*) AS total_runs,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                COUNT(*) FILTER (WHERE status = 'errored') AS errored,
                AVG(EXTRACT(EPOCH FROM (completed_at - started_at)))
                    FILTER (WHERE completed_at IS NOT NULL) AS avg_duration_s,
                AVG(cost) AS avg_cost,
                SUM(cost) AS total_cost,
                SUM(input_tokens) AS total_input_tokens,
                SUM(output_tokens) AS total_output_tokens
            FROM bot_runs WHERE bot_name = $1 AND user_id = $2
        """, bot_name, user_id)
        d = dict(row) if row else {}
        total = d.get("total_runs", 0) or 0
        completed = d.get("completed", 0) or 0
        errored = d.get("errored", 0) or 0
        # Get last 10 run statuses
        recent_rows = await conn.fetch("""
            SELECT status FROM bot_runs WHERE bot_name = $1 AND user_id = $2
            ORDER BY started_at DESC LIMIT 10
        """, bot_name, user_id)
        recent = [r["status"] for r in recent_rows]
        return {
            "total_runs": total,
            "success_rate": round(completed / total * 100, 1) if total else 0,
            "error_rate": round(errored / total * 100, 1) if total else 0,
            "avg_duration_s": round(float(d.get("avg_duration_s") or 0), 1),
            "avg_cost": round(float(d.get("avg_cost") or 0), 4),
            "total_cost": round(float(d.get("total_cost") or 0), 4),
            "total_input_tokens": int(d.get("total_input_tokens") or 0),
            "total_output_tokens": int(d.get("total_output_tokens") or 0),
            "recent_statuses": recent,
        }


# ── Bot Logs ──

async def create_bot_log(
    run_id: str, level: str, event_type: str,
    message: str, data: dict | None = None,
    user_id: str = "",
) -> None:
    async with get_conn() as conn:
        await conn.execute("""
            INSERT INTO bot_logs (run_id, level, event_type, message, data, user_id)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, run_id, level, event_type, message,
            json.dumps(data) if data else None, user_id)


async def get_bot_run_logs(run_id: str, limit: int = 100, user_id: str = "") -> list[dict]:
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM bot_logs WHERE run_id = $1 AND user_id = $2
            ORDER BY created_at ASC LIMIT $3
        """, run_id, user_id, limit)
        result = []
        for r in rows:
            d = dict(r)
            if "created_at" in d and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            result.append(d)
        return result


# ── Token Usage ──

async def get_token_usage(
    bot_name: str | None = None,
    period: str = "daily",
    limit: int = 30,
    user_id: str = "",
) -> list[dict]:
    async with get_conn() as conn:
        if bot_name:
            rows = await conn.fetch("""
                SELECT * FROM token_usage WHERE bot_name = $1 AND user_id = $2
                ORDER BY date DESC LIMIT $3
            """, bot_name, user_id, limit)
        else:
            rows = await conn.fetch("""
                SELECT * FROM token_usage WHERE user_id = $1 ORDER BY date DESC LIMIT $2
            """, user_id, limit)
        return [dict(r) for r in rows]


async def get_token_usage_summary(user_id: str = "") -> dict:
    """Aggregate token usage for display."""
    async with get_conn() as conn:
        # Total
        row = await conn.fetchrow("""
            SELECT COALESCE(SUM(cost), 0) as total_cost,
                   COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                   COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                   COALESCE(SUM(run_count), 0) as total_runs
            FROM token_usage
            WHERE user_id = $1
        """, user_id)
        totals = dict(row)

        # Per-bot
        bot_rows = await conn.fetch("""
            SELECT bot_name,
                   SUM(cost) as cost,
                   SUM(input_tokens) as input_tokens,
                   SUM(output_tokens) as output_tokens,
                   SUM(run_count) as runs
            FROM token_usage WHERE user_id = $1 GROUP BY bot_name
        """, user_id)
        by_bot = {r["bot_name"]: dict(r) for r in bot_rows}

        # Daily (last 7 days)
        daily_rows = await conn.fetch("""
            SELECT date, SUM(cost) as cost, SUM(input_tokens) as input_tokens,
                   SUM(output_tokens) as output_tokens, SUM(run_count) as runs
            FROM token_usage WHERE user_id = $1 GROUP BY date
            ORDER BY date DESC LIMIT 7
        """, user_id)

        return {
            "total_cost": round(float(totals.get("total_cost", 0)), 4),
            "total_input_tokens": int(totals.get("total_input_tokens", 0)),
            "total_output_tokens": int(totals.get("total_output_tokens", 0)),
            "total_runs": int(totals.get("total_runs", 0)),
            "by_bot": by_bot,
            "daily": [dict(r) for r in daily_rows],
        }
