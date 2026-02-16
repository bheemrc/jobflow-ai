"""Live Research Session engine — expert-guided research with supplementary web search.

Approach:
1. Classify intent (BUILD vs ANALYZE) and domain via regex
2. Generate comprehensive guide from LLM training knowledge
3. Search for supplementary URLs/resources to link
4. Combine into final output with real-time streaming
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.event_bus import event_bus
from app.thought_engine.core import _system_context

from .intent import classify_intent, IntentClassification

logger = logging.getLogger("app.research")

# ── Concurrency control ─────────────────────────────────────────────────────

MAX_CONCURRENT_SESSIONS = 5
_session_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SESSIONS)

# ── Domain-aware resource search sites ───────────────────────────────────────

RESOURCE_SITES: dict[str, list[str]] = {
    "electronics": ["site:github.com", "site:hackaday.io", "site:electronics.stackexchange.com"],
    "embedded": ["site:github.com", "site:hackaday.io", "site:platformio.org"],
    "mechanical": ["site:github.com", "site:instructables.com", "site:hackaday.io"],
    "software": ["site:github.com", "site:stackoverflow.com", "site:dev.to"],
    "robotics": ["site:github.com", "site:hackaday.io", "site:ros.org"],
    "aerospace": ["site:github.com", "site:hackaday.io", "site:arxiv.org"],
    "general": ["site:github.com", "site:stackoverflow.com", "site:dev.to"],
}


# ── Safe task helper ─────────────────────────────────────────────────────────

def _create_logged_task(coro, *, name: str | None = None) -> asyncio.Task:
    """Create an asyncio task that logs exceptions instead of swallowing them."""
    task = asyncio.create_task(coro, name=name)

    def _on_done(t: asyncio.Task) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            logger.error("Background task %s failed: %s", t.get_name(), exc, exc_info=exc)

    task.add_done_callback(_on_done)
    return task


# ── Session data ─────────────────────────────────────────────────────────────

@dataclass
class ResearchSession:
    """Tracks a live research session."""
    session_id: str
    topic: str
    user_id: str
    status: str = "pending"  # pending, spawning, synthesizing, researching, complete, cancelled, error
    agents: list[dict] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    synthesis: str = ""
    material_id: int | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    cancel_requested: bool = False
    # Intent classification
    intent: str = "build"  # build, analyze, troubleshoot, learn, compare
    domain: str = "general"
    complexity: str = "intermediate"
    keywords: list[str] = field(default_factory=list)


# ── Active sessions registry ─────────────────────────────────────────────────

_active_sessions: dict[str, ResearchSession] = {}


def get_session_status(session_id: str, user_id: str | None = None) -> dict | None:
    """Get status of a research session.

    If user_id is provided, verifies ownership.
    """
    session = _active_sessions.get(session_id)
    if not session:
        return None
    if user_id is not None and session.user_id != user_id:
        return None
    return {
        "session_id": session.session_id,
        "topic": session.topic,
        "status": session.status,
        "agents": session.agents,
        "synthesis": session.synthesis[:500] if session.synthesis else "",
        "material_id": session.material_id,
        "error": session.error,
        "created_at": session.created_at,
        "intent": session.intent,
        "domain": session.domain,
        "complexity": session.complexity,
    }


def cancel_session(session_id: str, user_id: str | None = None) -> bool:
    """Request cancellation of a running session.

    If user_id is provided, verifies ownership.
    """
    session = _active_sessions.get(session_id)
    if not session:
        return False
    if user_id is not None and session.user_id != user_id:
        return False
    if session.status in ("complete", "cancelled", "error"):
        return False
    session.cancel_requested = True
    session.status = "cancelled"
    return True


def session_count() -> int:
    """Return number of active (non-terminal) sessions."""
    return sum(
        1 for s in _active_sessions.values()
        if s.status not in ("complete", "cancelled", "error")
    )


# ── Event publishing ─────────────────────────────────────────────────────────

async def _publish_event(session_id: str, event_type: str, **kwargs: Any) -> None:
    """Publish a research session event."""
    await event_bus.publish({
        "type": event_type,
        "session_id": session_id,
        **kwargs,
    })


# ── Expert guide generation ──────────────────────────────────────────────────

async def _generate_expert_guide(
    topic: str,
    classification: IntentClassification,
    session_id: str,
) -> str:
    """Generate a comprehensive guide using the model's training knowledge directly.

    Streams tokens as they arrive via research_synthesis_chunk events.
    """
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        model = ChatOpenAI(
            model=settings.strong_model,
            temperature=0.4,
            max_tokens=5000,
        )

        domain = classification.domain
        keywords = ", ".join(classification.keywords_detected[:5])

        system_prompt = f"""{_system_context()}

You are a world-class expert writing a comprehensive technical guide. You have deep knowledge from extensive training. USE IT ALL.

DOMAIN: {domain}
KEYWORDS: {keywords}

Write a COMPLETE, DETAILED technical guide. This should be the quality of a senior engineer's documentation - specific, practical, actionable.

STRUCTURE (use markdown):

## Overview
- What this is and why it matters
- Key principles and physics involved
- Typical specifications and parameters (actual numbers)

## System Architecture
- Block diagram description
- Key subsystems and their interactions
- Critical interfaces

## Components

### [Component Category 1]
For each major component type:
- **Function**: What it does
- **Key specifications**: Actual values (voltage, current, torque, etc.)
- **Common options**: Specific products/parts that work
- **Selection criteria**: How to choose

### [Component Category 2]
...continue for all major components...

## Design Calculations
- Key formulas with explanations
- Example calculations with real numbers
- Design margins and safety factors

## Build Procedure

### Phase 1: [Name]
Detailed steps with specific actions

### Phase 2: [Name]
...continue for all phases...

## Control System
- Control architecture
- Algorithms (PID, FOC, etc.)
- Tuning procedures
- Code structure/pseudocode

## Testing & Validation
- Test procedures with pass/fail criteria
- Calibration steps
- Troubleshooting decision tree

## Common Failure Modes
| Symptom | Likely Cause | Solution |
|---------|--------------|----------|

## References & Resources
- Key papers/standards
- Recommended libraries/tools
- Community resources

---

CRITICAL RULES:
- Be SPECIFIC: actual values, not "appropriate" or "suitable"
- Include FORMULAS where relevant
- Give REAL component examples (you know these from training)
- Write for someone who will actually BUILD this
- 4000-5000 words minimum
- This should be BETTER than most tutorials online because you can synthesize knowledge from many sources"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"""Write a comprehensive technical guide for:

{topic}

Be thorough. Be specific. Be practical. This guide should enable someone to actually build this."""),
        ]

        # Stream tokens and emit chunks for real-time UI updates
        collected: list[str] = []
        buffer: list[str] = []
        CHUNK_SIZE = 200  # characters before flushing a chunk event

        async for chunk in model.astream(messages):
            token = chunk.content if hasattr(chunk, "content") else ""
            if not token:
                continue
            collected.append(token)
            buffer.append(token)

            if len("".join(buffer)) >= CHUNK_SIZE:
                await _publish_event(
                    session_id, "research_synthesis_chunk",
                    chunk="".join(buffer),
                )
                buffer.clear()

        # Flush remaining buffer
        if buffer:
            await _publish_event(
                session_id, "research_synthesis_chunk",
                chunk="".join(buffer),
            )

        return "".join(collected).strip()

    except Exception as e:
        logger.error("Expert guide generation failed: %s", e)
        return ""


# ── Resource search ──────────────────────────────────────────────────────────

def _build_resource_queries(session: ResearchSession) -> list[str]:
    """Build domain-aware resource search queries."""
    domain = session.domain
    keywords = session.keywords
    topic = session.topic

    sites = RESOURCE_SITES.get(domain, RESOURCE_SITES["general"])
    first_keyword = keywords[0] if keywords else topic.split()[0]
    keyword_str_short = " ".join(keywords[:2]) if keywords else first_keyword
    keyword_str = " ".join(keywords[:3]) if keywords else first_keyword

    return [
        f"{sites[0]} {keyword_str}",
        f"{sites[1]} {keyword_str_short}" if len(sites) > 1 else f"{first_keyword} tutorial guide",
        f"{first_keyword} tutorial guide",
    ]


async def _search_for_resources(
    session: ResearchSession,
    session_id: str,
    agent_id: str,
) -> list[str]:
    """Search for supplementary URLs to add to the guide."""
    from app.tools import TOOL_REGISTRY

    web_search = TOOL_REGISTRY.get("web_search")
    if not web_search:
        logger.warning("web_search tool not found in TOOL_REGISTRY")
        return []

    resource_queries = _build_resource_queries(session)
    found_urls: list[str] = []

    for query in resource_queries:
        if session.cancel_requested:
            break

        await _publish_event(
            session_id, "agent_search_started",
            agent_id=agent_id,
            agent_name="Resource Finder",
            query=query,
        )
        try:
            result_json = web_search.invoke({"query": query, "max_results": 3})
            result_data = json.loads(result_json) if isinstance(result_json, str) else result_json
            results = result_data.get("results", [])
            for r in results[:2]:
                found_urls.append(f"- [{r.get('title', 'Resource')}]({r.get('url', '')})")
            await _publish_event(
                session_id, "agent_search_result",
                agent_id=agent_id,
                agent_name="Resource Finder",
                query=query,
                result_count=len(results),
                snippet=results[0].get("title", "") if results else "No results",
            )
        except Exception as e:
            logger.warning("Resource search failed for '%s': %s", query, e)

    return found_urls


# ── Main session runner ──────────────────────────────────────────────────────

async def run_research_session(session_id: str, topic: str, user_id: str) -> None:
    """Execute a research session with concurrency control.

    Phases:
    1. CLASSIFY: Detect intent and domain
    2. GENERATE: Create expert guide from training knowledge (the main output)
    3. SEARCH: Find URLs/resources to link (supplementary)
    4. ENHANCE: Add found resources to the guide
    """
    session = ResearchSession(
        session_id=session_id,
        topic=topic,
        user_id=user_id,
        status="spawning",
    )
    _active_sessions[session_id] = session

    logger.info("Starting research session %s for topic: %s", session_id, topic[:100])

    try:
        async with _session_semaphore:
            await _run_research_phases(session)
    except Exception as e:
        logger.error("Research session %s failed: %s", session_id, e, exc_info=True)
        session.status = "error"
        session.error = str(e)
        await _publish_event(session_id, "research_error", error=str(e))
    finally:
        async def cleanup():
            await asyncio.sleep(300)
            _active_sessions.pop(session_id, None)

        _create_logged_task(cleanup(), name=f"cleanup-{session_id}")


async def _run_research_phases(session: ResearchSession) -> None:
    """Execute the research phases (runs inside the semaphore)."""
    session_id = session.session_id

    # Phase 1: CLASSIFY intent
    logger.info("Session %s: Phase 1 - Classifying intent", session_id)
    classification = classify_intent(session.topic)

    session.intent = classification.primary_intent.value
    session.domain = classification.domain
    session.complexity = classification.complexity
    session.keywords = classification.keywords_detected

    logger.info(
        "Session %s: Intent=%s, Domain=%s, Keywords=%s",
        session_id, session.intent, session.domain, session.keywords[:5],
    )

    await _publish_event(
        session_id, "research_phase", phase="spawning",
        intent=session.intent, domain=session.domain,
    )

    # Create agent representation for UI
    agent_id = f"expert_{session_id}"
    session.agents = [{
        "id": agent_id,
        "name": "Expert System",
        "avatar": "\U0001f9e0",
        "expertise": f"Comprehensive {session.domain} knowledge",
        "tone": "authoritative",
    }]

    await _publish_event(
        session_id, "research_agents_spawned",
        agents=session.agents, intent=session.intent,
    )

    if session.cancel_requested:
        return

    # Phase 2: GENERATE expert guide
    session.status = "synthesizing"
    await _publish_event(session_id, "research_phase", phase="synthesizing")

    await _publish_event(
        session_id, "agent_search_started",
        agent_id=agent_id,
        agent_name="Expert System",
        query="Generating comprehensive guide from training knowledge...",
    )

    synthesis = await _generate_expert_guide(session.topic, classification, session_id)

    await _publish_event(
        session_id, "agent_finding",
        agent_id=agent_id,
        agent_name="Expert System",
        avatar="\U0001f9e0",
        content="Expert guide generated successfully",
    )

    if session.cancel_requested:
        return

    # Phase 3: SEARCH for supplementary URLs
    session.status = "researching"
    await _publish_event(session_id, "research_phase", phase="researching")

    found_urls = await _search_for_resources(session, session_id, agent_id)

    if found_urls:
        synthesis += "\n\n## Additional Resources Found\n\n" + "\n".join(found_urls[:10])

    session.synthesis = synthesis
    session.findings = [synthesis]

    await _publish_event(session_id, "research_synthesis", content=synthesis)

    if session.cancel_requested:
        return

    # Phase 4: Complete
    session.status = "complete"
    await _publish_event(
        session_id, "research_complete",
        synthesis_preview=synthesis[:1000] if synthesis else "",
    )

    logger.info(
        "Research session %s complete: guide generated (%d chars)",
        session_id, len(synthesis) if synthesis else 0,
    )
