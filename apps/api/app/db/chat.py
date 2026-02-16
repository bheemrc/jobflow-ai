"""Group chats, messages, proposals, and workspace queries."""

from __future__ import annotations

import json

from .core import get_conn
from .timeline import _resolve_user_id


# ── LangChain Chat History (Postgres-backed) ──

async def append_chat_message(
    session_id: str,
    role: str,
    content: str,
    agent: str = "",
    metadata: dict | None = None,
) -> int:
    """Append a chat message to the Postgres-backed history."""
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO langchain_chat_history (session_id, agent, role, content, metadata)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING id
        """, session_id, agent, role, content, json.dumps(metadata or {}))
        return row["id"]


async def get_chat_history(
    session_id: str,
    agent: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Retrieve chat history for a session, optionally filtered by agent."""
    async with get_conn() as conn:
        if agent:
            rows = await conn.fetch("""
                SELECT * FROM langchain_chat_history
                WHERE session_id = $1 AND agent = $2
                ORDER BY created_at ASC LIMIT $3
            """, session_id, agent, limit)
        else:
            rows = await conn.fetch("""
                SELECT * FROM langchain_chat_history
                WHERE session_id = $1
                ORDER BY created_at ASC LIMIT $2
            """, session_id, limit)
        result = []
        for r in rows:
            d = dict(r)
            if "created_at" in d and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            if "metadata" in d and isinstance(d["metadata"], str):
                try:
                    d["metadata"] = json.loads(d["metadata"])
                except Exception:
                    pass
            result.append(d)
        return result


async def clear_chat_history(session_id: str, agent: str | None = None) -> None:
    """Clear chat history for a session."""
    async with get_conn() as conn:
        if agent:
            await conn.execute(
                "DELETE FROM langchain_chat_history WHERE session_id = $1 AND agent = $2",
                session_id, agent,
            )
        else:
            await conn.execute(
                "DELETE FROM langchain_chat_history WHERE session_id = $1",
                session_id,
            )


# ── Group Chat CRUD Functions ──

async def create_group_chat(
    topic: str,
    participants: list[str],
    initiator: str,
    config: dict | None = None,
    user_id: str = "",
) -> int:
    """Create a new group chat session."""
    user_id = _resolve_user_id(user_id)
    config_data = config or {}
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO agent_group_chats (topic, participants, initiator, config, user_id,
                max_turns, max_tokens)
            VALUES ($1, $2::jsonb, $3, $4::jsonb, $5,
                $6, $7)
            RETURNING id
        """, topic, json.dumps(participants), initiator, json.dumps(config_data), user_id,
            config_data.get("max_turns", 20), config_data.get("max_tokens", 50000))
        return row["id"]


async def get_group_chat(group_chat_id: int, user_id: str = "") -> dict | None:
    """Get a group chat by ID."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM agent_group_chats
            WHERE id = $1 AND user_id = $2
        """, group_chat_id, user_id)
        return _serialize_group_chat(dict(row)) if row else None


async def get_group_chats(
    status: str | None = None,
    limit: int = 50,
    user_id: str = "",
) -> list[dict]:
    """Get group chats, optionally filtered by status."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        if status:
            rows = await conn.fetch("""
                SELECT * FROM agent_group_chats
                WHERE user_id = $1 AND status = $2
                ORDER BY created_at DESC LIMIT $3
            """, user_id, status, limit)
        else:
            rows = await conn.fetch("""
                SELECT * FROM agent_group_chats
                WHERE user_id = $1
                ORDER BY created_at DESC LIMIT $2
            """, user_id, limit)
        return [_serialize_group_chat(dict(r)) for r in rows]


async def add_group_chat_message(
    group_chat_id: int,
    agent: str,
    turn_number: int,
    mentions: list[str] | None = None,
    timeline_post_id: int | None = None,
    tokens_used: int = 0,
    user_id: str = "",
) -> int:
    """Add a message to a group chat."""
    user_id = _resolve_user_id(user_id)
    mentions_list = mentions or []
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO group_chat_messages
                (group_chat_id, agent, turn_number, mentions, timeline_post_id, tokens_used, user_id)
            VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
            RETURNING id
        """, group_chat_id, agent, turn_number, json.dumps(mentions_list),
            timeline_post_id, tokens_used, user_id)
        return row["id"]


async def get_group_chat_messages(
    group_chat_id: int,
    limit: int = 100,
    user_id: str = "",
) -> list[dict]:
    """Get messages for a group chat."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT gcm.*, tp.content, tp.post_type, tp.context
            FROM group_chat_messages gcm
            LEFT JOIN timeline_posts tp ON gcm.timeline_post_id = tp.id
            WHERE gcm.group_chat_id = $1 AND gcm.user_id = $2
            ORDER BY gcm.turn_number ASC, gcm.created_at ASC
            LIMIT $3
        """, group_chat_id, user_id, limit)
        return [_serialize_group_chat_message(dict(r)) for r in rows]


async def update_group_chat_stats(
    group_chat_id: int,
    turns_delta: int = 0,
    tokens_delta: int = 0,
    user_id: str = "",
) -> None:
    """Update turn and token counters for a group chat."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        await conn.execute("""
            UPDATE agent_group_chats
            SET turns_used = turns_used + $1, tokens_used = tokens_used + $2
            WHERE id = $3 AND user_id = $4
        """, turns_delta, tokens_delta, group_chat_id, user_id)


async def update_group_chat_status(
    group_chat_id: int,
    status: str,
    summary: str | None = None,
    user_id: str = "",
) -> None:
    """Update group chat status (active, paused, concluded)."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        if status == "concluded" and summary:
            await conn.execute("""
                UPDATE agent_group_chats
                SET status = $1, summary = $2, concluded_at = NOW()
                WHERE id = $3 AND user_id = $4
            """, status, summary, group_chat_id, user_id)
        else:
            await conn.execute("""
                UPDATE agent_group_chats
                SET status = $1
                WHERE id = $2 AND user_id = $3
            """, status, group_chat_id, user_id)


async def conclude_group_chat(
    group_chat_id: int,
    summary: str,
    user_id: str = "",
) -> None:
    """Mark a group chat as concluded with a summary."""
    await update_group_chat_status(group_chat_id, "concluded", summary, user_id)


async def add_group_chat_participant(
    group_chat_id: int,
    agent: str,
    user_id: str = "",
) -> None:
    """Add a participant to an existing group chat."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        # Use jsonb_build_array and concatenation to add agent if not already present
        await conn.execute("""
            UPDATE agent_group_chats
            SET participants = CASE
                WHEN participants ? $1 THEN participants
                ELSE participants || jsonb_build_array($1)
            END
            WHERE id = $2 AND user_id = $3
        """, agent, group_chat_id, user_id)


# ── Prompt Proposals CRUD ──

async def create_prompt_proposal(
    agent: str,
    proposed_changes: dict,
    rationale: str,
    group_chat_id: int | None = None,
    user_id: str = "",
) -> int:
    """Create a prompt change proposal."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO prompt_proposals
                (agent, proposed_changes, rationale, group_chat_id, user_id)
            VALUES ($1, $2::jsonb, $3, $4, $5)
            RETURNING id
        """, agent, json.dumps(proposed_changes), rationale, group_chat_id, user_id)
        return row["id"]


async def get_prompt_proposals(
    agent: str | None = None,
    status: str | None = None,
    limit: int = 50,
    user_id: str = "",
) -> list[dict]:
    """Get prompt proposals, optionally filtered."""
    user_id = _resolve_user_id(user_id)
    conditions = ["user_id = $1"]
    params: list = [user_id]
    idx = 2
    if agent:
        conditions.append(f"agent = ${idx}")
        params.append(agent)
        idx += 1
    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    where = " AND ".join(conditions)
    params.append(limit)
    async with get_conn() as conn:
        rows = await conn.fetch(f"""
            SELECT * FROM prompt_proposals
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ${idx}
        """, *params)
        return [_serialize_prompt_proposal(dict(r)) for r in rows]


async def get_prompt_proposal(proposal_id: int, user_id: str = "") -> dict | None:
    """Get a single prompt proposal by ID."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM prompt_proposals
            WHERE id = $1 AND user_id = $2
        """, proposal_id, user_id)
        return _serialize_prompt_proposal(dict(row)) if row else None


async def update_prompt_proposal_status(
    proposal_id: int,
    status: str,
    user_id: str = "",
) -> None:
    """Update proposal status (pending, approved, rejected, applied)."""
    user_id = _resolve_user_id(user_id)
    async with get_conn() as conn:
        if status == "applied":
            await conn.execute("""
                UPDATE prompt_proposals
                SET status = $1, applied_at = NOW()
                WHERE id = $2 AND user_id = $3
            """, status, proposal_id, user_id)
        else:
            await conn.execute("""
                UPDATE prompt_proposals
                SET status = $1
                WHERE id = $2 AND user_id = $3
            """, status, proposal_id, user_id)


async def apply_prompt_proposal(proposal_id: int, user_id: str = "") -> dict | None:
    """Mark a proposal as applied and return its details."""
    proposal = await get_prompt_proposal(proposal_id, user_id)
    if proposal and proposal.get("status") in ("pending", "approved"):
        await update_prompt_proposal_status(proposal_id, "applied", user_id)
        proposal["status"] = "applied"
    return proposal


# ══════════════════════════════════════════════════════════════════════════════
# WORKSPACE PERSISTENCE - Tasks, Findings, Decisions, Tool Calls
# ══════════════════════════════════════════════════════════════════════════════

async def save_workspace_task(
    group_chat_id: int,
    task_key: str,
    title: str,
    description: str,
    created_by: str,
    deliverable_type: str = "",
    status: str = "pending",
    assigned_to: str | None = None,
    result: str | None = None,
) -> int:
    """Save or update a workspace task."""
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO workspace_tasks
                (group_chat_id, task_key, title, description, deliverable_type,
                 status, assigned_to, created_by, result)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (group_chat_id, task_key)
            DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                status = EXCLUDED.status,
                assigned_to = EXCLUDED.assigned_to,
                result = EXCLUDED.result,
                completed_at = CASE WHEN EXCLUDED.status = 'completed' THEN NOW() ELSE workspace_tasks.completed_at END
            RETURNING id
        """, group_chat_id, task_key, title, description, deliverable_type,
            status, assigned_to, created_by, result)
        return row["id"]


async def get_workspace_tasks(group_chat_id: int) -> list[dict]:
    """Get all tasks for a workspace."""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM workspace_tasks
            WHERE group_chat_id = $1
            ORDER BY created_at ASC
        """, group_chat_id)
        return [_serialize_workspace_item(dict(r)) for r in rows]


async def save_workspace_finding(
    group_chat_id: int,
    finding_key: str,
    content: str,
    source_agent: str,
    category: str = "general",
    confidence: float = 0.7,
    tags: list[str] | None = None,
) -> int:
    """Save a workspace finding."""
    tags_json = json.dumps(tags or [])
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO workspace_findings
                (group_chat_id, finding_key, content, source_agent, category, confidence, tags)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
            ON CONFLICT (group_chat_id, finding_key)
            DO UPDATE SET
                content = EXCLUDED.content,
                confidence = EXCLUDED.confidence,
                tags = EXCLUDED.tags
            RETURNING id
        """, group_chat_id, finding_key, content, source_agent, category, confidence, tags_json)
        return row["id"]


async def get_workspace_findings(group_chat_id: int) -> list[dict]:
    """Get all findings for a workspace."""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM workspace_findings
            WHERE group_chat_id = $1
            ORDER BY created_at ASC
        """, group_chat_id)
        return [_serialize_workspace_item(dict(r)) for r in rows]


async def save_workspace_decision(
    group_chat_id: int,
    decision_key: str,
    title: str,
    description: str,
    proposed_by: str,
    status: str = "proposed",
    votes_for: list[str] | None = None,
    votes_against: list[str] | None = None,
    rationale: str = "",
) -> int:
    """Save or update a workspace decision."""
    votes_for_json = json.dumps(votes_for or [])
    votes_against_json = json.dumps(votes_against or [])
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO workspace_decisions
                (group_chat_id, decision_key, title, description, proposed_by,
                 status, votes_for, votes_against, rationale)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9)
            ON CONFLICT (group_chat_id, decision_key)
            DO UPDATE SET
                status = EXCLUDED.status,
                votes_for = EXCLUDED.votes_for,
                votes_against = EXCLUDED.votes_against,
                rationale = EXCLUDED.rationale,
                resolved_at = CASE WHEN EXCLUDED.status IN ('approved', 'rejected') THEN NOW() ELSE workspace_decisions.resolved_at END
            RETURNING id
        """, group_chat_id, decision_key, title, description, proposed_by,
            status, votes_for_json, votes_against_json, rationale)
        return row["id"]


async def get_workspace_decisions(group_chat_id: int) -> list[dict]:
    """Get all decisions for a workspace."""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM workspace_decisions
            WHERE group_chat_id = $1
            ORDER BY created_at ASC
        """, group_chat_id)
        return [_serialize_workspace_item(dict(r)) for r in rows]


async def save_tool_call(
    group_chat_id: int,
    agent: str,
    turn_number: int,
    tool_name: str,
    tool_args: dict | None = None,
    tool_result: str | None = None,
) -> int:
    """Save a tool call for display in UI."""
    args_json = json.dumps(tool_args or {})
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO agent_tool_calls
                (group_chat_id, agent, turn_number, tool_name, tool_args, tool_result)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6)
            RETURNING id
        """, group_chat_id, agent, turn_number, tool_name, args_json, tool_result)
        return row["id"]


async def get_tool_calls(group_chat_id: int, turn_number: int | None = None) -> list[dict]:
    """Get tool calls for a group chat, optionally filtered by turn."""
    async with get_conn() as conn:
        if turn_number is not None:
            rows = await conn.fetch("""
                SELECT * FROM agent_tool_calls
                WHERE group_chat_id = $1 AND turn_number = $2
                ORDER BY created_at ASC
            """, group_chat_id, turn_number)
        else:
            rows = await conn.fetch("""
                SELECT * FROM agent_tool_calls
                WHERE group_chat_id = $1
                ORDER BY turn_number ASC, created_at ASC
            """, group_chat_id)
        return [_serialize_workspace_item(dict(r)) for r in rows]


async def get_full_workspace(group_chat_id: int) -> dict:
    """Get the complete workspace state for a group chat."""
    tasks = await get_workspace_tasks(group_chat_id)
    findings = await get_workspace_findings(group_chat_id)
    decisions = await get_workspace_decisions(group_chat_id)
    tool_calls = await get_tool_calls(group_chat_id)

    return {
        "group_chat_id": group_chat_id,
        "tasks": tasks,
        "findings": findings,
        "decisions": decisions,
        "tool_calls": tool_calls,
        "summary": {
            "total_tasks": len(tasks),
            "completed_tasks": len([t for t in tasks if t.get("status") == "completed"]),
            "total_findings": len(findings),
            "total_decisions": len(decisions),
            "approved_decisions": len([d for d in decisions if d.get("status") == "approved"]),
        },
    }


# ── Serializers ──

def _serialize_group_chat(d: dict) -> dict:
    """Serialize group chat for JSON response."""
    for key in ("created_at", "concluded_at"):
        if key in d and hasattr(d[key], "isoformat"):
            d[key] = d[key].isoformat() if d[key] else None
    for jkey in ("participants", "config"):
        if jkey in d and isinstance(d[jkey], str):
            try:
                d[jkey] = json.loads(d[jkey])
            except Exception:
                pass
    return d


def _serialize_group_chat_message(d: dict) -> dict:
    """Serialize group chat message for JSON response."""
    if "created_at" in d and hasattr(d["created_at"], "isoformat"):
        d["created_at"] = d["created_at"].isoformat()
    for jkey in ("mentions", "context"):
        if jkey in d and isinstance(d[jkey], str):
            try:
                d[jkey] = json.loads(d[jkey])
            except Exception:
                pass
    return d


def _serialize_prompt_proposal(d: dict) -> dict:
    """Serialize prompt proposal for JSON response."""
    for key in ("created_at", "applied_at"):
        if key in d and hasattr(d[key], "isoformat"):
            d[key] = d[key].isoformat() if d[key] else None
    if "proposed_changes" in d and isinstance(d["proposed_changes"], str):
        try:
            d["proposed_changes"] = json.loads(d["proposed_changes"])
        except Exception:
            pass
    return d


def _serialize_workspace_item(d: dict) -> dict:
    """Serialize workspace item for JSON response."""
    for key in ("created_at", "completed_at", "resolved_at"):
        if key in d and hasattr(d[key], "isoformat"):
            d[key] = d[key].isoformat() if d[key] else None
    for jkey in ("tags", "votes_for", "votes_against", "tool_args"):
        if jkey in d and isinstance(d[jkey], str):
            try:
                d[jkey] = json.loads(d[jkey])
            except Exception:
                pass
    return d
