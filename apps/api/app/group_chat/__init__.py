"""Multi-agent group chat system.

Enables autonomous group discussions between DNA agents on any topic.
Agents can @tag each other, debate ideas, and propose changes to their own prompts.
"""

from app.group_chat.orchestrator import GroupChatOrchestrator
from app.group_chat.controls import GroupChatConfig, GroupChatState, EnforcementAction

__all__ = [
    "GroupChatOrchestrator",
    "GroupChatConfig",
    "GroupChatState",
    "EnforcementAction",
]
