"""Workspace collaboration tools: read, add findings, claim/complete tasks, propose/vote decisions."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from .shared import get_current_group_chat, _get_current_agent


@tool
def read_workspace() -> str:
    """Read the current state of the shared workspace.

    Use this to see:
    - The main goal and sub-goals
    - Available tasks you can claim
    - Tasks currently being worked on
    - Findings from other agents
    - Pending decisions that need votes

    Returns:
        A summary of the workspace state including tasks, findings, and decisions.
    """
    from app.group_chat.workspace import get_workspace

    group_chat_id = get_current_group_chat()
    if not group_chat_id:
        return json.dumps({
            "success": False,
            "error": "No active group chat context",
        })

    workspace = get_workspace(group_chat_id)
    if not workspace:
        return json.dumps({
            "success": False,
            "error": "No workspace found for this chat",
        })

    return json.dumps({
        "success": True,
        "summary": workspace.get_summary(),
        "available_tasks": [t.to_dict() for t in workspace.get_available_tasks()],
        "recent_findings": [f.to_dict() for f in list(workspace.findings.values())[-5:]],
        "pending_decisions": [d.to_dict() for d in workspace.get_pending_decisions()],
        "approved_decisions": [d.to_dict() for d in workspace.get_approved_decisions()],
    })


@tool
def add_finding(
    content: str,
    category: str = "insight",
    confidence: float = 0.7,
    tags: str = "",
) -> str:
    """Add a finding, insight, or piece of research to the shared workspace.

    Use this when you've discovered something valuable that other agents should know:
    - Research results from web searches
    - Key insights or conclusions
    - Important data points
    - Recommendations

    Args:
        content: The finding content (what you discovered or concluded)
        category: Type of finding - "research", "insight", "data", "recommendation"
        confidence: How confident you are (0.0-1.0), default 0.7
        tags: Comma-separated tags for categorization

    Returns:
        Confirmation with finding ID that others can reference.
    """
    from app.group_chat.workspace import get_workspace

    group_chat_id = get_current_group_chat()
    current_agent = _get_current_agent()

    if not group_chat_id:
        return json.dumps({"success": False, "error": "No active group chat"})

    workspace = get_workspace(group_chat_id)
    if not workspace:
        return json.dumps({"success": False, "error": "No workspace found"})

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    result = workspace.add_finding(
        content=content,
        source_agent=current_agent or "unknown",
        category=category,
        confidence=confidence,
        tags=tag_list,
    )

    # Handle duplicate rejection
    if isinstance(result, tuple):
        success, message = result
        return json.dumps({
            "success": False,
            "error": "DUPLICATE_REJECTED",
            "message": message,
            "instruction": "Reference the existing finding instead of restating it. Add NEW information only.",
        })

    # Success - finding was added
    return json.dumps({
        "success": True,
        "finding_id": result.id,
        "message": f"Finding recorded. Other agents can reference it as {result.id}.",
    })


@tool
def claim_task(task_id: str) -> str:
    """Claim a task from the workspace to work on.

    Check available tasks with read_workspace first, then claim one that
    matches your expertise. Only claim tasks you can actually complete.

    Args:
        task_id: The ID of the task to claim (e.g., "task_1")

    Returns:
        Success/failure message with task details.
    """
    from app.group_chat.workspace import get_workspace

    group_chat_id = get_current_group_chat()
    current_agent = _get_current_agent()

    if not group_chat_id:
        return json.dumps({"success": False, "error": "No active group chat"})

    workspace = get_workspace(group_chat_id)
    if not workspace:
        return json.dumps({"success": False, "error": "No workspace found"})

    success, message = workspace.claim_task(task_id, current_agent or "unknown")

    if success:
        task = workspace.tasks.get(task_id)
        return json.dumps({
            "success": True,
            "message": message,
            "task": task.to_dict() if task else None,
            "instructions": "Work on this task and call complete_task when done.",
        })
    else:
        return json.dumps({"success": False, "error": message})


@tool
def complete_task(task_id: str, result: str) -> str:
    """Mark a task as completed with your result.

    Call this after you've finished working on a claimed task.
    Provide a clear result that others can build upon.

    Args:
        task_id: The ID of the task you completed
        result: The outcome/result of your work (be specific and useful)

    Returns:
        Confirmation that the task is marked complete.
    """
    from app.group_chat.workspace import get_workspace

    group_chat_id = get_current_group_chat()
    current_agent = _get_current_agent()

    if not group_chat_id:
        return json.dumps({"success": False, "error": "No active group chat"})

    workspace = get_workspace(group_chat_id)
    if not workspace:
        return json.dumps({"success": False, "error": "No workspace found"})

    success, message = workspace.complete_task(task_id, current_agent or "unknown", result)

    return json.dumps({
        "success": success,
        "message": message if success else None,
        "error": message if not success else None,
    })


@tool
def propose_decision(
    title: str,
    description: str,
    rationale: str = "",
) -> str:
    """Propose a decision for the group to vote on.

    Use this when you've reached a conclusion that needs group consensus:
    - "Use approach X over approach Y"
    - "Recommend product Z for this use case"
    - "Focus on priority A before priority B"

    Other agents will vote, and the decision is approved when majority agrees.

    Args:
        title: Short title for the decision (e.g., "Use Redis for caching")
        description: Detailed description of what you're proposing
        rationale: Why you're proposing this (evidence, reasoning)

    Returns:
        Decision ID that others can vote on.
    """
    from app.group_chat.workspace import get_workspace

    group_chat_id = get_current_group_chat()
    current_agent = _get_current_agent()

    if not group_chat_id:
        return json.dumps({"success": False, "error": "No active group chat"})

    workspace = get_workspace(group_chat_id)
    if not workspace:
        return json.dumps({"success": False, "error": "No workspace found"})

    decision = workspace.propose_decision(
        title=title,
        description=description,
        proposed_by=current_agent or "unknown",
        rationale=rationale,
    )

    return json.dumps({
        "success": True,
        "decision_id": decision.id,
        "message": f"Decision proposed: {title}. Other agents can vote with vote_on_decision.",
        "current_votes": {
            "for": decision.votes_for,
            "against": decision.votes_against,
        },
    })


@tool
def vote_on_decision(
    decision_id: str,
    vote: bool,
    reason: str = "",
) -> str:
    """Vote on a proposed decision.

    Check pending decisions with read_workspace, then vote based on your
    expertise and perspective.

    Args:
        decision_id: The ID of the decision (e.g., "decision_1")
        vote: True to support, False to oppose
        reason: Optional explanation for your vote

    Returns:
        Updated vote counts and whether decision was resolved.
    """
    from app.group_chat.workspace import get_workspace

    group_chat_id = get_current_group_chat()
    current_agent = _get_current_agent()

    if not group_chat_id:
        return json.dumps({"success": False, "error": "No active group chat"})

    workspace = get_workspace(group_chat_id)
    if not workspace:
        return json.dumps({"success": False, "error": "No workspace found"})

    success, message = workspace.vote_on_decision(
        decision_id=decision_id,
        agent=current_agent or "unknown",
        vote=vote,
        reason=reason,
    )

    if success:
        decision = workspace.decisions.get(decision_id)
        return json.dumps({
            "success": True,
            "message": message,
            "current_votes": {
                "for": decision.votes_for if decision else [],
                "against": decision.votes_against if decision else [],
            },
            "status": decision.status.value if decision else "unknown",
        })
    else:
        return json.dumps({"success": False, "error": message})


@tool
def create_task(
    title: str,
    description: str,
) -> str:
    """Create a new task in the workspace for the team.

    Use this when you identify work that needs to be done but you're not
    the right agent to do it, or when breaking down a complex problem.

    Args:
        title: Short task title
        description: What needs to be done (be specific)

    Returns:
        Task ID that agents can claim.
    """
    from app.group_chat.workspace import get_workspace

    group_chat_id = get_current_group_chat()
    current_agent = _get_current_agent()

    if not group_chat_id:
        return json.dumps({"success": False, "error": "No active group chat"})

    workspace = get_workspace(group_chat_id)
    if not workspace:
        return json.dumps({"success": False, "error": "No workspace found"})

    task = workspace.create_task(
        title=title,
        description=description,
        created_by=current_agent or "unknown",
    )

    return json.dumps({
        "success": True,
        "task_id": task.id,
        "message": f"Task created: {title}. Agents can claim it with claim_task.",
    })
