"""LangGraph node implementations for the Nexus AI orchestrator."""

from app.nodes.coach import coach_node
from app.nodes.approval_gate import approval_gate_node
from app.nodes.merge import merge_node
from app.nodes.respond import respond_node
from app.nodes.generic_agent import create_agent_node

# Legacy imports — kept for backward compatibility but specialist nodes
# are now dynamically created from flows.yaml via create_agent_node()
from app.nodes.job_intake import job_intake_node
from app.nodes.resume_tailor import resume_tailor_node
from app.nodes.recruiter_chat import recruiter_chat_node
from app.nodes.interview_prep import interview_prep_node
from app.nodes.leetcode_coach import leetcode_coach_node

__all__ = [
    "coach_node",
    "job_intake_node",
    "resume_tailor_node",
    "recruiter_chat_node",
    "interview_prep_node",
    "leetcode_coach_node",
    "approval_gate_node",
    "merge_node",
    "respond_node",
    "create_agent_node",
]
