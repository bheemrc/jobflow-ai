"""Thought Engine package — generates personality-driven timeline posts.

Re-exports the public API so existing imports like
    from app.thought_engine import create_user_post
continue to work unchanged.
"""

# Core constants and dataclasses
from .core import (
    MENTION_RE,
    MAX_THOUGHT_LENGTH,
    MAX_REPLY_LENGTH,
    MAX_SWARM_REPLY_LENGTH,
    MAX_DYNAMIC_REPLY_LENGTH,
    SWARM_MAX_ACTIVATIONS,
    DYNAMIC_AGENT_CAP,
    DYNAMIC_DEBATE_CAP,
    BUILDER_CAP_PER_POST,
    TTLCache,
    AgentRequest,
    DynamicAgent,
    AgentAssignment,
    ResponsePlan,
    BuilderState,
    SwarmState,
    _active_builders,
    _enforce_quality,
    _system_context,
    _system_context_slim,
    _build_agent_context,
    _get_tools_for_agent,
)

# Rate limiting (including module-level state vars accessed by main.py)
from .rate_limiting import (
    DAILY_POST_LIMIT_PER_AGENT,
    DAILY_POST_LIMIT_GLOBAL,
    THREAD_COOLDOWN_MINUTES,
    _rate_limit_date,
    _agent_daily_posts,
    _global_daily_posts,
    _check_rate_limit,
    _record_post,
)

# Personality and trigger config
from .personality import (
    get_agent_personality,
    get_all_personalities,
    initialize_triggers,
)

# Scheduler
from .scheduler import (
    start_scheduler,
    stop_scheduler,
)

# Event handlers
from .event_handlers import (
    handle_event,
    _generate_thought,
    _handle_mention,
)

# Router
from .router import (
    _plan_response,
    _generate_agent_content,
    _publish_agent_reply,
    _generate_routed_agent_reply,
    _execute_response_plan,
)

# User posts
from .user_posts import (
    create_user_post,
    create_user_reply,
)

# Research swarm
from .research_swarm import (
    _orchestrate_dynamic_swarm,
    _orchestrate_swarm,
)
