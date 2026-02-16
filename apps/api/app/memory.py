"""Conversation summarization for context window management.

When conversations grow long, older messages are summarized to keep
the context window manageable while preserving important information.
"""

from __future__ import annotations

import logging

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# Summarize when message count exceeds this threshold
SUMMARIZE_THRESHOLD = 20
# Keep this many recent messages verbatim
KEEP_RECENT = 10


async def maybe_summarize(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Summarize older messages if the conversation is getting long.

    When the message count exceeds SUMMARIZE_THRESHOLD, summarizes all
    messages except the most recent KEEP_RECENT into a single summary
    message prepended to the conversation.

    Args:
        messages: The full list of conversation messages.

    Returns:
        The (possibly shortened) message list. If summarization occurred,
        older messages are replaced with a summary SystemMessage.
    """
    if len(messages) <= SUMMARIZE_THRESHOLD:
        return messages

    # Split into old (to summarize) and recent (to keep)
    old_messages = messages[:-KEEP_RECENT]
    recent_messages = messages[-KEEP_RECENT:]

    # Build a text representation of old messages for the summarizer
    old_text_parts = []
    for msg in old_messages:
        role = getattr(msg, "type", "unknown")
        content = getattr(msg, "content", "")
        if content and isinstance(content, str) and content.strip():
            old_text_parts.append(f"[{role}]: {content[:500]}")

    if not old_text_parts:
        return messages

    old_text = "\n".join(old_text_parts)

    try:
        summarizer = ChatOpenAI(
            model=settings.fast_model,
            temperature=0,
            max_tokens=500,
        )
        summary_response = await summarizer.ainvoke([
            SystemMessage(content=(
                "Summarize this conversation history concisely. "
                "Preserve: user's name, target companies/roles, resume details mentioned, "
                "key decisions made, tools already used, and current task context. "
                "Be factual and brief."
            )),
            HumanMessage(content=f"Conversation to summarize:\n\n{old_text}"),
        ])

        summary_msg = SystemMessage(content=(
            f"[Conversation Summary]\n{summary_response.content}\n\n"
            "[End of summary — recent messages follow]"
        ))

        logger.info(
            "Summarized %d old messages into summary (kept %d recent)",
            len(old_messages), len(recent_messages),
        )

        return [summary_msg] + recent_messages

    except Exception as e:
        logger.error("Summarization failed, keeping full history: %s", e)
        return messages
