"""Dynamic Agent Spawning System for Group Chats.

Enables agents to create specialized virtual experts on-the-fly based on
conversation needs. This allows discussions on ANY domain by spawning
appropriate specialists like:
- NASAAdvisor, MITProfessor, SystemsEngineer
- BusinessLeader, RadiationEngineer, ProcurementSpecialist

Dynamic agents have:
- Custom personas, roles, and expertise
- Defined responsibilities and expectations
- Specific tool access
- Spawn permissions for creating sub-agents

Supports:
- Expertise-based agent suggestions
- Dynamic joining based on topic relevance
- Community agents (user-defined personalities)
- Agent availability and load balancing
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT ROLE TEMPLATES - Templates for spawning dynamic agents
# ═══════════════════════════════════════════════════════════════════════════════

ROLE_TEMPLATES = {
    # Academic roles
    "professor": {
        "role_format": "{domain} Professor",
        "style": "Academic and rigorous. Cites research, explains concepts clearly, questions assumptions.",
        "tools": ["web_search", "tag_agent_in_chat", "spawn_agent"],
        "temperature": 0.6,
        "can_spawn": ["researcher", "student", "peer_reviewer", "domain_expert"],
    },
    "researcher": {
        "role_format": "{domain} Researcher",
        "style": "Thorough and data-driven. Digs deep, finds primary sources, quantifies findings.",
        "tools": ["web_search", "tag_agent_in_chat"],
        "temperature": 0.5,
        "can_spawn": ["data_analyst", "specialist"],
    },

    # Industry roles
    "engineer": {
        "role_format": "{domain} Engineer",
        "style": "Practical and specific. Focuses on implementation, considers constraints, provides specs.",
        "tools": ["web_search", "tag_agent_in_chat", "spawn_agent"],
        "temperature": 0.6,
        "can_spawn": ["technician", "specialist", "vendor_contact", "test_engineer"],
    },
    "architect": {
        "role_format": "{domain} Architect",
        "style": "Systems thinker. Considers trade-offs, scalability, integration, long-term implications.",
        "tools": ["web_search", "tag_agent_in_chat", "spawn_agent"],
        "temperature": 0.7,
        "can_spawn": ["engineer", "analyst", "specialist"],
    },

    # Advisory roles
    "advisor": {
        "role_format": "{domain} Advisor",
        "style": "Strategic and experienced. Gives clear recommendations with rationale, identifies risks.",
        "tools": ["web_search", "tag_agent_in_chat", "spawn_agent"],
        "temperature": 0.7,
        "can_spawn": ["specialist", "analyst", "consultant", "engineer"],
    },
    "consultant": {
        "role_format": "{domain} Consultant",
        "style": "Client-focused and practical. ROI-conscious, considers constraints, provides actionable steps.",
        "tools": ["web_search", "tag_agent_in_chat"],
        "temperature": 0.7,
        "can_spawn": ["analyst", "specialist"],
    },

    # Business roles
    "executive": {
        "role_format": "{domain} Executive",
        "style": "Decision-focused and time-conscious. Cuts to what matters, prioritizes, drives action.",
        "tools": ["web_search", "tag_agent_in_chat", "spawn_agent"],
        "temperature": 0.7,
        "can_spawn": ["analyst", "specialist", "advisor", "consultant"],
    },
    "leader": {
        "role_format": "{domain} Leader",
        "style": "Visionary and decisive. Sets direction, motivates action, considers team dynamics.",
        "tools": ["web_search", "tag_agent_in_chat", "spawn_agent"],
        "temperature": 0.7,
        "can_spawn": ["analyst", "specialist", "engineer"],
    },
    "analyst": {
        "role_format": "{domain} Analyst",
        "style": "Data-driven and objective. Creates comparisons, quantifies trade-offs, presents clearly.",
        "tools": ["web_search", "tag_agent_in_chat"],
        "temperature": 0.5,
        "can_spawn": [],
    },

    # Specialized roles
    "specialist": {
        "role_format": "{domain} Specialist",
        "style": "Deep expertise. Knows edge cases, provides precise technical details, flags non-obvious issues.",
        "tools": ["web_search", "tag_agent_in_chat"],
        "temperature": 0.5,
        "can_spawn": [],
    },
    "expert": {
        "role_format": "{domain} Expert",
        "style": "Authoritative knowledge. Provides definitive answers, explains nuances, corrects misconceptions.",
        "tools": ["web_search", "tag_agent_in_chat", "spawn_agent"],
        "temperature": 0.6,
        "can_spawn": ["specialist", "researcher"],
    },
    "critic": {
        "role_format": "{domain} Critic",
        "style": "Skeptical and thorough. Finds weaknesses, plays devil's advocate, stress-tests ideas.",
        "tools": ["web_search", "tag_agent_in_chat"],
        "temperature": 0.8,
        "can_spawn": [],
    },
}

# Organization prefixes that indicate domain/authority
ORG_DOMAINS = {
    "nasa": {"domain": "aerospace/space systems", "authority": "NASA standards and procedures"},
    "esa": {"domain": "aerospace/European space", "authority": "ESA standards and procedures"},
    "spacex": {"domain": "aerospace/commercial space", "authority": "NewSpace industry practices"},
    "mit": {"domain": "academic/research", "authority": "cutting-edge research and theory"},
    "stanford": {"domain": "academic/research", "authority": "academic rigor and innovation"},
    "harvard": {"domain": "academic/business", "authority": "business strategy and leadership"},
    "google": {"domain": "tech/software", "authority": "large-scale software systems"},
    "microsoft": {"domain": "tech/enterprise", "authority": "enterprise software practices"},
    "amazon": {"domain": "tech/cloud", "authority": "cloud infrastructure and operations"},
    "fda": {"domain": "medical/regulatory", "authority": "medical device and drug regulations"},
    "faa": {"domain": "aerospace/aviation", "authority": "aviation safety regulations"},
    "dod": {"domain": "defense", "authority": "military specifications and procedures"},
    "mil": {"domain": "defense", "authority": "military standards"},
}

# Domain-specific knowledge to inject
DOMAIN_CONTEXT = {
    "aerospace": {
        "standards": ["NASA GEVS", "MIL-STD-1553", "ECSS", "DO-178C", "AS9100"],
        "considerations": ["radiation hardening", "thermal vacuum", "vibration", "mass budget", "power budget"],
        "typical_questions": ["What's the TRL?", "Is it flight heritage?", "What's the radiation tolerance?"],
    },
    "software": {
        "standards": ["IEEE 730", "ISO 25010", "OWASP", "SOC 2"],
        "considerations": ["scalability", "latency", "security", "maintainability", "testing"],
        "typical_questions": ["What's the time complexity?", "How does it scale?", "What's the failure mode?"],
    },
    "hardware": {
        "standards": ["IPC-A-610", "J-STD-001", "MIL-PRF-38534"],
        "considerations": ["reliability", "MTBF", "supply chain", "thermal management", "EMI/EMC"],
        "typical_questions": ["What's the MTBF?", "Who's the second source?", "What's the operating temp range?"],
    },
    "business": {
        "standards": ["GAAP", "SOX", "ISO 9001"],
        "considerations": ["ROI", "market timing", "competitive moat", "risk", "cash flow"],
        "typical_questions": ["What's the payback period?", "Who are the competitors?", "What's the TAM?"],
    },
    "medical": {
        "standards": ["FDA 21 CFR", "ISO 13485", "IEC 62304", "HIPAA"],
        "considerations": ["patient safety", "clinical evidence", "regulatory pathway", "reimbursement"],
        "typical_questions": ["Is it 510(k) or PMA?", "What's the clinical evidence?", "What's the regulatory timeline?"],
    },
}


# Default agent archetypes with their expertise domains
AGENT_ARCHETYPES = {
    "oracle": {
        "display_name": "Oracle",
        "expertise": ["trends", "market", "predictions", "analysis", "patterns"],
        "style": "analytical",
        "description": "Spots patterns and predicts trends",
    },
    "architect": {
        "display_name": "Architect",
        "expertise": ["design", "systems", "structure", "technical", "implementation"],
        "style": "systematic",
        "description": "Designs systems and technical solutions",
    },
    "pathfinder": {
        "display_name": "Pathfinder",
        "expertise": ["strategy", "options", "alternatives", "exploration", "innovation"],
        "style": "exploratory",
        "description": "Finds alternative paths and creative solutions",
    },
    "strategist": {
        "display_name": "Strategist",
        "expertise": ["business", "planning", "risk", "competitive", "execution"],
        "style": "pragmatic",
        "description": "Creates actionable business strategies",
    },
    "cipher": {
        "display_name": "Cipher",
        "expertise": ["research", "data", "facts", "evidence", "verification"],
        "style": "rigorous",
        "description": "Digs deep into research and data",
    },
    "forge": {
        "display_name": "Forge",
        "expertise": ["skills", "development", "learning", "growth", "career"],
        "style": "practical",
        "description": "Builds skills and career development plans",
    },
    "catalyst": {
        "display_name": "Catalyst",
        "expertise": ["networking", "connections", "opportunities", "introductions"],
        "style": "connector",
        "description": "Creates connections and opportunities",
    },
    "sentinel": {
        "display_name": "Sentinel",
        "expertise": ["risk", "security", "compliance", "audit", "protection"],
        "style": "protective",
        "description": "Identifies risks and ensures safety",
    },
    "critic": {
        "display_name": "Critic",
        "expertise": ["analysis", "review", "challenge", "weakness", "assumptions"],
        "style": "skeptical",
        "description": "Challenges assumptions and finds weaknesses in proposals",
        "is_critic": True,  # Special flag for critic behavior
    },
    "compass": {
        "display_name": "Compass",
        "expertise": ["guidance", "mentorship", "feedback", "coaching", "direction"],
        "style": "supportive",
        "description": "Provides guidance and mentorship",
    },
    "nexus": {
        "display_name": "Nexus",
        "expertise": ["synthesis", "integration", "coordination", "summary"],
        "style": "integrative",
        "description": "Synthesizes ideas and coordinates efforts",
    },
}

# Topic keywords to agent mapping
TOPIC_EXPERTISE_MAP = {
    # Technology
    "software": ["architect", "cipher"],
    "code": ["architect", "cipher"],
    "api": ["architect", "cipher"],
    "database": ["architect", "cipher"],
    "cloud": ["architect", "strategist"],
    "ai": ["oracle", "cipher", "architect"],
    "ml": ["oracle", "cipher", "architect"],
    "machine learning": ["oracle", "cipher", "architect"],

    # Business
    "market": ["oracle", "strategist"],
    "business": ["strategist", "catalyst"],
    "startup": ["strategist", "pathfinder", "catalyst"],
    "investment": ["oracle", "strategist", "sentinel"],
    "funding": ["strategist", "catalyst"],
    "competitor": ["oracle", "strategist"],

    # Career
    "job": ["forge", "compass", "catalyst"],
    "career": ["forge", "compass", "pathfinder"],
    "interview": ["forge", "compass"],
    "resume": ["forge", "compass"],
    "salary": ["oracle", "strategist"],
    "skills": ["forge", "cipher"],

    # Research
    "research": ["cipher", "oracle"],
    "data": ["cipher", "oracle"],
    "study": ["cipher", "oracle"],
    "analysis": ["oracle", "cipher"],

    # Innovation
    "innovation": ["pathfinder", "architect"],
    "creative": ["pathfinder", "catalyst"],
    "idea": ["pathfinder", "oracle"],
    "solution": ["architect", "pathfinder"],

    # Risk & Compliance
    "risk": ["sentinel", "strategist"],
    "security": ["sentinel", "architect"],
    "compliance": ["sentinel", "cipher"],
    "legal": ["sentinel", "cipher"],
}


@dataclass
class AgentSuggestion:
    """A suggested agent for a group chat."""
    agent: str
    relevance_score: float
    reason: str
    expertise_match: list[str] = field(default_factory=list)


def suggest_agents_for_topic(
    topic: str,
    exclude: list[str] | None = None,
    max_suggestions: int = 4,
) -> list[AgentSuggestion]:
    """Suggest relevant agents based on topic keywords.

    Args:
        topic: The discussion topic
        exclude: Agents to exclude (already participating)
        max_suggestions: Maximum number of suggestions

    Returns:
        List of AgentSuggestion ordered by relevance
    """
    exclude = exclude or []
    topic_lower = topic.lower()

    # Score each agent
    agent_scores: dict[str, tuple[float, list[str]]] = {}

    for keyword, agents in TOPIC_EXPERTISE_MAP.items():
        if keyword in topic_lower:
            for agent in agents:
                if agent not in exclude and agent in AGENT_ARCHETYPES:
                    current_score, current_matches = agent_scores.get(agent, (0.0, []))
                    agent_scores[agent] = (current_score + 1.0, current_matches + [keyword])

    # Also check agent expertise directly
    for agent, config in AGENT_ARCHETYPES.items():
        if agent in exclude:
            continue
        for expertise in config.get("expertise", []):
            if expertise in topic_lower:
                current_score, current_matches = agent_scores.get(agent, (0.0, []))
                if expertise not in current_matches:
                    agent_scores[agent] = (current_score + 0.5, current_matches + [expertise])

    # Convert to suggestions
    suggestions = []
    for agent, (score, matches) in agent_scores.items():
        if score > 0:
            config = AGENT_ARCHETYPES[agent]
            suggestions.append(AgentSuggestion(
                agent=agent,
                relevance_score=score,
                reason=config.get("description", ""),
                expertise_match=matches,
            ))

    # Sort by relevance
    suggestions.sort(key=lambda x: x.relevance_score, reverse=True)

    return suggestions[:max_suggestions]


def get_default_participants(topic: str) -> list[str]:
    """Get default participant list based on topic.

    Returns 3-4 agents most relevant to the topic.
    """
    suggestions = suggest_agents_for_topic(topic, max_suggestions=4)

    if len(suggestions) >= 2:
        return [s.agent for s in suggestions]

    # Fallback to defaults if topic doesn't match
    return ["oracle", "architect", "pathfinder"]


@dataclass
class CommunityAgent:
    """A user-defined community agent."""
    id: str
    name: str
    display_name: str
    description: str
    prompt: str
    expertise: list[str] = field(default_factory=list)
    created_by: str = ""
    is_public: bool = False


# In-memory community agent storage (would be DB in production)
_community_agents: dict[str, CommunityAgent] = {}


def register_community_agent(agent: CommunityAgent) -> None:
    """Register a community-created agent."""
    _community_agents[agent.id] = agent
    logger.info("Registered community agent: %s", agent.id)


def get_community_agent(agent_id: str) -> CommunityAgent | None:
    """Get a community agent by ID."""
    return _community_agents.get(agent_id)


def list_community_agents(user_id: str | None = None, include_public: bool = True) -> list[CommunityAgent]:
    """List available community agents."""
    agents = []
    for agent in _community_agents.values():
        if agent.is_public or (user_id and agent.created_by == user_id):
            agents.append(agent)
    return agents


def analyze_expertise_gap(
    topic: str,
    current_participants: list[str],
    conversation_summary: str | None = None,
) -> list[AgentSuggestion]:
    """Analyze conversation and suggest agents to fill expertise gaps.

    Args:
        topic: The discussion topic
        current_participants: Currently active agents
        conversation_summary: Optional summary of conversation so far

    Returns:
        Agents that could add missing expertise
    """
    suggestions = suggest_agents_for_topic(
        topic,
        exclude=current_participants,
        max_suggestions=3,
    )

    # If we have a conversation summary, boost agents that address gaps
    if conversation_summary:
        summary_lower = conversation_summary.lower()

        # Check for gap indicators
        gap_keywords = {
            "risk": "sentinel",
            "technical": "architect",
            "market": "oracle",
            "career": "forge",
            "creative": "pathfinder",
            "network": "catalyst",
        }

        for keyword, agent in gap_keywords.items():
            if keyword in summary_lower and agent not in current_participants:
                # Add or boost this agent
                existing = next((s for s in suggestions if s.agent == agent), None)
                if existing:
                    existing.relevance_score += 1.0
                    existing.reason = f"Could help with {keyword} aspects"
                elif agent in AGENT_ARCHETYPES:
                    config = AGENT_ARCHETYPES[agent]
                    suggestions.append(AgentSuggestion(
                        agent=agent,
                        relevance_score=1.0,
                        reason=f"Could help with {keyword} aspects",
                        expertise_match=[keyword],
                    ))

        # Re-sort
        suggestions.sort(key=lambda x: x.relevance_score, reverse=True)

    return suggestions[:3]


def get_agent_availability() -> dict[str, bool]:
    """Get availability status of all agents.

    In production, this would check agent load, rate limits, etc.
    """
    return {agent: True for agent in AGENT_ARCHETYPES}


def get_agent_display_info(agent: str) -> dict[str, Any]:
    """Get display information for an agent."""
    # Check dynamic agents first
    dynamic = get_dynamic_agent(agent)
    if dynamic:
        return {
            "id": agent,
            "display_name": dynamic.display_name,
            "description": dynamic.responsibilities,
            "expertise": dynamic.expertise,
            "style": dynamic.style,
            "type": "dynamic",
            "role": dynamic.role,
            "spawned_by": dynamic.spawned_by,
        }

    if agent in AGENT_ARCHETYPES:
        config = AGENT_ARCHETYPES[agent]
        return {
            "id": agent,
            "display_name": config.get("display_name", agent.title()),
            "description": config.get("description", ""),
            "expertise": config.get("expertise", []),
            "style": config.get("style", "neutral"),
            "type": "system",
        }

    # Check community agents
    community = get_community_agent(agent)
    if community:
        return {
            "id": community.id,
            "display_name": community.display_name,
            "description": community.description,
            "expertise": community.expertise,
            "style": "community",
            "type": "community",
        }

    return {
        "id": agent,
        "display_name": agent.title(),
        "description": "",
        "expertise": [],
        "style": "unknown",
        "type": "unknown",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DYNAMIC AGENT - Runtime-created specialized agent
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DynamicAgent:
    """A dynamically spawned agent with specific expertise and behavior."""

    # Identity
    name: str  # lowercase key: "nasaadvisor"
    display_name: str  # Human-readable: "NASA Advisor"

    # Role & Expertise
    role: str  # "Space Systems Advisor"
    domain: str  # "aerospace"
    expertise: list[str] = field(default_factory=list)

    # Behavior Definition
    style: str = ""  # Communication style
    responsibilities: str = ""  # What they're responsible for
    expectations: str = ""  # What's expected of them

    # Capabilities
    tools: list[str] = field(default_factory=lambda: ["web_search", "tag_agent_in_chat"])
    can_spawn: list[str] = field(default_factory=list)  # Role templates they can spawn

    # LLM Settings
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 1500

    # Lineage
    spawned_by: str = ""  # Which agent created this one
    spawn_reason: str = ""  # Why they were spawned
    group_chat_id: int = 0  # Which chat they belong to

    def generate_system_prompt(self, topic: str, context: str) -> str:
        """Generate the full system prompt for this agent with STRICT contribution rules."""
        expertise_str = ", ".join(self.expertise) if self.expertise else "general domain knowledge"

        # Get domain-specific context dynamically based on domain
        domain_ctx = DOMAIN_CONTEXT.get(self.domain.split("/")[0], {})
        standards = domain_ctx.get("standards", [])
        considerations = domain_ctx.get("considerations", [])

        standards_str = f"Standards you must cite: {', '.join(standards)}" if standards else ""
        considerations_str = f"Factors requiring numbers: {', '.join(considerations)}" if considerations else ""

        prompt = f"""You are {self.display_name}, a {self.role}.

TOPIC: {topic}
EXPERTISE: {expertise_str}
{standards_str}
{considerations_str}

CONTEXT:
{context}

═══════════════════════════════════════════════════════════════════════════════
MANDATORY: USE YOUR TOOLS FIRST
═══════════════════════════════════════════════════════════════════════════════

You MUST use at least one tool before posting. Research, then speak.

1. web_search - Get real data, specs, costs, comparisons
2. add_finding - Document your research with specific numbers
3. claim_task / complete_task - Take workspace tasks and deliver results
4. propose_decision / vote_on_decision - Drive decisions forward with evidence

NEVER post without data from tool use. Vague opinions are worthless.

═══════════════════════════════════════════════════════════════════════════════
RULES FOR YOUR POST
═══════════════════════════════════════════════════════════════════════════════

1. LEAD WITH RESEARCH DATA
   ✓ "My web_search found: Tantalum at $850/kg provides 50 krad TID per 2mm"
   ✓ "Per vendor specs: [table with 3+ options compared]"
   ✗ "I think we should consider..." (no data = worthless)

2. MANDATORY SPECIFICS
   ✓ "15W dissipation needs 0.18m² radiator at ε=0.85 for -40°C to +85°C"
   ✗ "thermal management is important" (vague = rejected)

3. PRODUCE DELIVERABLES
   - Comparison tables with actual numbers
   - Calculations: inputs → formula → result
   - Decisions with quantified trade-offs

4. CHALLENGE WITH EVIDENCE
   - "That adds 8kg = $96k extra launch cost. Worth 5% reliability gain?"
   - "Your assumption conflicts with NASA GEVS section 4.3.2"

═══════════════════════════════════════════════════════════════════════════════
FORBIDDEN
═══════════════════════════════════════════════════════════════════════════════
- "I've reviewed the discussion..."
- "Building on what others said..."
- "It's important to consider..."
- Any post without specific numbers from your research

═══════════════════════════════════════════════════════════════════════════════
THIS TURN
═══════════════════════════════════════════════════════════════════════════════
1. Use web_search to research something specific
2. Use add_finding to document results with numbers
3. Post your analysis with concrete data
"""
        return prompt

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "role": self.role,
            "domain": self.domain,
            "expertise": self.expertise,
            "style": self.style,
            "responsibilities": self.responsibilities,
            "expectations": self.expectations,
            "tools": self.tools,
            "can_spawn": self.can_spawn,
            "model": self.model,
            "temperature": self.temperature,
            "spawned_by": self.spawned_by,
            "spawn_reason": self.spawn_reason,
            "group_chat_id": self.group_chat_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DynamicAgent":
        """Create from dictionary."""
        valid_fields = {f.name for f in field(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid_fields})


# ═══════════════════════════════════════════════════════════════════════════════
# DYNAMIC AGENT REGISTRY - Global storage for spawned agents
# ═══════════════════════════════════════════════════════════════════════════════

# Global registry: agent_name -> DynamicAgent
_dynamic_agents: dict[str, DynamicAgent] = {}


def register_dynamic_agent(agent: DynamicAgent) -> None:
    """Register a spawned dynamic agent."""
    _dynamic_agents[agent.name.lower()] = agent
    logger.info(
        "Registered dynamic agent: %s (%s) spawned by %s",
        agent.display_name, agent.role, agent.spawned_by or "system"
    )


def get_dynamic_agent(name: str) -> DynamicAgent | None:
    """Get a dynamic agent by name."""
    return _dynamic_agents.get(name.lower())


def list_dynamic_agents(group_chat_id: int | None = None) -> list[DynamicAgent]:
    """List all dynamic agents, optionally filtered by chat."""
    if group_chat_id is None:
        return list(_dynamic_agents.values())
    return [a for a in _dynamic_agents.values() if a.group_chat_id == group_chat_id]


def clear_dynamic_agents(group_chat_id: int) -> None:
    """Clear dynamic agents for a specific chat."""
    to_remove = [name for name, agent in _dynamic_agents.items() if agent.group_chat_id == group_chat_id]
    for name in to_remove:
        del _dynamic_agents[name]
    logger.info("Cleared %d dynamic agents for chat %d", len(to_remove), group_chat_id)


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT FACTORY - Creates dynamic agents from names or specs
# ═══════════════════════════════════════════════════════════════════════════════

class DynamicAgentFactory:
    """Factory for creating dynamic agents from name patterns or explicit specs."""

    # Role detection from name suffixes
    ROLE_SUFFIXES = {
        "professor": "professor",
        "prof": "professor",
        "researcher": "researcher",
        "scientist": "researcher",
        "engineer": "engineer",
        "architect": "architect",
        "developer": "engineer",
        "advisor": "advisor",
        "consultant": "consultant",
        "expert": "expert",
        "executive": "executive",
        "director": "executive",
        "manager": "leader",
        "leader": "leader",
        "analyst": "analyst",
        "specialist": "specialist",
        "critic": "critic",
        "student": "researcher",
        "officer": "specialist",
        "technician": "specialist",
    }

    @classmethod
    def create_from_mention(
        cls,
        name: str,
        topic: str,
        spawned_by: str = "",
        spawn_reason: str = "",
        group_chat_id: int = 0,
    ) -> DynamicAgent:
        """Create a dynamic agent from a @mention name.

        Parses names like:
        - "NASAAdvisor" -> NASA domain, advisor role
        - "MITProfessor" -> MIT/academic domain, professor role
        - "SystemsEngineer" -> systems domain, engineer role
        - "RadiationSpecialist" -> radiation domain, specialist role
        """
        clean_name = re.sub(r"[^a-zA-Z0-9]", "", name)
        name_lower = clean_name.lower()

        # 1. Detect role from suffix
        role_key = "specialist"  # default
        for suffix, role in cls.ROLE_SUFFIXES.items():
            if name_lower.endswith(suffix):
                role_key = role
                break

        role_template = ROLE_TEMPLATES.get(role_key, ROLE_TEMPLATES["specialist"])

        # 2. Detect organization/domain from prefix
        org_domain = None
        authority = ""
        for org, info in ORG_DOMAINS.items():
            if name_lower.startswith(org):
                org_domain = info["domain"]
                authority = info["authority"]
                break

        # 3. Extract domain from middle of name if no org prefix
        if not org_domain:
            # Remove the role suffix to get potential domain
            for suffix in cls.ROLE_SUFFIXES.keys():
                if name_lower.endswith(suffix):
                    potential_domain = name_lower[:-len(suffix)]
                    if potential_domain:
                        org_domain = potential_domain
                    break

        # Infer domain from topic if still not found
        if not org_domain:
            org_domain = cls._infer_domain_from_topic(topic)

        # 4. Build display name (add spaces)
        display_name = cls._format_display_name(clean_name)

        # 5. Build role title
        domain_title = org_domain.split("/")[-1].title() if org_domain else "Domain"
        role_title = role_template["role_format"].format(domain=domain_title)

        # 6. Generate expertise
        expertise = cls._generate_expertise(org_domain, topic, role_key)

        # 7. Generate responsibilities
        responsibilities = cls._generate_responsibilities(role_key, org_domain, topic, authority)

        # 8. Generate expectations
        expectations = cls._generate_expectations(role_key, org_domain)

        return DynamicAgent(
            name=name_lower,
            display_name=display_name,
            role=role_title,
            domain=org_domain or "general",
            expertise=expertise,
            style=role_template["style"],
            responsibilities=responsibilities,
            expectations=expectations,
            tools=role_template["tools"].copy(),
            can_spawn=role_template["can_spawn"].copy(),
            temperature=role_template["temperature"],
            spawned_by=spawned_by,
            spawn_reason=spawn_reason,
            group_chat_id=group_chat_id,
        )

    @classmethod
    def create_from_spec(
        cls,
        name: str,
        role: str,
        expertise: list[str],
        responsibilities: str,
        expectations: str,
        tools: list[str] | None = None,
        can_spawn: list[str] | None = None,
        spawned_by: str = "",
        group_chat_id: int = 0,
    ) -> DynamicAgent:
        """Create a dynamic agent from explicit specification.

        Used when the spawning agent provides detailed specs.
        """
        return DynamicAgent(
            name=name.lower().replace(" ", ""),
            display_name=cls._format_display_name(name),
            role=role,
            domain="custom",
            expertise=expertise,
            style="Professional, focused, and action-oriented.",
            responsibilities=responsibilities,
            expectations=expectations,
            tools=tools or ["web_search", "tag_agent_in_chat"],
            can_spawn=can_spawn or [],
            spawned_by=spawned_by,
            group_chat_id=group_chat_id,
        )

    @classmethod
    def _format_display_name(cls, name: str) -> str:
        """Format a clean display name with spaces."""
        # Add space before capitals: "SystemsAdvisor" -> "Systems Advisor"
        spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
        # Handle ALLCAPS to Titlecase: "NASAEngineer" -> "NASA Engineer"
        spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
        return spaced

    @classmethod
    def _infer_domain_from_topic(cls, topic: str) -> str:
        """Infer domain from topic keywords."""
        topic_lower = topic.lower()

        domain_keywords = {
            "aerospace": ["satellite", "space", "orbit", "rocket", "nasa", "launch", "spacecraft"],
            "software": ["software", "code", "api", "app", "database", "cloud", "devops"],
            "hardware": ["hardware", "board", "component", "circuit", "pcb", "chip", "sensor"],
            "business": ["business", "market", "revenue", "profit", "customer", "sales"],
            "medical": ["medical", "health", "patient", "clinical", "fda", "drug", "device"],
        }

        for domain, keywords in domain_keywords.items():
            if any(kw in topic_lower for kw in keywords):
                return domain

        return "general"

    @classmethod
    def _generate_expertise(cls, domain: str, topic: str, role: str) -> list[str]:
        """Generate expertise list based on domain and topic."""
        expertise = []

        # Add domain knowledge
        if domain:
            domain_key = domain.split("/")[0]
            if domain_key in DOMAIN_CONTEXT:
                expertise.extend(DOMAIN_CONTEXT[domain_key].get("considerations", [])[:3])

        # Extract topic keywords
        topic_words = re.findall(r"\b\w{5,}\b", topic.lower())
        expertise.extend(topic_words[:3])

        # Add role-specific skills
        role_skills = {
            "professor": ["research methodology", "academic literature", "theoretical frameworks"],
            "engineer": ["implementation", "specifications", "testing", "constraints"],
            "advisor": ["strategy", "recommendations", "risk assessment"],
            "analyst": ["data analysis", "comparisons", "quantification"],
            "specialist": ["deep domain knowledge", "edge cases", "technical details"],
        }
        expertise.extend(role_skills.get(role, [])[:2])

        return list(set(expertise))[:8]

    @classmethod
    def _generate_responsibilities(cls, role: str, domain: str, topic: str, authority: str) -> str:
        """Generate responsibilities based on role and context."""
        base_responsibilities = {
            "professor": f"Provide academic perspective on {topic}. Explain complex concepts clearly. "
                        f"Cite relevant research. Challenge assumptions with evidence.",
            "researcher": f"Deep-dive into specific aspects of {topic}. Find primary sources and data. "
                         f"Verify claims. Identify knowledge gaps.",
            "engineer": f"Focus on practical implementation for {topic}. Provide specific technical specs. "
                       f"Consider real-world constraints (cost, time, resources).",
            "architect": f"Design system-level solutions for {topic}. Consider integration and scalability. "
                        f"Identify dependencies and potential issues.",
            "advisor": f"Provide strategic guidance on {topic}. Make clear recommendations. "
                      f"Identify risks and opportunities. Help drive decisions.",
            "consultant": f"Give actionable advice on {topic}. Focus on ROI and implementation. "
                         f"Consider client constraints.",
            "executive": f"Make decisions and set priorities for {topic}. Focus on business impact. "
                        f"Cut through complexity to what matters.",
            "leader": f"Guide the team on {topic}. Set direction. Ensure alignment.",
            "analyst": f"Analyze options for {topic}. Quantify trade-offs. Create clear comparisons.",
            "specialist": f"Provide deep expertise on {topic}. Share non-obvious insights. "
                         f"Flag edge cases and potential issues.",
            "expert": f"Provide authoritative knowledge on {topic}. Correct misconceptions. "
                     f"Explain nuances others might miss.",
            "critic": f"Challenge proposals about {topic}. Find weaknesses. Stress-test assumptions.",
        }

        responsibilities = base_responsibilities.get(role, f"Contribute expertise to discussion about {topic}.")

        if authority:
            responsibilities += f" Apply {authority}."

        return responsibilities

    @classmethod
    def _generate_expectations(cls, role: str, domain: str) -> str:
        """Generate expectations based on role."""
        base_expectations = {
            "professor": "Provide evidence-based contributions. Explain reasoning. Be willing to teach.",
            "researcher": "Back up claims with sources. Be thorough. Acknowledge uncertainty.",
            "engineer": "Be specific and practical. Provide concrete specs. Consider implementation.",
            "architect": "Think systemically. Balance ideal with practical. Consider long-term.",
            "advisor": "Give clear recommendations. Explain trade-offs. Drive toward decisions.",
            "consultant": "Be client-focused. Provide actionable steps. Consider constraints.",
            "executive": "Be decisive. Focus on outcomes. Ask questions that matter.",
            "leader": "Set direction. Enable others. Drive alignment.",
            "analyst": "Be data-driven. Quantify when possible. Present objectively.",
            "specialist": "Be precise. Share non-obvious insights. Flag what others miss.",
            "expert": "Be authoritative. Correct errors. Explain nuances.",
            "critic": "Be constructive. Offer alternatives. Explain why not just what.",
        }

        expectations = base_expectations.get(role, "Contribute meaningfully to the discussion.")

        # Add domain-specific expectations
        domain_key = domain.split("/")[0] if domain else ""
        domain_expectations = {
            "aerospace": " Consider flight heritage, radiation, and space qualification.",
            "medical": " Consider patient safety, regulatory requirements, and evidence.",
            "software": " Consider scalability, security, and maintainability.",
            "hardware": " Consider reliability, manufacturability, and supply chain.",
        }

        return expectations + domain_expectations.get(domain_key, "")
