"""Engineering-focused query templates for technical research.

Generates domain-specific search queries that find practical content
(schematics, code, BOMs, tutorials) instead of SEO market reports.
"""

from __future__ import annotations

import logging
from datetime import datetime

from .intent import QueryIntent, IntentClassification

logger = logging.getLogger("app.research.queries")


# Site operators to prioritize quality technical sources
QUALITY_SITES = {
    "code": [
        "site:github.com",
        "site:gitlab.com",
    ],
    "tutorials": [
        "site:hackaday.io",
        "site:hackaday.com",
        "site:instructables.com",
        "site:adafruit.com/learn",
        "site:sparkfun.com/tutorials",
    ],
    "electronics": [
        "site:electronics.stackexchange.com",
        "site:eevblog.com",
        "site:allaboutcircuits.com",
    ],
    "datasheets": [
        "site:ti.com",
        "site:analog.com",
        "site:st.com",
        "site:microchip.com",
        "site:nxp.com",
    ],
    "forums": [
        "site:reddit.com/r/AskElectronics",
        "site:reddit.com/r/arduino",
        "site:reddit.com/r/esp32",
        "site:reddit.com/r/embedded",
    ],
}

# Sites to exclude (SEO spam, marketing)
EXCLUDE_SITES = [
    "-site:pinterest.com",
    "-site:alibaba.com",
    "-site:aliexpress.com",
    "-site:made-in-china.com",
    "-inurl:market-report",
    "-inurl:industry-analysis",
    "-inurl:market-forecast",
]


# Query templates by agent type and domain
# Use {core} for the core subject (extracted from topic), {keywords} for technical terms
ENGINEERING_QUERY_TEMPLATES = {
    "electronics": {
        "Component Sourcer": [
            "{core} datasheet PDF specifications",
            "{keywords} site:digikey.com OR site:mouser.com",
            "{core} BOM bill of materials parts list",
            "{keywords} alternative equivalent part",
        ],
        "Schematic Hunter": [
            "{core} schematic circuit diagram",
            "{keywords} wiring diagram pinout connection",
            "{core} reference design application note",
            "site:github.com {core} schematic KiCAD Eagle",
        ],
        "Code Curator": [
            "site:github.com {core} stars:>50",
            "{keywords} arduino ESP32 library",
            "{core} firmware source code",
            "site:github.com {keywords} driver example",
        ],
        "Build Guide Finder": [
            "site:hackaday.io {core}",
            "site:hackaday.com {core} project",
            "{core} DIY tutorial complete guide",
            "site:instructables.com {core}",
        ],
        "Troubleshooter": [
            "site:electronics.stackexchange.com {core}",
            "{keywords} problem solution fix",
            "{core} common issues troubleshooting",
            "site:reddit.com/r/AskElectronics {keywords}",
        ],
    },
    "embedded": {
        "Component Sourcer": [
            "{keywords} specifications comparison",
            "{core} development board kit",
            "{keywords} module breakout datasheet",
            "{core} components parts where to buy",
        ],
        "Schematic Hunter": [
            "{core} schematic STM32 ESP32",
            "site:github.com {core} hardware KiCAD",
            "{keywords} reference design circuit",
            "{core} PCB layout design files",
        ],
        "Code Curator": [
            "site:github.com {core} stars:>100",
            "{keywords} HAL driver library",
            "SimpleFOC {keywords}",
            "site:github.com {keywords} firmware example",
        ],
        "Build Guide Finder": [
            "site:hackaday.io {core}",
            "site:hackaday.com {core}",
            "{core} complete tutorial build",
            "site:adafruit.com {keywords} guide",
        ],
        "Troubleshooter": [
            "site:stackoverflow.com {keywords}",
            "site:electronics.stackexchange.com {core}",
            "{keywords} not working debug fix",
            "{core} common mistakes problems",
        ],
    },
    "mechanical": {
        "Component Sourcer": [
            "{topic} {keywords} parts hardware",
            "{keywords} bearing gear shaft specifications",
            "{topic} materials aluminum steel",
            "3D printing filament {topic}",
        ],
        "Schematic Hunter": [
            "{topic} CAD model STL STEP",
            "site:github.com {topic} {keywords} CAD",
            "{topic} mechanical drawing dimensions",
            "{keywords} assembly diagram exploded view",
        ],
        "Code Curator": [
            "site:github.com {topic} {keywords} CAD",
            "{topic} OpenSCAD FreeCAD model",
            "CNC gcode {topic} {keywords}",
            "{topic} automation control code",
        ],
        "Build Guide Finder": [
            "site:instructables.com {topic} {keywords}",
            "{topic} DIY build assembly guide",
            "{topic} workshop tutorial",
            "how to machine {keywords} {topic}",
        ],
        "Troubleshooter": [
            "{topic} {keywords} vibration noise problem",
            "{keywords} alignment calibration issues",
            "{topic} failure mode analysis",
            "fixing {keywords} {topic} common problems",
        ],
    },
    "aerospace": {
        "Component Sourcer": [
            "{core} BLDC motor specifications datasheet",
            "reaction wheel motor cubesat specifications",
            "{keywords} site:digikey.com OR site:mouser.com",
            "flywheel inertia wheel BLDC motor small satellite",
        ],
        "Schematic Hunter": [
            "site:github.com reaction wheel schematic",
            "site:github.com {core} hardware",
            "BLDC motor driver schematic FOC",
            "{core} circuit design reference",
        ],
        "Code Curator": [
            "site:github.com reaction wheel control",
            "site:github.com SimpleFOC attitude control",
            "site:github.com cubesat ADCS",
            "{keywords} firmware PID control",
        ],
        "Build Guide Finder": [
            "site:hackaday.io reaction wheel",
            "site:hackaday.com reaction wheel satellite",
            "DIY reaction wheel cubesat tutorial",
            "{core} build guide project",
        ],
        "Troubleshooter": [
            "reaction wheel vibration balancing problem",
            "BLDC motor jitter noise fix",
            "site:electronics.stackexchange.com {keywords}",
            "{core} common issues calibration",
        ],
    },
    "software": {
        "Component Sourcer": [
            "{topic} {keywords} library package",
            "{keywords} framework comparison features",
            "{topic} SDK API documentation",
            "best {keywords} for {topic}",
        ],
        "Schematic Hunter": [
            "{topic} architecture diagram",
            "{keywords} system design flowchart",
            "{topic} data flow diagram",
            "{keywords} API schema documentation",
        ],
        "Code Curator": [
            "site:github.com {topic} {keywords} stars:>100",
            "{topic} {keywords} example implementation",
            "{keywords} boilerplate template {topic}",
            "{topic} code tutorial {keywords}",
        ],
        "Build Guide Finder": [
            "{topic} {keywords} tutorial from scratch",
            "build {topic} step by step guide",
            "{topic} {keywords} documentation getting started",
            "how to implement {topic} {keywords}",
        ],
        "Troubleshooter": [
            "{topic} {keywords} error stackoverflow",
            "{keywords} bug fix solution",
            "{topic} performance optimization issues",
            "debugging {topic} {keywords} problems",
        ],
    },
    "robotics": {
        "Component Sourcer": [
            "{topic} {keywords} servo motor actuator",
            "robot {keywords} sensors lidar camera",
            "{topic} motor driver controller",
            "{keywords} robot kit components",
        ],
        "Schematic Hunter": [
            "site:github.com {topic} {keywords} schematic robot",
            "{topic} wiring diagram motor driver",
            "{keywords} robot circuit design",
            "ROS {topic} hardware interface schematic",
        ],
        "Code Curator": [
            "site:github.com {topic} {keywords} ROS",
            "{topic} inverse kinematics code",
            "{keywords} robot control algorithm",
            "navigation SLAM {topic} code",
        ],
        "Build Guide Finder": [
            "site:hackaday.io robot {topic} {keywords}",
            "DIY {topic} robot build guide",
            "{topic} {keywords} robot tutorial",
            "homemade {topic} robot project",
        ],
        "Troubleshooter": [
            "{topic} robot {keywords} calibration issues",
            "motor driver {keywords} problems",
            "{topic} sensor noise filtering",
            "robot {keywords} accuracy drift",
        ],
    },
}

# Default templates for unknown domains
DEFAULT_TEMPLATES = {
    "Component Sourcer": [
        "{core} components parts specifications",
        "{keywords} datasheet PDF",
        "{core} BOM materials list",
        "{keywords} where to buy supplier",
    ],
    "Schematic Hunter": [
        "{core} schematic diagram",
        "site:github.com {core} schematic",
        "{keywords} reference design circuit",
        "{core} wiring pinout",
    ],
    "Code Curator": [
        "site:github.com {core} stars:>50",
        "site:github.com {keywords}",
        "{core} code example library",
        "{keywords} firmware driver",
    ],
    "Build Guide Finder": [
        "site:hackaday.io {core}",
        "site:hackaday.com {core}",
        "{core} DIY tutorial guide",
        "site:instructables.com {core}",
    ],
    "Troubleshooter": [
        "{core} problems solutions fix",
        "site:electronics.stackexchange.com {keywords}",
        "{core} common mistakes troubleshooting",
        "site:reddit.com {keywords} help",
    ],
}

# Templates for ANALYZE intent
ANALYZE_TEMPLATES = {
    "Market Analyst": [
        "{topic} market size growth {year}",
        "{topic} industry trends forecast",
        "{keywords} market analysis report",
        "{topic} adoption statistics",
    ],
    "Field Operative": [
        "{topic} {keywords} case study production",
        "{keywords} real world deployment",
        "company using {topic} success story",
        "{topic} enterprise implementation",
    ],
    "Contrarian": [
        "{topic} {keywords} criticism limitations",
        "{keywords} failure cases problems",
        "why {topic} fails",
        "{topic} alternatives better",
    ],
    "Economist": [
        "{topic} {keywords} cost analysis TCO",
        "{keywords} ROI calculation",
        "{topic} pricing comparison",
        "{keywords} cost benefit analysis",
    ],
}


def _extract_core_subject(topic: str) -> str:
    """Extract the core subject from a topic string.

    "How to build reaction wheels for small satellites using BLDC motors"
    -> "reaction wheels BLDC motors"

    "Build an ESP32 based IoT sensor with LoRa connectivity"
    -> "ESP32 IoT sensor LoRa"
    """
    import re

    # Preserve uppercase terms (acronyms, part numbers)
    uppercase_terms = re.findall(r'\b[A-Z][A-Z0-9]+\b', topic)

    # Remove common filler phrases
    core = topic.lower()
    filler_patterns = [
        r"^how\s+(?:do\s+i\s+|to\s+)?(?:build|make|create|design|implement)?\s*",
        r"^build\s+(?:a|an)?\s*",
        r"^create\s+(?:a|an)?\s*",
        r"^make\s+(?:a|an)?\s*",
        r"^design\s+(?:a|an)?\s*",
        r"\s+using\s+",
        r"\s+with\s+",
        r"\s+for\s+",
        r"\s+based\s+(?:on\s+)?",
        r"\s+and\s+",
        r"^what\s+is\s+(?:a|an|the)?\s*",
        r"^best\s+(?:way\s+to|practices?\s+for)\s+",
        r"^compare\s+",
    ]

    for pattern in filler_patterns:
        core = re.sub(pattern, " ", core)

    # Remove common stop words AND action verbs
    stop_words = {"a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
                  "have", "has", "had", "do", "does", "did", "will", "would", "could",
                  "should", "may", "might", "must", "shall", "can", "need", "dare",
                  "ought", "used", "to", "of", "in", "on", "at", "by", "from", "as",
                  "into", "through", "during", "before", "after", "above", "below",
                  "between", "under", "again", "further", "then", "once", "here",
                  "there", "when", "where", "why", "how", "all", "each", "few", "more",
                  "most", "other", "some", "such", "no", "nor", "not", "only", "own",
                  "same", "so", "than", "too", "very", "just", "also", "now",
                  # Action verbs that aren't helpful for searches
                  "build", "make", "create", "design", "implement", "develop", "use",
                  "get", "find", "learn", "understand", "compare", "analyze"}

    words = core.split()
    meaningful_words = [w for w in words if w not in stop_words and len(w) > 2]

    # Re-add uppercase terms that might have been lowercased
    for term in uppercase_terms:
        if term.lower() not in [w.lower() for w in meaningful_words]:
            meaningful_words.append(term)

    # Keep first 4-5 meaningful words
    core_words = meaningful_words[:5]

    result = " ".join(core_words)
    logger.debug("Extracted core subject: '%s' -> '%s'", topic[:50], result)
    return result


def generate_queries_for_agent(
    agent_type: str,
    topic: str,
    classification: IntentClassification,
) -> list[str]:
    """Generate domain-specific search queries for an agent.

    Args:
        agent_type: The agent archetype (e.g., "Component Sourcer")
        topic: The research topic
        classification: Intent classification with domain, keywords, etc.

    Returns:
        List of 3-4 search queries optimized for the agent's role
    """
    year = datetime.now().year

    # Extract clean core subject from topic
    core = _extract_core_subject(topic)

    # Use detected keywords, falling back to core words
    if classification.keywords_detected:
        keywords = " ".join(classification.keywords_detected[:3])
    else:
        keywords = core.split()[0] if core else topic.split()[0]

    # Select template set based on intent
    if classification.primary_intent == QueryIntent.BUILD:
        domain_templates = ENGINEERING_QUERY_TEMPLATES.get(
            classification.domain,
            DEFAULT_TEMPLATES
        )
        agent_templates = domain_templates.get(agent_type, DEFAULT_TEMPLATES.get(agent_type, []))
    else:
        agent_templates = ANALYZE_TEMPLATES.get(agent_type, [])

    if not agent_templates:
        agent_templates = DEFAULT_TEMPLATES.get(agent_type, [f"{core} {keywords}"])

    # Generate queries from templates
    queries = []
    for template in agent_templates[:4]:
        query = template.format(
            topic=topic,  # Keep for ANALYZE templates that use full topic
            core=core,    # Clean core subject for BUILD queries
            keywords=keywords,
            year=year,
        )
        queries.append(query)

    logger.info("Generated %d queries for %s: %s", len(queries), agent_type, queries[:2])

    return queries


def add_site_operators(query: str, agent_type: str, domain: str) -> str:
    """Add site operators to improve query quality.

    For first query of certain agent types, add site: operators.
    """
    # Don't add if query already has site operator
    if "site:" in query:
        return query

    # Add site operators for specific agent types
    if agent_type == "Code Curator":
        return f"site:github.com {query}"
    elif agent_type == "Build Guide Finder":
        return f"(site:hackaday.io OR site:instructables.com) {query}"
    elif agent_type == "Troubleshooter" and domain == "electronics":
        return f"site:electronics.stackexchange.com {query}"

    # Add exclusions to avoid SEO spam
    return f"{query} {EXCLUDE_SITES[0]}"


def get_quality_sites_for_agent(agent_type: str, domain: str) -> list[str]:
    """Get list of quality sites relevant to this agent type."""
    sites = []

    if agent_type == "Code Curator":
        sites.extend(QUALITY_SITES["code"])
    elif agent_type == "Build Guide Finder":
        sites.extend(QUALITY_SITES["tutorials"])
    elif agent_type == "Schematic Hunter":
        if domain in ["electronics", "embedded", "aerospace"]:
            sites.extend(QUALITY_SITES["datasheets"])
        sites.extend(QUALITY_SITES["tutorials"])
    elif agent_type == "Troubleshooter":
        sites.extend(QUALITY_SITES["forums"])
        if domain in ["electronics", "embedded"]:
            sites.extend(QUALITY_SITES["electronics"])
    elif agent_type == "Component Sourcer":
        sites.extend(QUALITY_SITES["datasheets"])

    return sites
