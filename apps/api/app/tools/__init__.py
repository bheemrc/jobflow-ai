"""Tools module re-exports for backward compatibility.

Usage:
    from app.tools import search_jobs, review_resume, TOOL_REGISTRY, ...
"""

# Shared state and helpers
from .shared import (
    _uid,
    drain_pending_agent_requests,
    drain_pending_builder_dispatches,
    set_current_group_chat,
    get_current_group_chat,
    set_current_context,
)

# Resume tools
from .resume import review_resume, extract_resume_profile

# Job search tools
from .job_search import search_jobs, search_jobs_for_resume

# Job management tools
from .job_management import (
    get_saved_jobs,
    save_job,
    update_job_stage,
    add_job_note,
    get_job_pipeline,
    update_job_pipeline_stage,
)

# User interests tools
from .user_interests import get_search_history, get_user_job_interests

# Application tools
from .application import prepare_job_application, generate_cover_letter

# Web search
from .web import web_search

# LeetCode tools
from .leetcode import get_leetcode_progress, select_leetcode_problems, log_leetcode_attempt_tool

# Integration tools
from .integrations import send_notification, call_webhook

# Prep materials
from .prep import generate_prep_materials

# Bot management
from .bots import manage_bot

# Journal
from .journal import add_journal_entry

# Swarm tools
from .swarm import (
    request_agent_help,
    dispatch_builder,
    tag_agent_in_chat,
    spawn_agent,
    start_group_chat,
)

# Workspace collaboration tools
from .workspace import (
    read_workspace,
    add_finding,
    claim_task,
    complete_task,
    propose_decision,
    vote_on_decision,
    create_task,
)

# Prompt evolution
from .prompt import propose_prompt_change

# Tool collections and registry
from .collections import (
    JOB_INTAKE_TOOLS,
    RESUME_TAILOR_TOOLS,
    RECRUITER_CHAT_TOOLS,
    INTERVIEW_PREP_TOOLS,
    LEETCODE_COACH_TOOLS,
    ALL_TOOLS,
    TOOL_REGISTRY,
)

__all__ = [
    # Shared
    "_uid",
    "drain_pending_agent_requests",
    "drain_pending_builder_dispatches",
    "set_current_group_chat",
    "get_current_group_chat",
    "set_current_context",
    # Resume
    "review_resume",
    "extract_resume_profile",
    # Job search
    "search_jobs",
    "search_jobs_for_resume",
    # Job management
    "get_saved_jobs",
    "save_job",
    "update_job_stage",
    "add_job_note",
    "get_job_pipeline",
    "update_job_pipeline_stage",
    # User interests
    "get_search_history",
    "get_user_job_interests",
    # Application
    "prepare_job_application",
    "generate_cover_letter",
    # Web
    "web_search",
    # LeetCode
    "get_leetcode_progress",
    "select_leetcode_problems",
    "log_leetcode_attempt_tool",
    # Integrations
    "send_notification",
    "call_webhook",
    # Prep
    "generate_prep_materials",
    # Bots
    "manage_bot",
    # Journal
    "add_journal_entry",
    # Swarm
    "request_agent_help",
    "dispatch_builder",
    "tag_agent_in_chat",
    "spawn_agent",
    "start_group_chat",
    # Workspace
    "read_workspace",
    "add_finding",
    "claim_task",
    "complete_task",
    "propose_decision",
    "vote_on_decision",
    "create_task",
    # Prompt
    "propose_prompt_change",
    # Collections
    "JOB_INTAKE_TOOLS",
    "RESUME_TAILOR_TOOLS",
    "RECRUITER_CHAT_TOOLS",
    "INTERVIEW_PREP_TOOLS",
    "LEETCODE_COACH_TOOLS",
    "ALL_TOOLS",
    "TOOL_REGISTRY",
]
