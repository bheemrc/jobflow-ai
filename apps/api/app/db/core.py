"""Core database connection pool and migrations.

PostgreSQL is required — the service will not start without it.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
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
