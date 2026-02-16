"""Database module re-exports for backward compatibility.

Usage:
    from app.db import init_db, get_conn, create_approval, ...
"""

# Core - connection pool, migrations
from .core import (
    init_db,
    close_db,
    get_conn,
    run_group_chat_migrations,
)

# Approvals
from .approvals import (
    create_approval,
    get_pending_approvals,
    get_approval_by_id,
    resolve_approval,
    get_resolved_approvals_for_thread,
)

# Agents - state, activity, memory, triggers
from .agents import (
    get_all_agent_states,
    update_agent_state,
    log_activity,
    get_recent_activity,
    get_thought_triggers,
    upsert_thought_trigger,
    update_trigger_last_fired,
    store_agent_memory,
    recall_agent_memories,
    get_agent_memory_stats,
)

# Jobs
from .jobs import (
    get_jobs_pipeline,
    update_job_stage,
)

# LeetCode
from .leetcode import (
    get_leetcode_progress_data,
    log_leetcode_attempt,
)

# Bots - registry, runs, logs, token usage
from .bots import (
    upsert_bot_record,
    get_all_bots,
    get_bot_by_name,
    update_bot_state,
    create_bot_run,
    complete_bot_run,
    get_bot_runs,
    get_bot_run_by_id,
    get_bot_analytics,
    create_bot_log,
    get_bot_run_logs,
    get_token_usage,
    get_token_usage_summary,
)

# Prep materials
from .prep import (
    get_prep_materials,
    get_prep_material_by_id,
    create_prep_material,
    delete_prep_material,
)

# Journal entries
from .journal import (
    get_journal_entries,
    mark_journal_read,
    pin_journal_entry,
    create_journal_entry,
    delete_journal_entry,
)

# Timeline - posts, votes, reactions, analytics
from .timeline import (
    create_timeline_post,
    get_timeline_posts,
    get_timeline_post_by_id,
    get_timeline_replies,
    add_timeline_reaction,
    pin_timeline_post,
    delete_timeline_post,
    get_timeline_reply_counts,
    vote_timeline_post,
    get_timeline_vote_counts,
    get_agent_reputation,
    get_agent_vote_stats,
)

# Chat - langchain history, group chats, messages, proposals, workspace
from .chat import (
    # LangChain chat history
    append_chat_message,
    get_chat_history,
    clear_chat_history,
    # Group chats
    create_group_chat,
    get_group_chat,
    get_group_chats,
    add_group_chat_message,
    get_group_chat_messages,
    update_group_chat_stats,
    update_group_chat_status,
    conclude_group_chat,
    add_group_chat_participant,
    # Prompt proposals
    create_prompt_proposal,
    get_prompt_proposals,
    get_prompt_proposal,
    update_prompt_proposal_status,
    apply_prompt_proposal,
    # Workspace
    save_workspace_task,
    get_workspace_tasks,
    save_workspace_finding,
    get_workspace_findings,
    save_workspace_decision,
    get_workspace_decisions,
    save_tool_call,
    get_tool_calls,
    get_full_workspace,
)

__all__ = [
    # Core
    "init_db",
    "close_db",
    "get_conn",
    "run_group_chat_migrations",
    # Approvals
    "create_approval",
    "get_pending_approvals",
    "get_approval_by_id",
    "resolve_approval",
    "get_resolved_approvals_for_thread",
    # Agents
    "get_all_agent_states",
    "update_agent_state",
    "log_activity",
    "get_recent_activity",
    "get_thought_triggers",
    "upsert_thought_trigger",
    "update_trigger_last_fired",
    "store_agent_memory",
    "recall_agent_memories",
    "get_agent_memory_stats",
    # Jobs
    "get_jobs_pipeline",
    "update_job_stage",
    # LeetCode
    "get_leetcode_progress_data",
    "log_leetcode_attempt",
    # Bots
    "upsert_bot_record",
    "get_all_bots",
    "get_bot_by_name",
    "update_bot_state",
    "create_bot_run",
    "complete_bot_run",
    "get_bot_runs",
    "get_bot_run_by_id",
    "get_bot_analytics",
    "create_bot_log",
    "get_bot_run_logs",
    "get_token_usage",
    "get_token_usage_summary",
    # Prep
    "get_prep_materials",
    "get_prep_material_by_id",
    "create_prep_material",
    "delete_prep_material",
    # Journal
    "get_journal_entries",
    "mark_journal_read",
    "pin_journal_entry",
    "create_journal_entry",
    "delete_journal_entry",
    # Timeline
    "create_timeline_post",
    "get_timeline_posts",
    "get_timeline_post_by_id",
    "get_timeline_replies",
    "add_timeline_reaction",
    "pin_timeline_post",
    "delete_timeline_post",
    "get_timeline_reply_counts",
    "vote_timeline_post",
    "get_timeline_vote_counts",
    "get_agent_reputation",
    "get_agent_vote_stats",
    # Chat - LangChain history
    "append_chat_message",
    "get_chat_history",
    "clear_chat_history",
    # Chat - Group chats
    "create_group_chat",
    "get_group_chat",
    "get_group_chats",
    "add_group_chat_message",
    "get_group_chat_messages",
    "update_group_chat_stats",
    "update_group_chat_status",
    "conclude_group_chat",
    "add_group_chat_participant",
    # Chat - Prompt proposals
    "create_prompt_proposal",
    "get_prompt_proposals",
    "get_prompt_proposal",
    "update_prompt_proposal_status",
    "apply_prompt_proposal",
    # Chat - Workspace
    "save_workspace_task",
    "get_workspace_tasks",
    "save_workspace_finding",
    "get_workspace_findings",
    "save_workspace_decision",
    "get_workspace_decisions",
    "save_tool_call",
    "get_tool_calls",
    "get_full_workspace",
]
