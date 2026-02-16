"""Pydantic request/response models for the FastAPI endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Coach ──

class CoachContext(BaseModel):
    resume_id: str | None = None
    company: str | None = None
    role: str | None = None
    source: str | None = None
    job_status: str | None = None
    job_description: str | None = None
    saved_jobs_count: int | None = None
    focus_topic: str | None = None


class CoachRequest(BaseModel):
    message: str | None = None
    session_id: str | None = None
    context: CoachContext | None = None


class CoachResponse(BaseModel):
    session_id: str
    response: str
    thinking: str = ""
    actions: list[dict[str, str]] = Field(default_factory=list)
    sections_generated: list[str] = Field(default_factory=list)
    section_cards: list[dict] = Field(default_factory=list)


# ── Resume ──

class ResumeUploadRequest(BaseModel):
    text: str
    resume_id: str | None = None


class ResumeResponse(BaseModel):
    resume_id: str
    text: str | None = None


# ── Approvals ──

class ApprovalDecision(BaseModel):
    decision: str  # "approved" or "rejected"


class BatchApprovalDecisions(BaseModel):
    """Batch resolve multiple approvals for the same thread at once."""
    decisions: dict[int, str]  # {approval_id: "approved"|"rejected"}


class ApprovalItem(BaseModel):
    id: int
    thread_id: str
    type: str
    title: str
    agent: str
    content: str
    priority: str
    status: str
    created_at: str


# ── Jobs Pipeline ──

class JobStageUpdate(BaseModel):
    status: str  # saved, applied, interview, offer, rejected


# ── LeetCode ──

class LeetCodeAttempt(BaseModel):
    problem_id: int
    problem_title: str = ""
    difficulty: str = "medium"
    topic: str = ""
    solved: bool = False
    time_minutes: int | None = None


# ── Flow Config ──

class FlowConfigUpdate(BaseModel):
    yaml_text: str


# ── Agent Status ──

class AgentStatus(BaseModel):
    agent_id: str
    status: str  # idle, running, waiting
    last_run: str | None = None
    current_task: str | None = None
    tasks_completed: int = 0


# ── Bots ──

class BotStateResponse(BaseModel):
    name: str
    display_name: str
    description: str = ""
    status: str  # waiting, running, paused, stopped, errored, disabled
    enabled: bool = True
    last_run_at: str | None = None
    cooldown_until: str | None = None
    runs_today: int = 0
    max_runs_per_day: int = 6
    last_activated_by: str | None = None
    total_runs: int = 0
    config: dict = Field(default_factory=dict)


class BotRunSummary(BaseModel):
    run_id: str
    bot_name: str
    status: str
    trigger_type: str
    started_at: str
    completed_at: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0


class BotRunDetail(BotRunSummary):
    output: str | None = None
    logs: list[dict] = Field(default_factory=list)


class BotScheduleUpdate(BaseModel):
    schedule_type: str  # "interval" or "cron"
    schedule_config: dict = Field(default_factory=dict)


class BotConfigUpdate(BaseModel):
    model: str | None = None
    temperature: float | None = None
    timeout_minutes: int | None = None
    schedule: dict | None = None


class BotEnabledUpdate(BaseModel):
    enabled: bool


class TokenUsageSummary(BaseModel):
    total_cost: float = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_runs: int = 0
    by_bot: dict = Field(default_factory=dict)
    daily: list[dict] = Field(default_factory=list)


class BotsConfigUpdate(BaseModel):
    yaml_text: str


class CustomBotCreate(BaseModel):
    """Create a custom bot at runtime."""
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]{1,48}$")
    display_name: str = Field(..., min_length=1, max_length=60)
    description: str = Field(default="", max_length=500)
    model: str = Field(default="default")  # fast, default, strong
    temperature: float = Field(default=0.5, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=256, le=16384)
    tools: list[str] = Field(default_factory=list)
    prompt: str = Field(default="", max_length=10000)
    schedule_type: str = Field(default="interval")  # interval or cron
    schedule_hours: int | None = Field(default=6, ge=1, le=168)
    schedule_hour: int | None = Field(default=None, ge=0, le=23)
    schedule_minute: int | None = Field(default=None, ge=0, le=59)
    requires_approval: bool = Field(default=False)
    timeout_minutes: int = Field(default=10, ge=1, le=60)
    integrations: dict = Field(default_factory=dict)  # {telegram: {chat_id: ...}, slack: {webhook: ...}, ...}


class AvailableToolInfo(BaseModel):
    """Tool info for the creation wizard."""
    name: str
    description: str
    category: str


class PrepMaterialCreate(BaseModel):
    material_type: str = "general"
    title: str
    content: dict | str = {}
    company: str | None = None
    role: str | None = None
    agent_source: str | None = "chat"
    resources: list | None = None


class BotStartRequest(BaseModel):
    context: str | None = None


# ── Timeline ──

class TimelinePostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    context: dict = Field(default_factory=dict)

class TimelineReplyCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)

class TimelineReactionAdd(BaseModel):
    agent: str = "user"
    emoji: str = Field(..., min_length=1, max_length=30)


# ── Group Chats ──

class GroupChatCreate(BaseModel):
    """Start a new group chat."""
    topic: str = Field(..., min_length=1, max_length=500)
    participants: list[str] = Field(..., min_length=2, max_length=6)
    config: dict = Field(default_factory=dict)


class GroupChatResponse(BaseModel):
    """Group chat details."""
    id: int
    topic: str
    status: str  # active, paused, concluded
    participants: list[str]
    initiator: str
    turns_used: int = 0
    tokens_used: int = 0
    max_turns: int = 20
    max_tokens: int = 50000
    created_at: str
    concluded_at: str | None = None
    summary: str | None = None


class GroupChatMessageResponse(BaseModel):
    """A message in a group chat."""
    id: int
    group_chat_id: int
    agent: str
    turn_number: int
    mentions: list[str] = Field(default_factory=list)
    content: str | None = None
    tokens_used: int = 0
    created_at: str


class PromptProposalCreate(BaseModel):
    """Agent proposal to change their own prompt."""
    agent: str
    field: str  # prompt, tools, temperature, quality_criteria, description
    new_value: str | dict
    rationale: str = Field(..., min_length=10, max_length=1000)


class PromptProposalResponse(BaseModel):
    """Prompt change proposal."""
    id: int
    agent: str
    proposed_changes: dict
    rationale: str
    status: str  # pending, approved, rejected, applied
    group_chat_id: int | None = None
    created_at: str
    applied_at: str | None = None
