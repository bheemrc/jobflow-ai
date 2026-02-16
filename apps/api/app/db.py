"""PostgreSQL database connection and queries for Nexus AI.

PostgreSQL is required — the service will not start without it.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from app.config import settings

logger = logging.getLogger(__name__)

_pool = None  # asyncpg.Pool | None


async def init_db() -> None:
    """Create connection pool and run migrations. Raises if PostgreSQL is unavailable."""
    global _pool
    import asyncpg
    _pool = await asyncpg.create_pool(settings.postgres_url, min_size=2, max_size=10)
    async with _pool.acquire() as conn:
        await _run_migrations(conn)

        # DNA system migrations
        try:
            from app.dna.db import run_migrations as dna_migrations
            await dna_migrations(conn)
        except Exception as e:
            logger.warning("DNA migrations failed: %s", e)

        # Katalyst system migrations
        try:
            from app.katalyst.db import run_migrations as katalyst_migrations
            await katalyst_migrations(conn)
        except Exception as e:
            logger.warning("Katalyst migrations failed: %s", e)

        # Group chat system migrations
        try:
            await run_group_chat_migrations(conn)
        except Exception as e:
            logger.warning("Group chat migrations failed: %s", e)

    logger.info("Database initialized (PostgreSQL)")


async def close_db() -> None:
    """Close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_conn() -> AsyncGenerator:
    """Acquire a connection from the pool."""
    if _pool is None:
        raise RuntimeError("Database not initialized — call init_db() first")
    async with _pool.acquire() as conn:
        yield conn


async def _run_migrations(conn) -> None:
    """Create tables if they don't exist."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS saved_jobs (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL DEFAULT '',
            min_amount REAL,
            max_amount REAL,
            currency TEXT,
            job_url TEXT NOT NULL UNIQUE,
            date_posted TEXT,
            job_type TEXT,
            is_remote BOOLEAN NOT NULL DEFAULT FALSE,
            description TEXT,
            site TEXT,
            status TEXT NOT NULL DEFAULT 'saved',
            notes TEXT NOT NULL DEFAULT '',
            saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_saved_jobs_status ON saved_jobs(status)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_saved_jobs_company ON saved_jobs(company)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS approvals (
            id SERIAL PRIMARY KEY,
            thread_id TEXT NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            agent TEXT NOT NULL,
            content TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            resolved_at TIMESTAMPTZ
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_states (
            agent_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'idle',
            last_run TIMESTAMPTZ,
            current_task TEXT,
            tasks_completed INTEGER NOT NULL DEFAULT 0
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS leetcode_progress (
            id SERIAL PRIMARY KEY,
            problem_id INTEGER NOT NULL UNIQUE,
            problem_title TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            topic TEXT NOT NULL,
            solved BOOLEAN NOT NULL DEFAULT FALSE,
            time_minutes INTEGER,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_attempt TIMESTAMPTZ
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS leetcode_mastery (
            topic TEXT PRIMARY KEY,
            level INTEGER NOT NULL DEFAULT 0,
            problems_solved INTEGER NOT NULL DEFAULT 0,
            problems_attempted INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id SERIAL PRIMARY KEY,
            agent TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_activity_log_created ON activity_log(created_at DESC)
    """)

    # Seed agent_states
    agents = ["job_intake", "resume_tailor", "recruiter_chat", "interview_prep", "leetcode_coach"]
    for agent_id in agents:
        await conn.execute("""
            INSERT INTO agent_states (agent_id) VALUES ($1)
            ON CONFLICT (agent_id) DO NOTHING
        """, agent_id)

    # ── Bot system tables ──

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bots (
            name TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            config JSONB,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            status TEXT NOT NULL DEFAULT 'scheduled',
            last_run_at TIMESTAMPTZ,
            next_run_at TIMESTAMPTZ,
            total_runs INTEGER NOT NULL DEFAULT 0
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_runs (
            run_id TEXT PRIMARY KEY,
            bot_name TEXT NOT NULL REFERENCES bots(name),
            status TEXT NOT NULL DEFAULT 'running',
            trigger_type TEXT NOT NULL DEFAULT 'manual',
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            output TEXT,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost REAL NOT NULL DEFAULT 0
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_bot_runs_bot_name ON bot_runs(bot_name)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_bot_runs_started ON bot_runs(started_at DESC)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_logs (
            id SERIAL PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES bot_runs(run_id),
            level TEXT NOT NULL DEFAULT 'info',
            event_type TEXT NOT NULL,
            message TEXT,
            data JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_bot_logs_run_id ON bot_logs(run_id)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id SERIAL PRIMARY KEY,
            date TEXT NOT NULL,
            bot_name TEXT NOT NULL,
            run_count INTEGER NOT NULL DEFAULT 0,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost REAL NOT NULL DEFAULT 0,
            model TEXT NOT NULL DEFAULT '',
            UNIQUE(date, bot_name, model)
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_token_usage_date ON token_usage(date DESC)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_schedules (
            bot_name TEXT PRIMARY KEY REFERENCES bots(name),
            schedule_type TEXT NOT NULL DEFAULT 'interval',
            schedule_config JSONB,
            next_fire_time TIMESTAMPTZ,
            paused BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)

    # ── Prep materials table ──
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS prep_materials (
            id SERIAL PRIMARY KEY,
            material_type TEXT NOT NULL,
            title TEXT NOT NULL,
            company TEXT,
            role TEXT,
            agent_source TEXT,
            content JSONB NOT NULL DEFAULT '{}',
            resources JSONB DEFAULT '[]',
            scheduled_date TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_prep_type ON prep_materials(material_type)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_prep_company ON prep_materials(company)
    """)

    # ── Journal entries table ──
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            id SERIAL PRIMARY KEY,
            entry_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            agent TEXT,
            priority TEXT NOT NULL DEFAULT 'medium',
            tags JSONB DEFAULT '[]',
            is_read BOOLEAN NOT NULL DEFAULT FALSE,
            is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_journal_type ON journal_entries(entry_type)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_journal_read ON journal_entries(is_read)
    """)

    # ── Timeline tables ──
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS timeline_posts (
            id SERIAL PRIMARY KEY,
            agent TEXT NOT NULL,
            post_type TEXT NOT NULL,
            content TEXT NOT NULL,
            parent_id INT REFERENCES timeline_posts(id),
            context JSONB DEFAULT '{}',
            reactions JSONB DEFAULT '{}',
            visibility TEXT DEFAULT 'all',
            pinned BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_timeline_created ON timeline_posts(created_at DESC)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_timeline_agent ON timeline_posts(agent)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_timeline_parent ON timeline_posts(parent_id)
    """)

    # ── Votes table ──
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS timeline_votes (
            post_id INT NOT NULL REFERENCES timeline_posts(id) ON DELETE CASCADE,
            voter TEXT NOT NULL DEFAULT 'user',
            direction SMALLINT NOT NULL CHECK (direction IN (-1, 0, 1)),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (post_id, voter)
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_votes_post ON timeline_votes(post_id)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS thought_triggers (
            id SERIAL PRIMARY KEY,
            trigger_type TEXT NOT NULL,
            trigger_config JSONB NOT NULL,
            agent TEXT NOT NULL,
            prompt_template TEXT NOT NULL,
            cooldown_minutes INT DEFAULT 30,
            enabled BOOLEAN DEFAULT TRUE,
            last_triggered_at TIMESTAMPTZ
        )
    """)

    # ── Performance indexes ──
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_thought_triggers_enabled
        ON thought_triggers(enabled) WHERE enabled = true
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_saved_jobs_saved_at
        ON saved_jobs(saved_at DESC)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_timeline_toplevel_created
        ON timeline_posts(created_at DESC) WHERE parent_id IS NULL
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_votes_post_voter
        ON timeline_votes(post_id, voter)
    """)

    # ── Agent Memory table ──
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_memories (
            id SERIAL PRIMARY KEY,
            agent TEXT NOT NULL,
            memory_type TEXT NOT NULL,
            content TEXT NOT NULL,
            context JSONB DEFAULT '{}',
            importance REAL NOT NULL DEFAULT 0.5,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_memories_agent ON agent_memories(agent)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_memories_type ON agent_memories(memory_type)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_memories_importance ON agent_memories(importance DESC)
    """)

    # ── Search history table (shared with Next.js frontend) ──
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT '',
            search_term TEXT NOT NULL,
            location TEXT NOT NULL DEFAULT '',
            is_remote BOOLEAN NOT NULL DEFAULT FALSE,
            site_name TEXT NOT NULL DEFAULT '',
            results_count INTEGER NOT NULL DEFAULT 0,
            searched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_search_history_term ON search_history(search_term)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_search_history_date ON search_history(searched_at)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_search_history_user_id ON search_history(user_id)
    """)

    # ── Multi-user migration: add user_id to all data tables ──
    user_id_tables = [
        "saved_jobs", "search_history", "approvals", "agent_states", "leetcode_progress",
        "leetcode_mastery", "activity_log", "bots", "bot_runs", "bot_logs", "token_usage",
        "bot_schedules", "prep_materials", "journal_entries", "timeline_posts",
        "timeline_votes", "thought_triggers", "agent_memories",
    ]
    for table in user_id_tables:
        try:
            await conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass  # Column already exists
    # User ID indexes
    for table in user_id_tables:
        try:
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_user_id ON {table}(user_id)")
        except Exception:
            pass

    # ── Fix saved_jobs unique constraint: (user_id, job_url) instead of just (job_url) ──
    try:
        await conn.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE tablename = 'saved_jobs' AND indexname = 'saved_jobs_job_url_key'
                ) THEN
                    ALTER TABLE saved_jobs DROP CONSTRAINT saved_jobs_job_url_key;
                END IF;
            EXCEPTION WHEN OTHERS THEN
                NULL;
            END $$
        """)
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_jobs_user_url ON saved_jobs(user_id, job_url)
        """)
    except Exception:
        pass

    # ── Resumes table (replaces filesystem storage) ──
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS resumes (
            id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (id, user_id)
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_resumes_user_id ON resumes(user_id)
    """)

    # ── LangChain chat message history table ──
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS langchain_chat_history (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            agent TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_history_session ON langchain_chat_history(session_id)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_history_agent ON langchain_chat_history(agent)
    """)


# ── Approval queries ──

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


# ── Job pipeline queries ──

async def get_jobs_pipeline(user_id: str = "") -> dict:
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM saved_jobs WHERE user_id = $1 ORDER BY saved_at DESC
        """, user_id)
        pipeline: dict[str, list] = {
            "saved": [], "applied": [], "interview": [], "offer": [], "rejected": []
        }
        for r in rows:
            job = dict(r)
            stage = job.get("status", "saved")
            if stage in pipeline:
                pipeline[stage].append(job)
            else:
                pipeline["saved"].append(job)
        return pipeline


async def update_job_stage(job_id: int, new_status: str, user_id: str = "") -> None:
    async with get_conn() as conn:
        await conn.execute("""
            UPDATE saved_jobs SET status = $1, updated_at = NOW() WHERE id = $2 AND user_id = $3
        """, new_status, job_id, user_id)


# ── LeetCode queries ──

async def get_leetcode_progress_data(user_id: str = "") -> dict:
    async with get_conn() as conn:
        progress = await conn.fetch("SELECT * FROM leetcode_progress WHERE user_id = $1 ORDER BY last_attempt DESC NULLS LAST", user_id)
        mastery = await conn.fetch("SELECT * FROM leetcode_mastery WHERE user_id = $1 ORDER BY topic", user_id)
        total_solved = sum(1 for r in progress if r["solved"])
        streak = 0
        return {
            "total_solved": total_solved,
            "total_attempted": len(progress),
            "streak": streak,
            "problems": [dict(r) for r in progress],
            "mastery": [dict(r) for r in mastery],
        }


async def log_leetcode_attempt(
    problem_id: int,
    problem_title: str,
    difficulty: str,
    topic: str,
    solved: bool,
    time_minutes: int | None = None,
    user_id: str = "",
) -> None:
    async with get_conn() as conn:
        await conn.execute("""
            INSERT INTO leetcode_progress (problem_id, problem_title, difficulty, topic, solved, time_minutes, attempts, last_attempt, user_id)
            VALUES ($1, $2, $3, $4, $5, $6, 1, NOW(), $7)
            ON CONFLICT (problem_id) DO UPDATE SET
                solved = COALESCE(leetcode_progress.solved, FALSE) OR $5,
                time_minutes = COALESCE($6, leetcode_progress.time_minutes),
                attempts = leetcode_progress.attempts + 1,
                last_attempt = NOW()
        """, problem_id, problem_title, difficulty, topic, solved, time_minutes, user_id)

        await conn.execute("""
            INSERT INTO leetcode_mastery (topic, level, problems_solved, problems_attempted, updated_at, user_id)
            VALUES ($1, $2, $3, 1, NOW(), $5)
            ON CONFLICT (topic) DO UPDATE SET
                problems_attempted = leetcode_mastery.problems_attempted + 1,
                problems_solved = leetcode_mastery.problems_solved + (CASE WHEN $4 THEN 1 ELSE 0 END),
                level = LEAST(100, (leetcode_mastery.problems_solved + (CASE WHEN $4 THEN 1 ELSE 0 END)) * 10),
                updated_at = NOW()
        """, topic, (10 if solved else 0), (1 if solved else 0), solved, user_id)


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


# ── Prep Materials queries ──

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


# ── Journal Entries queries ──

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


# ── Timeline Posts ──


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


# ── LangChain Chat History (Postgres-backed) ──

async def append_chat_message(
    session_id: str,
    role: str,
    content: str,
    agent: str = "",
    metadata: dict | None = None,
) -> int:
    """Append a chat message to the Postgres-backed history."""
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO langchain_chat_history (session_id, agent, role, content, metadata)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING id
        """, session_id, agent, role, content, json.dumps(metadata or {}))
        return row["id"]


async def get_chat_history(
    session_id: str,
    agent: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Retrieve chat history for a session, optionally filtered by agent."""
    async with get_conn() as conn:
        if agent:
            rows = await conn.fetch("""
                SELECT * FROM langchain_chat_history
                WHERE session_id = $1 AND agent = $2
                ORDER BY created_at ASC LIMIT $3
            """, session_id, agent, limit)
        else:
            rows = await conn.fetch("""
                SELECT * FROM langchain_chat_history
                WHERE session_id = $1
                ORDER BY created_at ASC LIMIT $2
            """, session_id, limit)
        result = []
        for r in rows:
            d = dict(r)
            if "created_at" in d and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            if "metadata" in d and isinstance(d["metadata"], str):
                try:
                    d["metadata"] = json.loads(d["metadata"])
                except Exception:
                    pass
            result.append(d)
        return result


async def clear_chat_history(session_id: str, agent: str | None = None) -> None:
    """Clear chat history for a session."""
    async with get_conn() as conn:
        if agent:
            await conn.execute(
                "DELETE FROM langchain_chat_history WHERE session_id = $1 AND agent = $2",
                session_id, agent,
            )
        else:
            await conn.execute(
                "DELETE FROM langchain_chat_history WHERE session_id = $1",
                session_id,
            )


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


# ── Group Chat Tables (run separately to avoid migration issues) ──

async def run_group_chat_migrations(conn) -> None:
    """Create group chat tables. Called from init_db after main migrations."""
    # Group chat sessions
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_group_chats (
            id SERIAL PRIMARY KEY,
            topic TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            participants JSONB DEFAULT '[]',
            initiator TEXT,
            max_turns INTEGER DEFAULT 20,
            max_tokens INTEGER DEFAULT 50000,
            turns_used INTEGER DEFAULT 0,
            tokens_used INTEGER DEFAULT 0,
            config JSONB DEFAULT '{}',
            user_id TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            concluded_at TIMESTAMPTZ,
            summary TEXT
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_group_chats_user_id ON agent_group_chats(user_id)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_group_chats_status ON agent_group_chats(status)
    """)

    # Link group chat messages to timeline posts
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS group_chat_messages (
            id SERIAL PRIMARY KEY,
            group_chat_id INTEGER REFERENCES agent_group_chats(id) ON DELETE CASCADE,
            timeline_post_id INTEGER REFERENCES timeline_posts(id) ON DELETE SET NULL,
            agent TEXT NOT NULL,
            turn_number INTEGER NOT NULL,
            mentions JSONB DEFAULT '[]',
            tokens_used INTEGER DEFAULT 0,
            user_id TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_group_chat_messages_chat ON group_chat_messages(group_chat_id)
    """)

    # Prompt evolution proposals
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS prompt_proposals (
            id SERIAL PRIMARY KEY,
            agent TEXT NOT NULL,
            proposed_changes JSONB NOT NULL,
            rationale TEXT,
            status TEXT DEFAULT 'pending',
            group_chat_id INTEGER REFERENCES agent_group_chats(id) ON DELETE SET NULL,
            user_id TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            applied_at TIMESTAMPTZ
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_prompt_proposals_agent ON prompt_proposals(agent)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_prompt_proposals_status ON prompt_proposals(status)
    """)

    # Workspace tasks - persisted collaboration tasks
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS workspace_tasks (
            id SERIAL PRIMARY KEY,
            group_chat_id INTEGER REFERENCES agent_group_chats(id) ON DELETE CASCADE,
            task_key TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            deliverable_type TEXT,
            status TEXT DEFAULT 'pending',
            assigned_to TEXT,
            created_by TEXT NOT NULL,
            result TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            UNIQUE(group_chat_id, task_key)
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_workspace_tasks_chat ON workspace_tasks(group_chat_id)
    """)

    # Workspace findings - persisted research/insights
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS workspace_findings (
            id SERIAL PRIMARY KEY,
            group_chat_id INTEGER REFERENCES agent_group_chats(id) ON DELETE CASCADE,
            finding_key TEXT NOT NULL,
            content TEXT NOT NULL,
            source_agent TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            confidence REAL DEFAULT 0.7,
            tags JSONB DEFAULT '[]',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(group_chat_id, finding_key)
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_workspace_findings_chat ON workspace_findings(group_chat_id)
    """)

    # Workspace decisions - persisted group decisions
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS workspace_decisions (
            id SERIAL PRIMARY KEY,
            group_chat_id INTEGER REFERENCES agent_group_chats(id) ON DELETE CASCADE,
            decision_key TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            proposed_by TEXT NOT NULL,
            status TEXT DEFAULT 'proposed',
            votes_for JSONB DEFAULT '[]',
            votes_against JSONB DEFAULT '[]',
            rationale TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            resolved_at TIMESTAMPTZ,
            UNIQUE(group_chat_id, decision_key)
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_workspace_decisions_chat ON workspace_decisions(group_chat_id)
    """)

    # Tool calls - for UI display
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_tool_calls (
            id SERIAL PRIMARY KEY,
            group_chat_id INTEGER REFERENCES agent_group_chats(id) ON DELETE CASCADE,
            agent TEXT NOT NULL,
            turn_number INTEGER NOT NULL,
            tool_name TEXT NOT NULL,
            tool_args JSONB DEFAULT '{}',
            tool_result TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tool_calls_chat ON agent_tool_calls(group_chat_id)
    """)


# ── Group Chat CRUD Functions ──

async def create_group_chat(
    topic: str,
    participants: list[str],
    initiator: str,
    config: dict | None = None,
    user_id: str = "",
) -> int:
    """Create a new group chat session."""
    user_id = _resolve_user_id(user_id)
    config_data = config or {}
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO agent_group_chats (topic, participants, initiator, config, user_id,
                max_turns, max_tokens)
            VALUES ($1, $2::jsonb, $3, $4::jsonb, $5,
                $6, $7)
            RETURNING id
        """, topic, json.dumps(participants), initiator, json.dumps(config_data), user_id,
            config_data.get("max_turns", 20), config_data.get("max_tokens", 50000))
        return row["id"]


async def get_group_chat(group_chat_id: int, user_id: str = "") -> dict | None:
    """Get a group chat by ID."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM agent_group_chats
            WHERE id = $1 AND user_id = $2
        """, group_chat_id, user_id)
        return _serialize_group_chat(dict(row)) if row else None


async def get_group_chats(
    status: str | None = None,
    limit: int = 50,
    user_id: str = "",
) -> list[dict]:
    """Get group chats, optionally filtered by status."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        if status:
            rows = await conn.fetch("""
                SELECT * FROM agent_group_chats
                WHERE user_id = $1 AND status = $2
                ORDER BY created_at DESC LIMIT $3
            """, user_id, status, limit)
        else:
            rows = await conn.fetch("""
                SELECT * FROM agent_group_chats
                WHERE user_id = $1
                ORDER BY created_at DESC LIMIT $2
            """, user_id, limit)
        return [_serialize_group_chat(dict(r)) for r in rows]


async def add_group_chat_message(
    group_chat_id: int,
    agent: str,
    turn_number: int,
    mentions: list[str] | None = None,
    timeline_post_id: int | None = None,
    tokens_used: int = 0,
    user_id: str = "",
) -> int:
    """Add a message to a group chat."""
    user_id = _resolve_user_id(user_id)
    mentions_list = mentions or []
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO group_chat_messages
                (group_chat_id, agent, turn_number, mentions, timeline_post_id, tokens_used, user_id)
            VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
            RETURNING id
        """, group_chat_id, agent, turn_number, json.dumps(mentions_list),
            timeline_post_id, tokens_used, user_id)
        return row["id"]


async def get_group_chat_messages(
    group_chat_id: int,
    limit: int = 100,
    user_id: str = "",
) -> list[dict]:
    """Get messages for a group chat."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT gcm.*, tp.content, tp.post_type, tp.context
            FROM group_chat_messages gcm
            LEFT JOIN timeline_posts tp ON gcm.timeline_post_id = tp.id
            WHERE gcm.group_chat_id = $1 AND gcm.user_id = $2
            ORDER BY gcm.turn_number ASC, gcm.created_at ASC
            LIMIT $3
        """, group_chat_id, user_id, limit)
        return [_serialize_group_chat_message(dict(r)) for r in rows]


async def update_group_chat_stats(
    group_chat_id: int,
    turns_delta: int = 0,
    tokens_delta: int = 0,
    user_id: str = "",
) -> None:
    """Update turn and token counters for a group chat."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        await conn.execute("""
            UPDATE agent_group_chats
            SET turns_used = turns_used + $1, tokens_used = tokens_used + $2
            WHERE id = $3 AND user_id = $4
        """, turns_delta, tokens_delta, group_chat_id, user_id)


async def update_group_chat_status(
    group_chat_id: int,
    status: str,
    summary: str | None = None,
    user_id: str = "",
) -> None:
    """Update group chat status (active, paused, concluded)."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        if status == "concluded" and summary:
            await conn.execute("""
                UPDATE agent_group_chats
                SET status = $1, summary = $2, concluded_at = NOW()
                WHERE id = $3 AND user_id = $4
            """, status, summary, group_chat_id, user_id)
        else:
            await conn.execute("""
                UPDATE agent_group_chats
                SET status = $1
                WHERE id = $2 AND user_id = $3
            """, status, group_chat_id, user_id)


async def conclude_group_chat(
    group_chat_id: int,
    summary: str,
    user_id: str = "",
) -> None:
    """Mark a group chat as concluded with a summary."""
    await update_group_chat_status(group_chat_id, "concluded", summary, user_id)


async def add_group_chat_participant(
    group_chat_id: int,
    agent: str,
    user_id: str = "",
) -> None:
    """Add a participant to an existing group chat."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        # Use jsonb_build_array and concatenation to add agent if not already present
        await conn.execute("""
            UPDATE agent_group_chats
            SET participants = CASE
                WHEN participants ? $1 THEN participants
                ELSE participants || jsonb_build_array($1)
            END
            WHERE id = $2 AND user_id = $3
        """, agent, group_chat_id, user_id)


# ── Prompt Proposals CRUD ──

async def create_prompt_proposal(
    agent: str,
    proposed_changes: dict,
    rationale: str,
    group_chat_id: int | None = None,
    user_id: str = "",
) -> int:
    """Create a prompt change proposal."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO prompt_proposals
                (agent, proposed_changes, rationale, group_chat_id, user_id)
            VALUES ($1, $2::jsonb, $3, $4, $5)
            RETURNING id
        """, agent, json.dumps(proposed_changes), rationale, group_chat_id, user_id)
        return row["id"]


async def get_prompt_proposals(
    agent: str | None = None,
    status: str | None = None,
    limit: int = 50,
    user_id: str = "",
) -> list[dict]:
    """Get prompt proposals, optionally filtered."""
    user_id = _resolve_user_id(user_id)
    conditions = ["user_id = $1"]
    params: list = [user_id]
    idx = 2
    if agent:
        conditions.append(f"agent = ${idx}")
        params.append(agent)
        idx += 1
    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    where = " AND ".join(conditions)
    params.append(limit)
    async with get_conn() as conn:
        rows = await conn.fetch(f"""
            SELECT * FROM prompt_proposals
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ${idx}
        """, *params)
        return [_serialize_prompt_proposal(dict(r)) for r in rows]


async def get_prompt_proposal(proposal_id: int, user_id: str = "") -> dict | None:
    """Get a single prompt proposal by ID."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM prompt_proposals
            WHERE id = $1 AND user_id = $2
        """, proposal_id, user_id)
        return _serialize_prompt_proposal(dict(row)) if row else None


async def update_prompt_proposal_status(
    proposal_id: int,
    status: str,
    user_id: str = "",
) -> None:
    """Update proposal status (pending, approved, rejected, applied)."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        if status == "applied":
            await conn.execute("""
                UPDATE prompt_proposals
                SET status = $1, applied_at = NOW()
                WHERE id = $2 AND user_id = $3
            """, status, proposal_id, user_id)
        else:
            await conn.execute("""
                UPDATE prompt_proposals
                SET status = $1
                WHERE id = $2 AND user_id = $3
            """, status, proposal_id, user_id)


async def apply_prompt_proposal(proposal_id: int, user_id: str = "") -> dict | None:
    """Mark a proposal as applied and return its details."""
    proposal = await get_prompt_proposal(proposal_id, user_id)
    if proposal and proposal.get("status") in ("pending", "approved"):
        await update_prompt_proposal_status(proposal_id, "applied", user_id)
        proposal["status"] = "applied"
    return proposal


def _serialize_group_chat(d: dict) -> dict:
    """Serialize group chat for JSON response."""
    for key in ("created_at", "concluded_at"):
        if key in d and hasattr(d[key], "isoformat"):
            d[key] = d[key].isoformat() if d[key] else None
    for jkey in ("participants", "config"):
        if jkey in d and isinstance(d[jkey], str):
            try:
                d[jkey] = json.loads(d[jkey])
            except Exception:
                pass
    return d


def _serialize_group_chat_message(d: dict) -> dict:
    """Serialize group chat message for JSON response."""
    if "created_at" in d and hasattr(d["created_at"], "isoformat"):
        d["created_at"] = d["created_at"].isoformat()
    for jkey in ("mentions", "context"):
        if jkey in d and isinstance(d[jkey], str):
            try:
                d[jkey] = json.loads(d[jkey])
            except Exception:
                pass
    return d


def _serialize_prompt_proposal(d: dict) -> dict:
    """Serialize prompt proposal for JSON response."""
    for key in ("created_at", "applied_at"):
        if key in d and hasattr(d[key], "isoformat"):
            d[key] = d[key].isoformat() if d[key] else None
    if "proposed_changes" in d and isinstance(d["proposed_changes"], str):
        try:
            d["proposed_changes"] = json.loads(d["proposed_changes"])
        except Exception:
            pass
    return d


# ══════════════════════════════════════════════════════════════════════════════
# WORKSPACE PERSISTENCE - Tasks, Findings, Decisions, Tool Calls
# ══════════════════════════════════════════════════════════════════════════════

async def save_workspace_task(
    group_chat_id: int,
    task_key: str,
    title: str,
    description: str,
    created_by: str,
    deliverable_type: str = "",
    status: str = "pending",
    assigned_to: str | None = None,
    result: str | None = None,
) -> int:
    """Save or update a workspace task."""
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO workspace_tasks
                (group_chat_id, task_key, title, description, deliverable_type,
                 status, assigned_to, created_by, result)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (group_chat_id, task_key)
            DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                status = EXCLUDED.status,
                assigned_to = EXCLUDED.assigned_to,
                result = EXCLUDED.result,
                completed_at = CASE WHEN EXCLUDED.status = 'completed' THEN NOW() ELSE workspace_tasks.completed_at END
            RETURNING id
        """, group_chat_id, task_key, title, description, deliverable_type,
            status, assigned_to, created_by, result)
        return row["id"]


async def get_workspace_tasks(group_chat_id: int) -> list[dict]:
    """Get all tasks for a workspace."""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM workspace_tasks
            WHERE group_chat_id = $1
            ORDER BY created_at ASC
        """, group_chat_id)
        return [_serialize_workspace_item(dict(r)) for r in rows]


async def save_workspace_finding(
    group_chat_id: int,
    finding_key: str,
    content: str,
    source_agent: str,
    category: str = "general",
    confidence: float = 0.7,
    tags: list[str] | None = None,
) -> int:
    """Save a workspace finding."""
    tags_json = json.dumps(tags or [])
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO workspace_findings
                (group_chat_id, finding_key, content, source_agent, category, confidence, tags)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
            ON CONFLICT (group_chat_id, finding_key)
            DO UPDATE SET
                content = EXCLUDED.content,
                confidence = EXCLUDED.confidence,
                tags = EXCLUDED.tags
            RETURNING id
        """, group_chat_id, finding_key, content, source_agent, category, confidence, tags_json)
        return row["id"]


async def get_workspace_findings(group_chat_id: int) -> list[dict]:
    """Get all findings for a workspace."""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM workspace_findings
            WHERE group_chat_id = $1
            ORDER BY created_at ASC
        """, group_chat_id)
        return [_serialize_workspace_item(dict(r)) for r in rows]


async def save_workspace_decision(
    group_chat_id: int,
    decision_key: str,
    title: str,
    description: str,
    proposed_by: str,
    status: str = "proposed",
    votes_for: list[str] | None = None,
    votes_against: list[str] | None = None,
    rationale: str = "",
) -> int:
    """Save or update a workspace decision."""
    votes_for_json = json.dumps(votes_for or [])
    votes_against_json = json.dumps(votes_against or [])
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO workspace_decisions
                (group_chat_id, decision_key, title, description, proposed_by,
                 status, votes_for, votes_against, rationale)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9)
            ON CONFLICT (group_chat_id, decision_key)
            DO UPDATE SET
                status = EXCLUDED.status,
                votes_for = EXCLUDED.votes_for,
                votes_against = EXCLUDED.votes_against,
                rationale = EXCLUDED.rationale,
                resolved_at = CASE WHEN EXCLUDED.status IN ('approved', 'rejected') THEN NOW() ELSE workspace_decisions.resolved_at END
            RETURNING id
        """, group_chat_id, decision_key, title, description, proposed_by,
            status, votes_for_json, votes_against_json, rationale)
        return row["id"]


async def get_workspace_decisions(group_chat_id: int) -> list[dict]:
    """Get all decisions for a workspace."""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM workspace_decisions
            WHERE group_chat_id = $1
            ORDER BY created_at ASC
        """, group_chat_id)
        return [_serialize_workspace_item(dict(r)) for r in rows]


async def save_tool_call(
    group_chat_id: int,
    agent: str,
    turn_number: int,
    tool_name: str,
    tool_args: dict | None = None,
    tool_result: str | None = None,
) -> int:
    """Save a tool call for display in UI."""
    args_json = json.dumps(tool_args or {})
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO agent_tool_calls
                (group_chat_id, agent, turn_number, tool_name, tool_args, tool_result)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6)
            RETURNING id
        """, group_chat_id, agent, turn_number, tool_name, args_json, tool_result)
        return row["id"]


async def get_tool_calls(group_chat_id: int, turn_number: int | None = None) -> list[dict]:
    """Get tool calls for a group chat, optionally filtered by turn."""
    async with get_conn() as conn:
        if turn_number is not None:
            rows = await conn.fetch("""
                SELECT * FROM agent_tool_calls
                WHERE group_chat_id = $1 AND turn_number = $2
                ORDER BY created_at ASC
            """, group_chat_id, turn_number)
        else:
            rows = await conn.fetch("""
                SELECT * FROM agent_tool_calls
                WHERE group_chat_id = $1
                ORDER BY turn_number ASC, created_at ASC
            """, group_chat_id)
        return [_serialize_workspace_item(dict(r)) for r in rows]


async def get_full_workspace(group_chat_id: int) -> dict:
    """Get the complete workspace state for a group chat."""
    tasks = await get_workspace_tasks(group_chat_id)
    findings = await get_workspace_findings(group_chat_id)
    decisions = await get_workspace_decisions(group_chat_id)
    tool_calls = await get_tool_calls(group_chat_id)

    return {
        "group_chat_id": group_chat_id,
        "tasks": tasks,
        "findings": findings,
        "decisions": decisions,
        "tool_calls": tool_calls,
        "summary": {
            "total_tasks": len(tasks),
            "completed_tasks": len([t for t in tasks if t.get("status") == "completed"]),
            "total_findings": len(findings),
            "total_decisions": len(decisions),
            "approved_decisions": len([d for d in decisions if d.get("status") == "approved"]),
        },
    }


def _serialize_workspace_item(d: dict) -> dict:
    """Serialize workspace item for JSON response."""
    for key in ("created_at", "completed_at", "resolved_at"):
        if key in d and hasattr(d[key], "isoformat"):
            d[key] = d[key].isoformat() if d[key] else None
    for jkey in ("tags", "votes_for", "votes_against", "tool_args"):
        if jkey in d and isinstance(d[jkey], str):
            try:
                d[jkey] = json.loads(d[jkey])
            except Exception:
                pass
    return d
