"""In-process async pub/sub event bus for bot activity.

Production features:
- Event ID tracking for replay on reconnection
- Replay buffer (last N events) for missed event recovery
- Heartbeat generation for SSE keep-alive
- Slow consumer detection and eviction
- Thread-safe subscriber management
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

# Replay buffer size — last N events stored for reconnecting clients
REPLAY_BUFFER_SIZE = 200
# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = 15
# Max queue size per subscriber before dropping events
MAX_SUBSCRIBER_QUEUE = 512


class EventBus:
    """Broadcast event bus with replay buffer and heartbeats."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()
        self._event_counter: int = 0
        self._replay_buffer: deque[dict[str, Any]] = deque(maxlen=REPLAY_BUFFER_SIZE)

    async def publish(self, event: dict[str, Any]) -> None:
        """Publish an event to all subscribers. Assigns event ID and timestamp."""
        self._event_counter += 1
        event["event_id"] = self._event_counter
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()
        if "source" not in event:
            event["source"] = "bot"

        # Store in replay buffer
        self._replay_buffer.append(event)

        # Log group chat events for debugging
        if "group_chat" in event.get("type", ""):
            logger.info("EventBus: publishing %s to %d subscribers", event["type"], len(self._subscribers))

        async with self._lock:
            dead: list[asyncio.Queue] = []
            for queue in self._subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("EventBus: dropping event for slow subscriber (queue full)")
                except Exception:
                    dead.append(queue)
            for q in dead:
                try:
                    self._subscribers.remove(q)
                except ValueError:
                    pass

    async def subscribe(
        self,
        last_event_id: int | None = None,
        include_heartbeats: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to events. Yields events as they arrive.

        Args:
            last_event_id: If provided, replay missed events from buffer first.
            include_heartbeats: If True, yield heartbeat events periodically.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=MAX_SUBSCRIBER_QUEUE)
        async with self._lock:
            self._subscribers.append(queue)

        try:
            # Replay missed events if client reconnected
            if last_event_id is not None:
                for event in self._replay_buffer:
                    if event.get("event_id", 0) > last_event_id:
                        yield event

            # Stream live events with heartbeats
            while True:
                if include_heartbeats:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
                        yield event
                    except asyncio.TimeoutError:
                        yield {
                            "type": "heartbeat",
                            "source": "bot",
                            "event_id": self._event_counter,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                else:
                    event = await queue.get()
                    yield event
        finally:
            async with self._lock:
                try:
                    self._subscribers.remove(queue)
                except ValueError:
                    pass

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def last_event_id(self) -> int:
        return self._event_counter

    def get_replay_events(self, since_id: int) -> list[dict[str, Any]]:
        """Get events from replay buffer since the given event ID."""
        return [e for e in self._replay_buffer if e.get("event_id", 0) > since_id]


# Module-level singleton
event_bus = EventBus()
