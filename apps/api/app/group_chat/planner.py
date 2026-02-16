"""Problem-Solving Planner for Multi-Agent Orchestration.

The Planner is an LLM-powered component that:
1. Analyzes the problem/topic to understand what needs to be solved
2. Creates a plan with sub-tasks
3. Determines what skills/agents are needed
4. Spawns the right agents dynamically
5. Monitors progress and adjusts the plan

This transforms group chats from "agents taking turns" to
"agents collaborating to solve a problem."
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.group_chat.workspace import (
    SharedWorkspace,
    get_or_create_workspace_async,
)

logger = logging.getLogger(__name__)

# Timeout for planner LLM calls
PLANNER_TIMEOUT = 45


@dataclass
class AgentSpec:
    """Specification for an agent to spawn."""
    name: str
    role: str
    expertise: list[str]
    reason: str


@dataclass
class TaskSpec:
    """Specification for a task in the plan."""
    title: str
    description: str
    deliverable_type: str = ""  # COMPARISON_TABLE, CALCULATION, DECISION_MATRIX, etc.
    suggested_agent: str | None = None
    dependencies: list[str] = field(default_factory=list)


@dataclass
class Plan:
    """A problem-solving plan created by the planner."""
    topic: str
    main_goal: str
    sub_goals: list[str]
    tasks: list[TaskSpec]
    required_agents: list[AgentSpec]
    approach: str
    success_criteria: str


PLANNER_SYSTEM_PROMPT = """You are a Problem-Solving Planner creating execution plans for AI agent teams.

CRITICAL: Each task must require a SPECIFIC DELIVERABLE with numbers/data. NO vague tasks.

AGENT TYPES (combine org + role):
- Engineer: Specs, calculations, constraints (NASAEngineer, ThermalEngineer)
- Analyst: Quantified comparisons, trade-offs (CostAnalyst, RiskAnalyst)
- Architect: System designs, block diagrams (SystemArchitect)
- Specialist: Deep domain expertise (RadiationSpecialist, RFSpecialist)
- Critic: ALWAYS INCLUDE ONE - challenges assumptions, finds gaps

MANDATORY: Every plan MUST include a Critic agent.

TASK DELIVERABLE TYPES (each task must specify exactly one):
- COMPARISON_TABLE: "Compare X options with ≥4 criteria, actual values"
- CALCULATION: "Calculate X given Y inputs, show formula and result"
- DECISION_MATRIX: "Score options 1-10 on weighted criteria, recommend one"
- SPEC_SHEET: "List requirements with specific numbers (voltage, mass, temp range)"
- RISK_ANALYSIS: "Identify ≥3 risks with probability and impact ratings"
- CHALLENGE_BRIEF: "Find ≥3 weaknesses in the current approach with evidence"

❌ BAD TASK: "Research radiation shielding options"
✓ GOOD TASK: "COMPARISON_TABLE: Compare ≥4 shielding materials (Tantalum, BeO, Al, Polyethylene) on density, cost/kg, TID protection at 2mm, availability"

RESPOND WITH VALID JSON:
{
  "main_goal": "One sentence with measurable outcome",
  "sub_goals": ["Specific milestone 1", "Specific milestone 2"],
  "approach": "Method in 1-2 sentences",
  "tasks": [
    {
      "title": "Brief title",
      "deliverable_type": "COMPARISON_TABLE | CALCULATION | DECISION_MATRIX | SPEC_SHEET | RISK_ANALYSIS | CHALLENGE_BRIEF",
      "description": "Exactly what data/output is required",
      "suggested_agent": "AgentName"
    }
  ],
  "required_agents": [
    {
      "name": "AgentName",
      "role": "Specific Role",
      "expertise": ["skill1", "skill2"],
      "reason": "What unique value they provide"
    }
  ],
  "success_criteria": "Measurable: 'X comparison tables, Y calculations, decision on Z'"
}
"""


class ProblemPlanner:
    """Analyzes problems and creates execution plans."""

    def __init__(self):
        model_name = settings.openai_model or "gpt-4o"
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=0.3,  # Lower temp for structured planning
            max_tokens=2000,
            request_timeout=PLANNER_TIMEOUT,
        )

    async def analyze_and_plan(self, topic: str, context: str = "") -> Plan:
        """Analyze the problem and create an execution plan.

        Args:
            topic: The problem/topic to analyze
            context: Optional additional context (user requirements, constraints)

        Returns:
            A Plan object with goals, tasks, and required agents
        """
        user_message = f"""Analyze this problem and create an execution plan:

TOPIC: {topic}

{f"ADDITIONAL CONTEXT: {context}" if context else ""}

REQUIREMENTS:
1. Main goal with MEASURABLE outcome
2. 2-3 sub-goals (specific milestones)
3. 3-5 tasks - EACH must specify deliverable_type and exact output
4. 2-4 agents - MUST include at least one Critic agent
5. Success criteria with specific numbers

CRITICAL RULES:
- Every task MUST have a deliverable_type (COMPARISON_TABLE, CALCULATION, DECISION_MATRIX, SPEC_SHEET, RISK_ANALYSIS, or CHALLENGE_BRIEF)
- Every task description must specify WHAT DATA is required
- ALWAYS include a Critic agent whose job is to challenge assumptions
- Use specialized agents (NASAEngineer, CostAnalyst) not generic ones

Example good task:
{{"title": "Shielding Material Comparison", "deliverable_type": "COMPARISON_TABLE", "description": "Compare Tantalum, BeO, Al alloy, Polyethylene on: density (g/cm³), cost ($/kg), TID protection at 2mm (krad), mass for 100krad protection (kg/m²)", "suggested_agent": "MaterialsEngineer"}}
"""

        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]

        try:
            response = await asyncio.wait_for(
                self.llm.ainvoke(messages),
                timeout=PLANNER_TIMEOUT
            )

            content = response.content if hasattr(response, "content") else str(response)

            # Parse JSON response
            # Handle markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            plan_data = json.loads(content.strip())

            # Convert to Plan object
            tasks = [
                TaskSpec(
                    title=t["title"],
                    description=t["description"],
                    deliverable_type=t.get("deliverable_type", ""),
                    suggested_agent=t.get("suggested_agent"),
                    dependencies=t.get("dependencies", []),
                )
                for t in plan_data.get("tasks", [])
            ]

            agents = [
                AgentSpec(
                    name=a["name"],
                    role=a["role"],
                    expertise=a.get("expertise", []),
                    reason=a["reason"],
                )
                for a in plan_data.get("required_agents", [])
            ]

            # ALWAYS ensure a Critic agent is included
            has_critic = any("critic" in a.name.lower() for a in agents)
            if not has_critic:
                agents.append(AgentSpec(
                    name="Critic",
                    role="Critical Reviewer",
                    expertise=["assumption testing", "risk identification", "devil's advocate"],
                    reason="Challenges assumptions and identifies weaknesses in the approach",
                ))

            plan = Plan(
                topic=topic,
                main_goal=plan_data.get("main_goal", topic),
                sub_goals=plan_data.get("sub_goals", []),
                tasks=tasks,
                required_agents=agents,
                approach=plan_data.get("approach", ""),
                success_criteria=plan_data.get("success_criteria", ""),
            )

            logger.info(
                "Plan created: %d tasks, %d agents (critic included) for '%s'",
                len(tasks), len(agents), topic[:50]
            )
            return plan

        except asyncio.TimeoutError:
            logger.error("Planner timeout for topic: %s", topic[:50])
            return self._create_fallback_plan(topic)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse planner response: %s", e)
            return self._create_fallback_plan(topic)
        except Exception as e:
            logger.error("Planner error: %s", e)
            return self._create_fallback_plan(topic)

    def _create_fallback_plan(self, topic: str) -> Plan:
        """Create a basic fallback plan if LLM fails."""
        return Plan(
            topic=topic,
            main_goal=f"Discuss and analyze: {topic}",
            sub_goals=["Research the topic", "Identify key considerations", "Form recommendations"],
            tasks=[
                TaskSpec(
                    title="Research current state",
                    description=f"Research the current state of {topic}",
                    suggested_agent="Researcher",
                ),
                TaskSpec(
                    title="Analyze options",
                    description=f"Analyze different approaches to {topic}",
                    suggested_agent="Analyst",
                ),
                TaskSpec(
                    title="Synthesize recommendations",
                    description="Combine research and analysis into recommendations",
                    suggested_agent=None,
                ),
            ],
            required_agents=[
                AgentSpec(
                    name="Researcher",
                    role="Research Specialist",
                    expertise=["research", "data gathering"],
                    reason="Need to gather information",
                ),
                AgentSpec(
                    name="Analyst",
                    role="Analysis Expert",
                    expertise=["analysis", "evaluation"],
                    reason="Need to evaluate options",
                ),
            ],
            approach="Research, analyze, and synthesize",
            success_criteria="Clear recommendations with supporting evidence",
        )


class PlanExecutor:
    """Executes a plan by spawning agents and creating tasks in workspace."""

    def __init__(self, workspace: SharedWorkspace):
        self.workspace = workspace

    async def execute_plan(self, plan: Plan) -> dict[str, Any]:
        """Execute a plan: spawn agents and create workspace tasks.

        Args:
            plan: The plan to execute

        Returns:
            Execution result with spawned agents and created tasks
        """
        from app.group_chat.dynamic_agents import (
            DynamicAgentFactory,
            register_dynamic_agent,
            get_dynamic_agent,
        )

        # Set workspace goals
        self.workspace.main_goal = plan.main_goal
        self.workspace.sub_goals = plan.sub_goals

        # Spawn required agents
        spawned_agents = []
        for agent_spec in plan.required_agents:
            # Check if already exists
            existing = get_dynamic_agent(agent_spec.name)
            if existing:
                spawned_agents.append({
                    "name": agent_spec.name,
                    "status": "already_exists",
                    "display_name": existing.display_name,
                })
                continue

            try:
                # Create the dynamic agent
                dynamic_agent = DynamicAgentFactory.create_from_mention(
                    name=agent_spec.name,
                    topic=plan.topic,
                    spawned_by="planner",
                    spawn_reason=agent_spec.reason,
                    group_chat_id=self.workspace.group_chat_id,
                )

                # Override with plan-specified values
                if agent_spec.role:
                    dynamic_agent.role = agent_spec.role
                if agent_spec.expertise:
                    dynamic_agent.expertise = agent_spec.expertise

                register_dynamic_agent(dynamic_agent)

                spawned_agents.append({
                    "name": dynamic_agent.name,
                    "status": "spawned",
                    "display_name": dynamic_agent.display_name,
                    "role": dynamic_agent.role,
                })

                logger.info("Planner spawned agent: %s (%s)", dynamic_agent.display_name, dynamic_agent.role)

            except Exception as e:
                logger.error("Failed to spawn agent %s: %s", agent_spec.name, e)
                spawned_agents.append({
                    "name": agent_spec.name,
                    "status": "failed",
                    "error": str(e),
                })

        # Create workspace tasks with deliverable requirements
        created_tasks = []
        task_id_map = {}  # Map task titles to IDs for dependencies

        for task_spec in plan.tasks:
            # Include deliverable type in description if specified
            description = task_spec.description
            if task_spec.deliverable_type:
                description = f"[{task_spec.deliverable_type}] {description}"

            task = self.workspace.create_task(
                title=task_spec.title,
                description=description,
                created_by="planner",
                dependencies=[],  # Will update after all tasks created
            )
            task_id_map[task_spec.title] = task.id
            created_tasks.append({
                "id": task.id,
                "title": task.title,
                "deliverable_type": task_spec.deliverable_type,
                "suggested_agent": task_spec.suggested_agent,
            })

        # Add initial finding about the plan
        self.workspace.add_finding(
            content=f"Plan created: {plan.main_goal}. Approach: {plan.approach}. "
                   f"Success criteria: {plan.success_criteria}",
            source_agent="planner",
            category="plan",
            confidence=0.9,
            tags=["plan", "goal"],
        )

        return {
            "main_goal": plan.main_goal,
            "sub_goals": plan.sub_goals,
            "approach": plan.approach,
            "spawned_agents": spawned_agents,
            "created_tasks": created_tasks,
            "success_criteria": plan.success_criteria,
        }


async def analyze_and_setup_workspace(
    group_chat_id: int,
    topic: str,
    context: str = "",
) -> dict[str, Any]:
    """Main entry point: analyze problem and set up collaborative workspace.

    Args:
        group_chat_id: The chat ID
        topic: The problem/topic
        context: Optional additional context

    Returns:
        Setup result with plan, agents, and tasks
    """
    # Create workspace (loads from DB if exists)
    workspace = await get_or_create_workspace_async(group_chat_id, topic)

    # Create and execute plan
    planner = ProblemPlanner()
    plan = await planner.analyze_and_plan(topic, context)

    executor = PlanExecutor(workspace)
    result = await executor.execute_plan(plan)

    logger.info(
        "Workspace setup complete for chat %d: %d agents, %d tasks",
        group_chat_id,
        len(result["spawned_agents"]),
        len(result["created_tasks"]),
    )

    return result
