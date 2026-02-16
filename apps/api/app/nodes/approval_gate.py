"""Approval Gate node — blocks execution until human approves or rejects.

Supports multiple pending approvals from parallel agents.
"""

from __future__ import annotations

from langgraph.types import interrupt

from app.state import AgentState


async def approval_gate_node(state: AgentState) -> dict:
    """Block the graph and wait for human approval of all pending items.

    Uses LangGraph's interrupt() to pause execution. The interrupt value
    is the full pending_approvals dict (keyed by agent name). When resumed
    via Command(resume={"agent_a": "approved", "agent_b": "rejected"}),
    execution continues and the decisions are stored in approval_decisions.
    """
    approvals = state.pending_approvals
    if not approvals:
        return {"approval_decisions": {}}

    # Interrupt with ALL pending approvals at once.
    # The resume value should be a dict: {"agent_name": "approved"|"rejected", ...}
    decisions = interrupt(approvals)

    # Handle both dict (batch) and string (single/legacy) resume values
    if isinstance(decisions, dict):
        return {"approval_decisions": decisions}

    # Legacy: single string applied to all pending approvals
    if isinstance(decisions, str):
        return {"approval_decisions": {k: decisions for k in approvals}}

    return {"approval_decisions": {}}
