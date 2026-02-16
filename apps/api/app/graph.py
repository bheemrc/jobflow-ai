"""LangGraph StateGraph construction for the Nexus AI orchestrator.

Config-driven: reads agent definitions from flows.yaml and dynamically
registers nodes. Supports parallel multi-agent execution via Send() fan-out.
"""

from __future__ import annotations

import logging

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Send

from app.state import AgentState
from app.flow_config import FlowConfig, get_flow_config
from app.nodes.generic_agent import create_agent_node
from app.nodes import (
    coach_node,
    approval_gate_node,
    merge_node,
    respond_node,
)

logger = logging.getLogger(__name__)


def route_from_coach(state: AgentState) -> list[Send]:
    """Fan out to one or more specialist agents in parallel via Send().

    The coach sets `dispatched_agents` to a list of agent names.
    Each agent receives a copy of the current state and runs concurrently.
    Results merge via state reducers (operator.or_ for dicts, operator.add for lists).
    """
    config = get_flow_config()
    agents = state.dispatched_agents

    if not agents or agents == ["respond"]:
        return [Send("respond", state)]

    # Validate agent names against current config
    valid = [a for a in agents if a in config.specialist_agents]
    if not valid:
        return [Send("respond", state)]

    return [Send(agent, state) for agent in valid]


def route_after_merge(state: AgentState) -> str:
    """After all parallel agents complete and merge, check for approvals."""
    if state.pending_approvals:
        return "approval_gate"
    return "respond"


def build_coach_graph(config: FlowConfig | None = None) -> StateGraph:
    """Build the main orchestrator graph with parallel execution support.

    When config is provided, dynamically registers specialist nodes from YAML.
    """
    if config is None:
        config = get_flow_config()

    graph = StateGraph(AgentState)

    # Core nodes (always present)
    graph.add_node("coach", coach_node)
    graph.add_node("merge", merge_node)
    graph.add_node("approval_gate", approval_gate_node)
    graph.add_node("respond", respond_node)

    # Dynamically register specialist nodes from config
    for name, agent_cfg in config.agents.items():
        if agent_cfg.is_specialist:
            graph.add_node(name, create_agent_node(agent_cfg, config))

    # Entry point
    graph.add_edge(START, "coach")

    # Coach fans out to specialists via Send()
    graph.add_conditional_edges("coach", route_from_coach)

    # Each specialist converges to the merge barrier
    for agent in config.specialist_agents:
        graph.add_edge(agent, "merge")

    # After merge, route to approval gate or respond
    graph.add_conditional_edges("merge", route_after_merge, {
        "approval_gate": "approval_gate",
        "respond": "respond",
    })

    # After approval, go to respond
    graph.add_edge("approval_gate", "respond")

    # End
    graph.add_edge("respond", END)

    return graph


async def create_compiled_graph(postgres_url: str, flow_config: FlowConfig | None = None):
    """Create a compiled graph with PostgreSQL checkpointing. Raises if Postgres is unavailable."""
    from psycopg import AsyncConnection
    from psycopg_pool import AsyncConnectionPool

    graph_builder = build_coach_graph(flow_config)

    # Run checkpointer setup with autocommit so CREATE INDEX CONCURRENTLY works
    async with await AsyncConnection.connect(postgres_url, autocommit=True) as conn:
        checkpointer_tmp = AsyncPostgresSaver(conn)
        await checkpointer_tmp.setup()
    logger.info("Checkpointer tables created/verified")

    pool = AsyncConnectionPool(
        conninfo=postgres_url,
        min_size=1,
        max_size=5,
        open=False,
    )
    await pool.open()
    await pool.check()
    checkpointer = AsyncPostgresSaver(pool)
    logger.info("Using PostgreSQL checkpointer (connection pool)")

    compiled = graph_builder.compile(
        checkpointer=checkpointer,
    )

    logger.info("Compiled graph ready (parallel execution enabled, config-driven)")
    return compiled
