"""SSE event conversion helpers for LangGraph stream events."""

from __future__ import annotations

import json
import re

from app.flow_config import get_flow_config

# Tags that should be stripped from streamed text
TAG_PATTERN = re.compile(r"\[(?:ROUTE|COMPANY|ROLE):\s*.+?\]")


def _get_agent_names() -> set[str]:
    """Derive the full set of graph node names from the live flow config."""
    config = get_flow_config()
    # All configured agents + structural nodes
    return config.valid_agents | {"coach", "merge", "approval_gate", "respond"}


def _get_specialist_agents() -> set[str]:
    """Derive the specialist agent set from the live flow config."""
    return get_flow_config().specialist_agents


class SSEConverter:
    """Stateful converter that tracks active nodes to filter events properly.

    Key design decisions driven by the flow config:
    - Agent names and specialist classification come from FlowConfig, not hardcoded sets.
    - Specialist agent tokens use a separate 'agent_delta' event type so the frontend
      can display them in per-agent progress areas instead of mixing them into the
      main chat stream. The main 'delta' type is reserved for the respond/coach nodes.
    - Coach routing chatter is fully suppressed server-side. The frontend never needs
      to filter it.
    """

    def __init__(self):
        self._active_nodes: set[str] = set()

    def convert(self, event: dict) -> dict | list[dict] | None:
        """Convert a LangGraph astream_events event to our SSE protocol.

        May return a single dict, a list of dicts (for multi-event responses),
        or None to skip.
        """
        kind = event.get("event")
        agent_names = _get_agent_names()

        # Track node lifecycle
        if kind == "on_chain_start" and event.get("name") in agent_names:
            name = event["name"]
            self._active_nodes.add(name)
            return {
                "type": "agent_start",
                "agent": name,
            }

        if kind == "on_chain_end" and event.get("name") in agent_names:
            name = event["name"]
            self._active_nodes.discard(name)
            return {
                "type": "agent_end",
                "agent": name,
            }

        # LLM token streaming
        if kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                text = chunk.content

                # Strip control tags from streamed text
                text = TAG_PATTERN.sub("", text)

                # Skip empty chunks after stripping
                if not text.strip() and not text:
                    return None

                parent = event.get("metadata", {}).get("langgraph_node", "")

                # The coach is purely a router — its text (routing decisions,
                # filler phrases) is never shown to the user. Suppress entirely.
                if parent == "coach":
                    return None

                # Specialist agent tokens → separate event type so the frontend
                # can show them in per-agent progress panels, not the main stream.
                if parent in _get_specialist_agents():
                    return {"type": "agent_delta", "text": text, "agent": parent}

                # respond node and any other non-specialist → main stream
                return {"type": "delta", "text": text}

        # Tool invocation started
        if kind == "on_tool_start":
            parent_agent = event.get("metadata", {}).get("langgraph_node", "")
            return {
                "type": "tool_start",
                "tool": event.get("name", ""),
                "agent": parent_agent,
                "input": event.get("data", {}).get("input"),
            }

        # Tool finished
        if kind == "on_tool_end":
            output = event.get("data", {}).get("output", "")
            parent_agent = event.get("metadata", {}).get("langgraph_node", "")
            return {
                "type": "tool_end",
                "tool": event.get("name", ""),
                "agent": parent_agent,
                "output": str(output)[:2000],
            }

        return None


def convert_to_sse(event: dict) -> dict | None:
    """Legacy stateless converter — kept for backward compatibility."""
    kind = event.get("event")
    agent_names = _get_agent_names()

    if kind == "on_chat_model_stream":
        chunk = event.get("data", {}).get("chunk")
        if chunk and hasattr(chunk, "content") and chunk.content:
            text = TAG_PATTERN.sub("", chunk.content)
            if text:
                return {"type": "delta", "text": text}
            return None

    if kind == "on_tool_start":
        return {
            "type": "tool_start",
            "tool": event.get("name", ""),
            "input": event.get("data", {}).get("input"),
        }

    if kind == "on_tool_end":
        output = event.get("data", {}).get("output", "")
        return {
            "type": "tool_end",
            "tool": event.get("name", ""),
            "output": str(output)[:2000],
        }

    if kind == "on_chain_start" and event.get("name") in agent_names:
        return {
            "type": "agent_start",
            "agent": event["name"],
        }

    if kind == "on_chain_end" and event.get("name") in agent_names:
        return {
            "type": "agent_end",
            "agent": event["name"],
        }

    return None


def format_sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def format_bot_event(event: dict) -> str:
    """Format a bot event as an SSE data line.

    Ensures all bot events have source='bot' to distinguish from chat events.
    """
    if "source" not in event:
        event["source"] = "bot"
    return format_sse(event)
