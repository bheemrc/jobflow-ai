"""Robust SSE streaming with proper disconnect handling.

Prevents memory leaks and zombie connections that cause browser crashes.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Callable, Awaitable

from starlette.requests import Request
from starlette.responses import StreamingResponse

from app.event_bus import event_bus

logger = logging.getLogger(__name__)

# How often to check if client is still connected (seconds)
CLIENT_CHECK_INTERVAL = 5
# Max time without client activity before disconnecting (seconds)
MAX_IDLE_TIME = 300


def format_sse(data: dict[str, Any], event_id: str | int | None = None) -> str:
    """Format data as SSE event."""
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"data: {json.dumps(data, default=str)}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


async def sse_response(
    request: Request,
    generator: AsyncGenerator[dict[str, Any], None],
    *,
    include_heartbeats: bool = True,
) -> StreamingResponse:
    """Create an SSE response with proper disconnect handling.

    Args:
        request: The incoming request (used to detect disconnects)
        generator: Async generator yielding event dicts
        include_heartbeats: Whether to send periodic heartbeats
    """
    async def stream() -> AsyncGenerator[str, None]:
        try:
            async for event in generator:
                # Format and yield event immediately
                event_id = event.get("event_id")
                event_type = event.get("type", "unknown")
                formatted = format_sse(event, event_id)

                # Log non-heartbeat events being formatted
                if event_type != "heartbeat":
                    logger.info("SSE formatting and sending: type=%s, id=%s, bytes=%d",
                              event_type, event_id, len(formatted))

                yield formatted

        except asyncio.CancelledError:
            logger.debug("SSE stream cancelled")
        except GeneratorExit:
            logger.debug("SSE stream generator exit")
        except Exception as e:
            logger.error("SSE stream error: %s", e)
            yield format_sse({"type": "error", "message": str(e)})
        finally:
            logger.debug("SSE stream cleanup complete")

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


async def filtered_event_stream(
    request: Request,
    filter_fn: Callable[[dict[str, Any]], bool],
    *,
    initial_state: dict[str, Any] | None = None,
    last_event_id: int | None = None,
) -> StreamingResponse:
    """Create an SSE stream filtered by a predicate function.

    Args:
        request: The incoming request
        filter_fn: Function that returns True for events to include
        initial_state: Optional initial state to send first
        last_event_id: Event ID for replay (reconnection support)
    """
    async def generator() -> AsyncGenerator[dict[str, Any], None]:
        # Send initial state if provided
        if initial_state:
            yield initial_state

        # Stream filtered events
        # Note: Let the event_bus handle cleanup - no explicit disconnect check
        async for event in event_bus.subscribe(
            last_event_id=last_event_id,
            include_heartbeats=True,
        ):
            # Always pass through heartbeats
            if event.get("type") == "heartbeat":
                yield event
            elif filter_fn(event):
                yield event

    return await sse_response(request, generator())


class SSEManager:
    """Manages SSE connections with proper lifecycle handling."""

    def __init__(self):
        self._connections: dict[str, set[str]] = {}  # channel -> connection_ids
        self._lock = asyncio.Lock()

    async def add_connection(self, channel: str, conn_id: str) -> None:
        async with self._lock:
            if channel not in self._connections:
                self._connections[channel] = set()
            self._connections[channel].add(conn_id)

    async def remove_connection(self, channel: str, conn_id: str) -> None:
        async with self._lock:
            if channel in self._connections:
                self._connections[channel].discard(conn_id)
                if not self._connections[channel]:
                    del self._connections[channel]

    def get_connection_count(self, channel: str | None = None) -> int:
        if channel:
            return len(self._connections.get(channel, set()))
        return sum(len(conns) for conns in self._connections.values())

    def get_channels(self) -> list[str]:
        return list(self._connections.keys())


# Global SSE manager
sse_manager = SSEManager()
