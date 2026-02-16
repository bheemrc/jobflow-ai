"""Live Research Session package — expert-guided research with intent-aware strategies."""

from .engine import (
    run_research_session,
    get_session_status,
    cancel_session,
    session_count,
    ResearchSession,
    MAX_CONCURRENT_SESSIONS,
)

from .intent import (
    classify_intent,
    QueryIntent,
    IntentClassification,
)

__all__ = [
    # Engine
    "run_research_session",
    "get_session_status",
    "cancel_session",
    "session_count",
    "ResearchSession",
    "MAX_CONCURRENT_SESSIONS",
    # Intent
    "classify_intent",
    "QueryIntent",
    "IntentClassification",
]
