"""Shared state, locks, and helpers for tools.

This module contains thread-safe primitives used across tool modules.
"""

from __future__ import annotations

import threading

from app.user_context import current_user_id


def _uid() -> str:
    """Get the current user_id from context."""
    return current_user_id.get()


# ── Request Agent Help State ──

_request_agent_help_lock = threading.Lock()
_request_agent_help_pending: list[dict] = []


def drain_pending_agent_requests() -> list[dict]:
    """Drain and return all pending agent help requests (called by orchestrator)."""
    with _request_agent_help_lock:
        pending = list(_request_agent_help_pending)
        _request_agent_help_pending.clear()
    return pending


def _add_pending_agent_request(request: dict) -> None:
    """Add a pending agent help request (called by request_agent_help tool)."""
    with _request_agent_help_lock:
        _request_agent_help_pending.append(request)


# ── Dispatch Builder State ──

_dispatch_builder_lock = threading.Lock()
_dispatch_builder_pending: list[dict] = []


def drain_pending_builder_dispatches() -> list[dict]:
    """Drain and return all pending builder dispatch requests (called by orchestrator)."""
    with _dispatch_builder_lock:
        pending = list(_dispatch_builder_pending)
        _dispatch_builder_pending.clear()
    return pending


def _add_pending_builder_dispatch(request: dict) -> None:
    """Add a pending builder dispatch request (called by dispatch_builder tool)."""
    with _dispatch_builder_lock:
        _dispatch_builder_pending.append(request)


# ── Group Chat Context ──

_current_group_chat_id: int | None = None
_current_group_chat_lock = threading.Lock()


def set_current_group_chat(chat_id: int | None) -> None:
    """Set the current group chat context (called by orchestrator)."""
    global _current_group_chat_id
    with _current_group_chat_lock:
        _current_group_chat_id = chat_id


def get_current_group_chat() -> int | None:
    """Get the current group chat ID."""
    with _current_group_chat_lock:
        return _current_group_chat_id


# ── Current Agent/Topic Context ──

_current_topic: str = ""
_current_agent: str = ""


def set_current_context(topic: str = "", agent: str = "") -> None:
    """Set the current execution context for tools."""
    global _current_topic, _current_agent
    if topic:
        _current_topic = topic
    if agent:
        _current_agent = agent


def _get_current_topic() -> str:
    return _current_topic


def _get_current_agent() -> str:
    return _current_agent
