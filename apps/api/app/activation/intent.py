"""Intent matching — maps events to bots that should activate.

IntentSignal: a pattern an event must match (glob support for event names).
BotIntent: a bot's full activation config (signals + conditions + rate limits).
IntentMatcher: evaluates an event against all bot intents.
"""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class IntentSignal:
    """A single event pattern a bot listens for."""
    name: str  # event type pattern, supports globs like "bot_completed:*"
    filter: dict = field(default_factory=dict)  # optional key filters (gene_type, tags_any)
    priority: str = "medium"  # high, medium, low


@dataclass
class BotIntent:
    """Full activation intent for a bot."""
    signals: list[IntentSignal] = field(default_factory=list)
    cooldown_minutes: int = 120
    max_runs_per_day: int = 6


class IntentMatcher:
    """Evaluates events against registered bot intents."""

    def __init__(self) -> None:
        self._intents: dict[str, BotIntent] = {}  # bot_name -> BotIntent

    def register(self, bot_name: str, intent: BotIntent) -> None:
        self._intents[bot_name] = intent

    def unregister(self, bot_name: str) -> None:
        self._intents.pop(bot_name, None)

    def match(self, event: dict) -> list[tuple[str, str]]:
        """Match an event against all registered intents.

        Returns list of (bot_name, priority) for bots that should activate.
        """
        event_type = event.get("type", "")
        matches: list[tuple[str, str]] = []

        for bot_name, intent in self._intents.items():
            for signal in intent.signals:
                if not fnmatch.fnmatch(event_type, signal.name):
                    continue
                if not self._check_filters(event, signal.filter):
                    continue
                matches.append((bot_name, signal.priority))
                break  # One match per bot is enough

        # Sort by priority: high > medium > low
        priority_order = {"high": 0, "medium": 1, "low": 2}
        matches.sort(key=lambda m: priority_order.get(m[1], 1))

        return matches

    @staticmethod
    def _check_filters(event: dict, filters: dict) -> bool:
        """Check if event data matches the signal's filter criteria."""
        if not filters:
            return True

        for key, expected in filters.items():
            if key == "tags_any":
                # At least one tag must be present in event's tags
                event_tags = set(event.get("tags", []))
                if not event_tags & set(expected):
                    return False
            elif key == "gene_type":
                if event.get("gene_type") != expected:
                    return False
            else:
                if event.get(key) != expected:
                    return False

        return True
