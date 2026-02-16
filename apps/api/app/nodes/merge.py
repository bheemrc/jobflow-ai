"""Merge node — synchronization barrier after parallel agent execution."""

from __future__ import annotations

from app.state import AgentState


async def merge_node(state: AgentState) -> dict:
    """No-op barrier that waits for all parallel agents to complete.

    LangGraph only invokes this node after every Send() branch has
    finished and their results have been merged via state reducers.
    This provides a single convergence point for routing to the
    approval gate or respond node.
    """
    return {}
