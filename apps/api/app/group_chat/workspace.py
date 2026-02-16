"""Shared Workspace for Multi-Agent Collaboration.

A central workspace where agents can:
- View and claim tasks (sub-problems to solve)
- Add findings (research, insights, data)
- Propose and vote on decisions
- Reference each other's work

This enables true collaboration rather than just taking turns.

NOW WITH DATABASE PERSISTENCE - workspace survives restarts and can be reviewed after chats.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import json

logger = logging.getLogger(__name__)

# Flag to enable async DB persistence (runs in background)
PERSIST_TO_DB = True


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_DISCUSSION = "needs_discussion"


@dataclass
class WorkspaceTask:
    """A sub-task that agents can claim and complete."""
    id: str
    title: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: str | None = None
    created_by: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    result: str | None = None
    dependencies: list[str] = field(default_factory=list)  # Task IDs this depends on

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "assigned_to": self.assigned_to,
            "created_by": self.created_by,
            "result": self.result,
            "dependencies": self.dependencies,
        }


@dataclass
class Finding:
    """A research finding, insight, or piece of data contributed by an agent."""
    id: str
    content: str
    source_agent: str
    category: str = "general"  # research, insight, data, reference
    confidence: float = 0.7
    references: list[str] = field(default_factory=list)  # Other finding IDs or agent names
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content[:500],  # Truncate for display
            "source_agent": self.source_agent,
            "category": self.category,
            "confidence": self.confidence,
            "references": self.references,
            "tags": self.tags,
        }


@dataclass
class Decision:
    """A proposed or approved decision for the group."""
    id: str
    title: str
    description: str
    proposed_by: str
    status: DecisionStatus = DecisionStatus.PROPOSED
    votes_for: list[str] = field(default_factory=list)
    votes_against: list[str] = field(default_factory=list)
    rationale: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "proposed_by": self.proposed_by,
            "status": self.status.value,
            "votes_for": self.votes_for,
            "votes_against": self.votes_against,
            "rationale": self.rationale,
        }


class SharedWorkspace:
    """Central workspace for multi-agent collaboration.

    Agents interact with this via tools:
    - read_workspace: See all tasks, findings, decisions
    - add_finding: Contribute research/insight
    - claim_task: Take ownership of a task
    - complete_task: Mark task done with result
    - propose_decision: Propose a group decision
    - vote_on_decision: Support or oppose a decision
    """

    def __init__(self, group_chat_id: int, topic: str):
        self.group_chat_id = group_chat_id
        self.topic = topic
        self.created_at = datetime.now(timezone.utc).isoformat()

        # Core data structures
        self.tasks: dict[str, WorkspaceTask] = {}
        self.findings: dict[str, Finding] = {}
        self.decisions: dict[str, Decision] = {}

        # Counters for ID generation
        self._task_counter = 0
        self._finding_counter = 0
        self._decision_counter = 0

        # Goal tracking
        self.main_goal: str = ""
        self.sub_goals: list[str] = []
        self.progress_summary: str = ""

    # ═══════════════════════════════════════════════════════════════════════════
    # TASK MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════

    def create_task(
        self,
        title: str,
        description: str,
        created_by: str,
        dependencies: list[str] | None = None,
        deliverable_type: str = "",
    ) -> WorkspaceTask:
        """Create a new task in the workspace."""
        self._task_counter += 1
        task_id = f"task_{self._task_counter}"

        task = WorkspaceTask(
            id=task_id,
            title=title,
            description=description,
            created_by=created_by,
            dependencies=dependencies or [],
        )
        self.tasks[task_id] = task

        logger.info("Task created: %s by %s", title, created_by)

        # Persist to database asynchronously
        if PERSIST_TO_DB:
            asyncio.create_task(self._persist_task(task, deliverable_type))

        return task

    async def _persist_task(self, task: WorkspaceTask, deliverable_type: str = "") -> None:
        """Persist task to database."""
        try:
            from app.db import save_workspace_task
            await save_workspace_task(
                group_chat_id=self.group_chat_id,
                task_key=task.id,
                title=task.title,
                description=task.description,
                created_by=task.created_by,
                deliverable_type=deliverable_type,
                status=task.status.value,
                assigned_to=task.assigned_to,
                result=task.result,
            )
        except Exception as e:
            logger.error("Failed to persist task: %s", e)

    def claim_task(self, task_id: str, agent: str) -> tuple[bool, str]:
        """Agent claims a task to work on."""
        if task_id not in self.tasks:
            return False, f"Task {task_id} not found"

        task = self.tasks[task_id]

        if task.status == TaskStatus.COMPLETED:
            return False, f"Task '{task.title}' is already completed"

        if task.assigned_to and task.assigned_to != agent:
            return False, f"Task '{task.title}' is assigned to {task.assigned_to}"

        # Check dependencies
        for dep_id in task.dependencies:
            if dep_id in self.tasks:
                dep_task = self.tasks[dep_id]
                if dep_task.status != TaskStatus.COMPLETED:
                    return False, f"Task blocked by incomplete dependency: {dep_task.title}"

        task.assigned_to = agent
        task.status = TaskStatus.IN_PROGRESS

        logger.info("Task claimed: %s by %s", task.title, agent)

        # Persist to database
        if PERSIST_TO_DB:
            asyncio.create_task(self._persist_task(task))

        return True, f"You are now working on: {task.title}"

    def complete_task(self, task_id: str, agent: str, result: str) -> tuple[bool, str]:
        """Mark a task as completed with result."""
        if task_id not in self.tasks:
            return False, f"Task {task_id} not found"

        task = self.tasks[task_id]

        if task.assigned_to and task.assigned_to != agent:
            return False, f"Task is assigned to {task.assigned_to}, not you"

        task.status = TaskStatus.COMPLETED
        task.result = result
        task.completed_at = datetime.now(timezone.utc).isoformat()

        logger.info("Task completed: %s by %s", task.title, agent)

        # Persist to database
        if PERSIST_TO_DB:
            asyncio.create_task(self._persist_task(task))

        return True, f"Task '{task.title}' completed"

    def get_available_tasks(self) -> list[WorkspaceTask]:
        """Get tasks that are available to claim."""
        available = []
        for task in self.tasks.values():
            if task.status == TaskStatus.PENDING:
                # Check if all dependencies are complete
                deps_complete = all(
                    self.tasks.get(dep_id, WorkspaceTask(id="", title="", description="")).status == TaskStatus.COMPLETED
                    for dep_id in task.dependencies
                )
                if deps_complete:
                    available.append(task)
        return available

    def get_tasks_for_agent(self, agent: str) -> list[WorkspaceTask]:
        """Get tasks assigned to a specific agent."""
        return [t for t in self.tasks.values() if t.assigned_to == agent]

    # ═══════════════════════════════════════════════════════════════════════════
    # FINDINGS MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════

    def _check_duplicate_finding(self, content: str) -> tuple[bool, str | None]:
        """Check if this finding is too similar to existing ones.

        Returns (is_duplicate, existing_finding_id) if duplicate found.
        Uses simple keyword overlap for efficiency.
        """
        # Extract significant words (>4 chars) from new content
        new_words = set(
            word.lower() for word in content.split()
            if len(word) > 4 and word.isalpha()
        )

        if len(new_words) < 3:
            return False, None

        for finding in self.findings.values():
            existing_words = set(
                word.lower() for word in finding.content.split()
                if len(word) > 4 and word.isalpha()
            )

            if not existing_words:
                continue

            # Calculate Jaccard similarity
            intersection = len(new_words & existing_words)
            union = len(new_words | existing_words)
            similarity = intersection / union if union > 0 else 0

            # High overlap = likely duplicate
            if similarity > 0.6:
                return True, finding.id

        return False, None

    def add_finding(
        self,
        content: str,
        source_agent: str,
        category: str = "general",
        confidence: float = 0.7,
        references: list[str] | None = None,
        tags: list[str] | None = None,
        force: bool = False,  # Skip duplicate check
    ) -> Finding | tuple[bool, str]:
        """Add a finding to the shared knowledge base.

        Returns Finding if added, or (False, message) if rejected as duplicate.
        """
        # Check for duplicates unless forced
        if not force:
            is_dup, existing_id = self._check_duplicate_finding(content)
            if is_dup:
                existing = self.findings.get(existing_id)
                msg = f"REJECTED: This finding is too similar to {existing_id} by @{existing.source_agent if existing else 'unknown'}. Reference it instead of restating."
                logger.warning("Duplicate finding rejected from %s", source_agent)
                return (False, msg)

        self._finding_counter += 1
        finding_id = f"finding_{self._finding_counter}"

        finding = Finding(
            id=finding_id,
            content=content,
            source_agent=source_agent,
            category=category,
            confidence=confidence,
            references=references or [],
            tags=tags or [],
        )
        self.findings[finding_id] = finding

        logger.info("Finding added by %s: %s...", source_agent, content[:50])

        # Persist to database
        if PERSIST_TO_DB:
            asyncio.create_task(self._persist_finding(finding))

        return finding

    async def _persist_finding(self, finding: Finding) -> None:
        """Persist finding to database."""
        try:
            from app.db import save_workspace_finding
            await save_workspace_finding(
                group_chat_id=self.group_chat_id,
                finding_key=finding.id,
                content=finding.content,
                source_agent=finding.source_agent,
                category=finding.category,
                confidence=finding.confidence,
                tags=finding.tags,
            )
        except Exception as e:
            logger.error("Failed to persist finding: %s", e)

    def get_findings_by_category(self, category: str) -> list[Finding]:
        """Get findings filtered by category."""
        return [f for f in self.findings.values() if f.category == category]

    def get_findings_by_agent(self, agent: str) -> list[Finding]:
        """Get findings contributed by a specific agent."""
        return [f for f in self.findings.values() if f.source_agent == agent]

    def search_findings(self, query: str) -> list[Finding]:
        """Search findings by content or tags."""
        query_lower = query.lower()
        results = []
        for finding in self.findings.values():
            if query_lower in finding.content.lower():
                results.append(finding)
            elif any(query_lower in tag.lower() for tag in finding.tags):
                results.append(finding)
        return results

    # ═══════════════════════════════════════════════════════════════════════════
    # DECISION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════

    def propose_decision(
        self,
        title: str,
        description: str,
        proposed_by: str,
        rationale: str = "",
    ) -> Decision:
        """Propose a decision for the group."""
        self._decision_counter += 1
        decision_id = f"decision_{self._decision_counter}"

        decision = Decision(
            id=decision_id,
            title=title,
            description=description,
            proposed_by=proposed_by,
            rationale=rationale,
        )
        # Proposer automatically votes for
        decision.votes_for.append(proposed_by)

        self.decisions[decision_id] = decision

        logger.info("Decision proposed by %s: %s", proposed_by, title)

        # Persist to database
        if PERSIST_TO_DB:
            asyncio.create_task(self._persist_decision(decision))

        return decision

    async def _persist_decision(self, decision: Decision) -> None:
        """Persist decision to database."""
        try:
            from app.db import save_workspace_decision
            await save_workspace_decision(
                group_chat_id=self.group_chat_id,
                decision_key=decision.id,
                title=decision.title,
                description=decision.description,
                proposed_by=decision.proposed_by,
                status=decision.status.value,
                votes_for=decision.votes_for,
                votes_against=decision.votes_against,
                rationale=decision.rationale,
            )
        except Exception as e:
            logger.error("Failed to persist decision: %s", e)

    def vote_on_decision(
        self,
        decision_id: str,
        agent: str,
        vote: bool,  # True = for, False = against
        reason: str = "",
    ) -> tuple[bool, str]:
        """Vote on a proposed decision."""
        if decision_id not in self.decisions:
            return False, f"Decision {decision_id} not found"

        decision = self.decisions[decision_id]

        if decision.status != DecisionStatus.PROPOSED:
            return False, f"Decision '{decision.title}' is already {decision.status.value}"

        # Remove from previous vote if changing
        if agent in decision.votes_for:
            decision.votes_for.remove(agent)
        if agent in decision.votes_against:
            decision.votes_against.remove(agent)

        # Add new vote
        if vote:
            decision.votes_for.append(agent)
        else:
            decision.votes_against.append(agent)

        # Check if decision is resolved (simple majority for now)
        total_votes = len(decision.votes_for) + len(decision.votes_against)
        if total_votes >= 3:  # Minimum votes to resolve
            if len(decision.votes_for) > len(decision.votes_against):
                decision.status = DecisionStatus.APPROVED
                decision.resolved_at = datetime.now(timezone.utc).isoformat()
            elif len(decision.votes_against) > len(decision.votes_for):
                decision.status = DecisionStatus.REJECTED
                decision.resolved_at = datetime.now(timezone.utc).isoformat()

        status_msg = f"voted {'for' if vote else 'against'}"
        if decision.status in (DecisionStatus.APPROVED, DecisionStatus.REJECTED):
            status_msg += f" - Decision {decision.status.value}!"

        logger.info("Vote on decision %s by %s: %s", decision.title, agent, vote)

        # Persist to database
        if PERSIST_TO_DB:
            asyncio.create_task(self._persist_decision(decision))

        return True, status_msg

    def get_pending_decisions(self) -> list[Decision]:
        """Get decisions that need votes."""
        return [d for d in self.decisions.values() if d.status == DecisionStatus.PROPOSED]

    def get_approved_decisions(self) -> list[Decision]:
        """Get approved decisions."""
        return [d for d in self.decisions.values() if d.status == DecisionStatus.APPROVED]

    # ═══════════════════════════════════════════════════════════════════════════
    # WORKSPACE SUMMARY
    # ═══════════════════════════════════════════════════════════════════════════

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the workspace state."""
        tasks_by_status = {
            "pending": len([t for t in self.tasks.values() if t.status == TaskStatus.PENDING]),
            "in_progress": len([t for t in self.tasks.values() if t.status == TaskStatus.IN_PROGRESS]),
            "completed": len([t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]),
        }

        return {
            "group_chat_id": self.group_chat_id,
            "topic": self.topic,
            "main_goal": self.main_goal,
            "tasks": tasks_by_status,
            "total_findings": len(self.findings),
            "pending_decisions": len(self.get_pending_decisions()),
            "approved_decisions": len(self.get_approved_decisions()),
        }

    def get_context_for_agent(self, agent: str) -> str:
        """Generate workspace context string for an agent's prompt."""
        parts = []

        # Main goal
        if self.main_goal:
            parts.append(f"MAIN GOAL: {self.main_goal}")
            parts.append("")

        # Tasks overview
        available_tasks = self.get_available_tasks()
        my_tasks = self.get_tasks_for_agent(agent)
        completed_tasks = [t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]

        if my_tasks:
            parts.append("YOUR ASSIGNED TASKS:")
            for task in my_tasks:
                parts.append(f"  [{task.status.value}] {task.title}: {task.description[:100]}")
            parts.append("")

        if available_tasks:
            parts.append("AVAILABLE TASKS (claim one matching your expertise):")
            for task in available_tasks[:5]:
                # Show title and expected deliverable
                parts.append(f"  • {task.id}: {task.title}")
                parts.append(f"    ↳ {task.description[:150]}")
            parts.append("")

        if completed_tasks:
            parts.append("COMPLETED WORK:")
            for task in completed_tasks[-5:]:
                result_preview = task.result[:100] if task.result else "No result"
                parts.append(f"  ✓ {task.title} (by {task.assigned_to}): {result_preview}")
            parts.append("")

        # Recent findings
        if self.findings:
            parts.append("SHARED FINDINGS:")
            for finding in list(self.findings.values())[-5:]:
                parts.append(f"  • [{finding.category}] @{finding.source_agent}: {finding.content[:100]}...")
            parts.append("")

        # Pending decisions
        pending = self.get_pending_decisions()
        if pending:
            parts.append("DECISIONS NEEDING YOUR VOTE:")
            for decision in pending:
                votes = f"+{len(decision.votes_for)}/-{len(decision.votes_against)}"
                parts.append(f"  • {decision.id}: {decision.title} ({votes})")
            parts.append("")

        # Approved decisions
        approved = self.get_approved_decisions()
        if approved:
            parts.append("APPROVED DECISIONS:")
            for decision in approved[-3:]:
                parts.append(f"  ✓ {decision.title}")
            parts.append("")

        return "\n".join(parts) if parts else "Workspace is empty. Start by adding findings or creating tasks."

    def to_dict(self) -> dict[str, Any]:
        """Serialize workspace to dictionary."""
        return {
            "group_chat_id": self.group_chat_id,
            "topic": self.topic,
            "main_goal": self.main_goal,
            "sub_goals": self.sub_goals,
            "tasks": [t.to_dict() for t in self.tasks.values()],
            "findings": [f.to_dict() for f in self.findings.values()],
            "decisions": [d.to_dict() for d in self.decisions.values()],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# WORKSPACE REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

_workspaces: dict[int, SharedWorkspace] = {}


async def _load_workspace_from_db(workspace: SharedWorkspace) -> None:
    """Load existing workspace data from database."""
    try:
        from app.db import get_workspace_tasks, get_workspace_findings, get_workspace_decisions

        # Load tasks
        db_tasks = await get_workspace_tasks(workspace.group_chat_id)
        for t in db_tasks:
            task = WorkspaceTask(
                id=t.get("task_key", f"task_{len(workspace.tasks)}"),
                title=t.get("title", ""),
                description=t.get("description", ""),
                status=TaskStatus(t.get("status", "pending")),
                assigned_to=t.get("assigned_to"),
                created_by=t.get("created_by", ""),
                result=t.get("result"),
            )
            workspace.tasks[task.id] = task

        # Load findings
        db_findings = await get_workspace_findings(workspace.group_chat_id)
        for f in db_findings:
            finding = Finding(
                id=f.get("finding_key", f"finding_{len(workspace.findings)}"),
                content=f.get("content", ""),
                source_agent=f.get("source_agent", ""),
                category=f.get("category", "general"),
                confidence=f.get("confidence", 0.7),
                tags=f.get("tags", []),
            )
            workspace.findings[finding.id] = finding

        # Load decisions
        db_decisions = await get_workspace_decisions(workspace.group_chat_id)
        for d in db_decisions:
            decision = Decision(
                id=d.get("decision_key", f"decision_{len(workspace.decisions)}"),
                title=d.get("title", ""),
                description=d.get("description", ""),
                proposed_by=d.get("proposed_by", ""),
                status=DecisionStatus(d.get("status", "proposed")),
                votes_for=d.get("votes_for", []),
                votes_against=d.get("votes_against", []),
                rationale=d.get("rationale", ""),
            )
            workspace.decisions[decision.id] = decision

        # Update counters
        workspace._task_counter = len(workspace.tasks)
        workspace._finding_counter = len(workspace.findings)
        workspace._decision_counter = len(workspace.decisions)

        if db_tasks or db_findings or db_decisions:
            logger.info(
                "Loaded workspace from DB: %d tasks, %d findings, %d decisions",
                len(db_tasks), len(db_findings), len(db_decisions)
            )
    except Exception as e:
        logger.error("Failed to load workspace from DB: %s", e)


def get_or_create_workspace(group_chat_id: int, topic: str) -> SharedWorkspace:
    """Get or create workspace for a group chat."""
    if group_chat_id not in _workspaces:
        _workspaces[group_chat_id] = SharedWorkspace(group_chat_id, topic)
        logger.info("Created workspace for chat %d: %s", group_chat_id, topic)
    return _workspaces[group_chat_id]


async def get_or_create_workspace_async(group_chat_id: int, topic: str) -> SharedWorkspace:
    """Get or create workspace, loading from DB if needed."""
    if group_chat_id not in _workspaces:
        workspace = SharedWorkspace(group_chat_id, topic)
        _workspaces[group_chat_id] = workspace
        # Load existing data from database
        await _load_workspace_from_db(workspace)
        logger.info("Created workspace for chat %d: %s (loaded from DB)", group_chat_id, topic)
    return _workspaces[group_chat_id]


def get_workspace(group_chat_id: int) -> SharedWorkspace | None:
    """Get workspace if it exists."""
    return _workspaces.get(group_chat_id)


def clear_workspace(group_chat_id: int) -> None:
    """Clear workspace when chat ends."""
    if group_chat_id in _workspaces:
        del _workspaces[group_chat_id]
        logger.info("Cleared workspace for chat %d", group_chat_id)
