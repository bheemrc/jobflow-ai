"""Agent archetypes for different research intents.

BUILD intent uses engineering-focused agents (Component Sourcer, Schematic Hunter, etc.)
ANALYZE intent uses market-focused agents (Market Analyst, Contrarian, etc.)
"""

from __future__ import annotations

from .intent import QueryIntent, IntentClassification


# Engineering-focused archetypes for BUILD queries
BUILD_AGENT_ARCHETYPES = """
ENGINEERING AGENT ARCHETYPES (for building/making projects):

You MUST spawn agents from these archetypes when the user wants to BUILD something:

1. **Component Sourcer** 🔌
   - Expertise: Finding specific parts, datasheets, suppliers, alternatives
   - Focus: Part numbers, specifications, where to buy, price ranges
   - Search strategy: Target DigiKey, Mouser, manufacturer datasheets
   - Output: Specific component recommendations with part numbers and sources

2. **Schematic Hunter** 📐
   - Expertise: Finding circuit diagrams, wiring guides, PCB layouts, CAD files
   - Focus: Reference designs, application circuits, pinout diagrams
   - Search strategy: Target EasyEDA, GitHub hardware repos, manufacturer app notes
   - Output: Links to schematics, wiring diagrams, design files

3. **Code Curator** 💻
   - Expertise: Finding working code, firmware, libraries, algorithms
   - Focus: GitHub repos, library recommendations, code examples
   - Search strategy: Target GitHub (filter by stars), PlatformIO, official SDKs
   - Output: Repository links, code snippets, library recommendations

4. **Build Guide Finder** 🛠️
   - Expertise: Step-by-step tutorials, maker projects, video guides, build logs
   - Focus: Complete project walkthroughs, assembly instructions
   - Search strategy: Target Hackaday.io, Instructables, Adafruit Learn, SparkFun tutorials
   - Output: Tutorial links with difficulty ratings, time estimates

5. **Troubleshooter** 🔧
   - Expertise: Common pitfalls, debugging guides, forum solutions
   - Focus: What goes wrong, how to fix it, calibration tips
   - Search strategy: Target Stack Exchange, Reddit, EEVblog forums
   - Output: Common failure modes, debugging flowcharts, solutions

CRITICAL RULES FOR BUILD QUERIES:
- Search for TECHNICAL ARTIFACTS (schematics, code, BOMs) not market reports
- Include specific part numbers and component names in searches
- Prioritize GitHub, Hackaday, Instructables, manufacturer sites
- Avoid generic marketing content and SEO spam
- Each agent must find ACTIONABLE information (things the user can use to build)
"""

# Analysis-focused archetypes for ANALYZE queries
ANALYZE_AGENT_ARCHETYPES = """
ANALYSIS AGENT ARCHETYPES (for market research and comparisons):

1. **Market Analyst** 📊
   - Expertise: Market size, growth trends, industry reports
   - Focus: Statistics, forecasts, adoption metrics
   - Output: Data-backed market insights with sources

2. **Field Operative** 🎯
   - Expertise: Real-world case studies, production deployments
   - Focus: Who's using it, how it performs in practice
   - Output: Case studies with concrete results

3. **Contrarian** ⚔️
   - Expertise: Counter-arguments, limitations, failure cases
   - Focus: What could go wrong, hidden costs, alternatives
   - Output: Balanced critique with evidence

4. **Economist** 💰
   - Expertise: Cost analysis, ROI, total cost of ownership
   - Focus: Pricing, value comparison, hidden costs
   - Output: Cost-benefit analysis with numbers

5. **Scout** 🔭
   - Expertise: Emerging trends, new developments, research papers
   - Focus: What's coming next, cutting-edge developments
   - Output: Forward-looking insights with sources
"""

# Archetype configurations with search hints
BUILD_ARCHETYPE_CONFIG = {
    "Component Sourcer": {
        "avatar": "🔌",
        "expertise_template": "Finding specific components and parts for {domain} projects",
        "tone": "practical",
        "preferred_sources": ["datasheets", "digikey", "mouser", "octopart"],
    },
    "Schematic Hunter": {
        "avatar": "📐",
        "expertise_template": "Finding circuit schematics and design references for {domain}",
        "tone": "technical",
        "preferred_sources": ["github", "easyeda", "manufacturer_appnotes"],
    },
    "Code Curator": {
        "avatar": "💻",
        "expertise_template": "Finding working code and libraries for {domain} applications",
        "tone": "methodical",
        "preferred_sources": ["github", "platformio", "official_sdks"],
    },
    "Build Guide Finder": {
        "avatar": "🛠️",
        "expertise_template": "Finding step-by-step build tutorials for {domain} projects",
        "tone": "encouraging",
        "preferred_sources": ["hackaday", "instructables", "adafruit", "sparkfun"],
    },
    "Troubleshooter": {
        "avatar": "🔧",
        "expertise_template": "Finding solutions to common problems in {domain} projects",
        "tone": "pragmatic",
        "preferred_sources": ["stackexchange", "reddit", "eevblog", "forums"],
    },
}

ANALYZE_ARCHETYPE_CONFIG = {
    "Market Analyst": {
        "avatar": "📊",
        "expertise_template": "Market analysis and industry trends for {domain}",
        "tone": "analytical",
    },
    "Field Operative": {
        "avatar": "🎯",
        "expertise_template": "Real-world deployments and case studies in {domain}",
        "tone": "pragmatic",
    },
    "Contrarian": {
        "avatar": "⚔️",
        "expertise_template": "Critical analysis and limitations of {domain} solutions",
        "tone": "skeptical",
    },
    "Economist": {
        "avatar": "💰",
        "expertise_template": "Cost analysis and ROI for {domain} investments",
        "tone": "analytical",
    },
    "Scout": {
        "avatar": "🔭",
        "expertise_template": "Emerging trends and innovations in {domain}",
        "tone": "enthusiastic",
    },
}


def get_archetypes_prompt(intent: QueryIntent) -> str:
    """Get the appropriate archetypes prompt for the given intent."""
    if intent == QueryIntent.BUILD:
        return BUILD_AGENT_ARCHETYPES
    else:
        return ANALYZE_AGENT_ARCHETYPES


def get_archetype_config(intent: QueryIntent) -> dict:
    """Get archetype configuration for the given intent."""
    if intent == QueryIntent.BUILD:
        return BUILD_ARCHETYPE_CONFIG
    else:
        return ANALYZE_ARCHETYPE_CONFIG


def get_recommended_agent_count(intent: QueryIntent, complexity: str) -> int:
    """Get recommended number of agents based on intent and complexity."""
    if intent == QueryIntent.BUILD:
        # BUILD queries benefit from more specialized agents
        if complexity == "advanced":
            return 5
        elif complexity == "intermediate":
            return 4
        else:
            return 3
    else:
        # ANALYZE queries work well with 3-4 agents
        return 4


def select_agents_for_intent(
    classification: IntentClassification,
) -> list[str]:
    """Select specific agent types based on intent and domain.

    Returns list of agent type names to spawn.
    """
    intent = classification.primary_intent
    domain = classification.domain
    complexity = classification.complexity

    if intent == QueryIntent.BUILD:
        # Core agents for all BUILD queries
        agents = ["Component Sourcer", "Build Guide Finder"]

        # Add domain-specific agents
        if domain in ["electronics", "embedded", "aerospace", "robotics"]:
            agents.append("Schematic Hunter")

        if domain in ["software", "embedded", "robotics"]:
            agents.append("Code Curator")

        # Always include troubleshooter for intermediate/advanced
        if complexity in ["intermediate", "advanced"]:
            agents.append("Troubleshooter")

        return agents[:5]  # Max 5 agents

    elif intent == QueryIntent.ANALYZE:
        return ["Market Analyst", "Field Operative", "Contrarian", "Economist"]

    elif intent == QueryIntent.COMPARE:
        return ["Market Analyst", "Field Operative", "Contrarian"]

    elif intent == QueryIntent.TROUBLESHOOT:
        return ["Troubleshooter", "Code Curator", "Build Guide Finder"]

    else:  # LEARN
        return ["Build Guide Finder", "Code Curator", "Schematic Hunter"]
