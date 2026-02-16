"""Tool collections for binding to agents and the tool registry."""

from __future__ import annotations

# Import all tools for collections
from .resume import review_resume, extract_resume_profile
from .job_search import search_jobs, search_jobs_for_resume
from .job_management import (
    get_saved_jobs,
    save_job,
    update_job_stage,
    add_job_note,
    get_job_pipeline,
    update_job_pipeline_stage,
)
from .user_interests import get_search_history, get_user_job_interests
from .application import prepare_job_application, generate_cover_letter
from .web import web_search
from .leetcode import get_leetcode_progress, select_leetcode_problems, log_leetcode_attempt_tool
from .integrations import send_notification, call_webhook
from .prep import generate_prep_materials
from .bots import manage_bot
from .journal import add_journal_entry
from .swarm import request_agent_help, dispatch_builder, tag_agent_in_chat, spawn_agent, start_group_chat
from .workspace import (
    read_workspace,
    add_finding,
    claim_task,
    complete_task,
    propose_decision,
    vote_on_decision,
    create_task,
)
from .prompt import propose_prompt_change


# ── Tool Collections (for binding to agents) ──

JOB_INTAKE_TOOLS = [search_jobs, review_resume, extract_resume_profile, get_saved_jobs, web_search]
RESUME_TAILOR_TOOLS = [review_resume, extract_resume_profile]
RECRUITER_CHAT_TOOLS = [review_resume, search_jobs, web_search]
INTERVIEW_PREP_TOOLS = [review_resume, extract_resume_profile, search_jobs, web_search]
LEETCODE_COACH_TOOLS = [get_leetcode_progress, select_leetcode_problems, log_leetcode_attempt_tool, web_search]

ALL_TOOLS = [
    review_resume,
    extract_resume_profile,
    search_jobs,
    search_jobs_for_resume,
    get_saved_jobs,
    get_search_history,
    get_user_job_interests,
    prepare_job_application,
    generate_cover_letter,
    get_job_pipeline,
    update_job_pipeline_stage,
    get_leetcode_progress,
    select_leetcode_problems,
    log_leetcode_attempt_tool,
    web_search,
    send_notification,
    call_webhook,
    save_job,
    add_job_note,
    generate_prep_materials,
    manage_bot,
    add_journal_entry,
]


# ── Tool Registry (name → tool object) ──

TOOL_REGISTRY: dict[str, object] = {
    "review_resume": review_resume,
    "extract_resume_profile": extract_resume_profile,
    "search_jobs": search_jobs,
    "search_jobs_for_resume": search_jobs_for_resume,
    "get_saved_jobs": get_saved_jobs,
    "prepare_job_application": prepare_job_application,
    "generate_cover_letter": generate_cover_letter,
    "get_job_pipeline": get_job_pipeline,
    "update_job_stage": update_job_stage,
    "get_leetcode_progress": get_leetcode_progress,
    "select_leetcode_problems": select_leetcode_problems,
    "log_leetcode_attempt_tool": log_leetcode_attempt_tool,
    "web_search": web_search,
    "get_search_history": get_search_history,
    "get_user_job_interests": get_user_job_interests,
    "send_notification": send_notification,
    "call_webhook": call_webhook,
    "save_job": save_job,
    "add_job_note": add_job_note,
    "generate_prep_materials": generate_prep_materials,
    "manage_bot": manage_bot,
    "add_journal_entry": add_journal_entry,
    "request_agent_help": request_agent_help,
    "dispatch_builder": dispatch_builder,
    "tag_agent_in_chat": tag_agent_in_chat,
    "spawn_agent": spawn_agent,
    "propose_prompt_change": propose_prompt_change,
    "start_group_chat": start_group_chat,
    # Workspace collaboration tools
    "read_workspace": read_workspace,
    "add_finding": add_finding,
    "claim_task": claim_task,
    "complete_task": complete_task,
    "propose_decision": propose_decision,
    "vote_on_decision": vote_on_decision,
    "create_task": create_task,
}
