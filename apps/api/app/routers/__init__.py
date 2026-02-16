"""API routers for modular endpoint organization."""

from .shared import set_graph, get_graph
from .health import router as health_router
from .coach import router as coach_router
from .approvals import router as approvals_router
from .agents import router as agents_router
from .jobs import router as jobs_router
from .leetcode import router as leetcode_router
from .events import router as events_router
from .resume import router as resume_router
from .bots import router as bots_router
from .prep import router as prep_router
from .journal import router as journal_router
from .timeline import router as timeline_router
from .dna import router as dna_router
from .katalyst import router as katalyst_router
from .admin_dna import router as admin_dna_router
from .prompt_proposals import router as prompt_proposals_router
from .admin import router as admin_router
from .group_chats import router as group_chats_router
from .research import router as research_router

__all__ = [
    # Shared utilities
    "set_graph",
    "get_graph",
    # Routers
    "health_router",
    "coach_router",
    "approvals_router",
    "agents_router",
    "jobs_router",
    "leetcode_router",
    "events_router",
    "resume_router",
    "bots_router",
    "prep_router",
    "journal_router",
    "timeline_router",
    "dna_router",
    "katalyst_router",
    "admin_dna_router",
    "prompt_proposals_router",
    "admin_router",
    "group_chats_router",
    "research_router",
]
