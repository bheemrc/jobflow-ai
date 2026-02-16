"""Intent classification for research queries.

Detects whether a query is BUILD (how to make something) vs ANALYZE (market research)
and adjusts research strategy accordingly.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("app.research.intent")


class QueryIntent(Enum):
    """Types of research intent."""
    BUILD = "build"           # How to make/create/assemble something
    ANALYZE = "analyze"       # Market research, comparisons, trends
    TROUBLESHOOT = "debug"    # Fix a problem, debug an issue
    LEARN = "learn"           # Understand a concept, tutorial
    COMPARE = "compare"       # A vs B comparisons


@dataclass
class IntentClassification:
    """Result of intent classification."""
    primary_intent: QueryIntent
    confidence: float
    keywords_detected: list[str]
    domain: str  # electronics, software, mechanical, etc.
    complexity: str  # beginner, intermediate, advanced


# Pattern indicators for BUILD intent
BUILD_INDICATORS = {
    "strong": [
        r"\bhow\s+(?:to\s+)?(?:do\s+I\s+)?(?:build|make|create|construct|assemble|wire|solder|design)\b",
        r"\bDIY\b",
        r"\bfrom\s+scratch\b",
        r"\bschematic\b",
        r"\bbill\s+of\s+materials\b",
        r"\bBOM\b",
        r"\bparts?\s+list\b",
        r"\bcircuit\s+(?:diagram|design|board)\b",
        r"\bPCB\s+(?:design|layout)\b",
        r"\bwiring\s+(?:diagram|guide)\b",
        r"\bfirmware\b",
        r"\bstep[- ]by[- ]step\b",
        r"\b(?:arduino|esp32|raspberry\s*pi|stm32)\b",
        r"\bsoldering\b",
        r"\b3d\s+print\b",
        r"\bCAD\b",
        r"\bgerber\b",
    ],
    "moderate": [
        r"\bproject\b",
        r"\btutorial\b",
        r"\bcomponents?\b",
        r"\bcode\s+(?:for|to)\b",
        r"\bimplementation\b",
        r"\bprototype\b",
        r"\bsensor\b",
        r"\bmotor\b",
        r"\bdriver\b",
        r"\bcontroller\b",
        r"\bmodule\b",
    ],
}

# Pattern indicators for ANALYZE intent
ANALYZE_INDICATORS = {
    "strong": [
        r"\bmarket\s+(?:analysis|research|trends?|size|report)\b",
        r"\bcompare\s+(?:options?|products?|solutions?|tools?)\b",
        r"\bROI\b",
        r"\bcost[- ]benefit\b",
        r"\bindustry\s+(?:report|analysis|trends?)\b",
        r"\bforecast\b",
        r"\bmarket\s+share\b",
        r"\bgrowth\s+(?:rate|projection)\b",
    ],
    "moderate": [
        r"\bbest\s+(?:option|choice|tool|platform|framework)\b",
        r"\bpros?\s+and\s+cons?\b",
        r"\bwhich\s+(?:is|should|one)\b",
        r"\balternatives?\s+to\b",
        r"\bvs\.?\b",
        r"\bversus\b",
    ],
}

# Domain detection patterns
# More specific domains should have higher-weighted patterns
DOMAIN_PATTERNS = {
    "electronics": [
        r"\bcircuit\b", r"\bPCB\b", r"\bschematic\b", r"\bsolder\b",
        r"\bresistor\b", r"\bcapacitor\b", r"\bdiode\b", r"\btransistor\b",
        r"\bmosfet\b", r"\bop[- ]?amp\b", r"\bvoltage\b", r"\bcurrent\b",
        r"\bpower\s+supply\b", r"\bLED\b",
        # Motor/BLDC moved to lower priority - common across domains
    ],
    "embedded": [
        r"\barduino\b", r"\besp32\b", r"\besp8266\b", r"\bstm32\b",
        r"\braspberry\s*pi\b", r"\bmicrocontroller\b", r"\bMCU\b",
        r"\bfirmware\b", r"\bI2C\b", r"\bSPI\b", r"\bUART\b", r"\bGPIO\b",
        r"\bPWM\b", r"\bADC\b", r"\bDAC\b",
    ],
    "mechanical": [
        r"\b3d\s*print\b", r"\bCAD\b", r"\bCNC\b", r"\bmachining\b",
        r"\bbearing\b", r"\bgear\b", r"\bshaft\b", r"\benclosure\b",
        r"\bmount\b", r"\bbracket\b", r"\bframe\b", r"\bstructure\b",
    ],
    "software": [
        r"\bpython\b", r"\bjavascript\b", r"\btypescript\b", r"\brust\b",
        r"\bAPI\b", r"\bweb\s*app\b", r"\bdatabase\b", r"\bbackend\b",
        r"\bfrontend\b", r"\bframework\b", r"\blibrary\b",
    ],
    "robotics": [
        r"\brobot\b", r"\bdrone\b", r"\bquadcopter\b", r"\bservo\b",
        r"\bactuator\b", r"\bkinematics\b", r"\bnavigation\b", r"\blidar\b",
        r"\bodometry\b", r"\bROS\b",
    ],
    "aerospace": [
        r"\bsatellites?\b", r"\bcubesats?\b", r"\breaction\s*wheels?\b",
        r"\battitude\s*control\b", r"\bgyroscopes?\b", r"\bIMU\b",
        r"\bpropulsion\b", r"\borbital?\b", r"\bspace\b", r"\bADCS\b",
    ],
}

# High-priority domain indicators - if these match, strongly prefer that domain
DOMAIN_PRIORITY_PATTERNS = {
    "aerospace": [r"\bsatellites?\b", r"\bcubesats?\b", r"\breaction\s*wheels?\b", r"\bspace\b", r"\borbital?\b"],
    "robotics": [r"\brobots?\b", r"\bdrones?\b", r"\bROS\b", r"\bquadcopter\b"],
    "embedded": [r"\barduino\b", r"\besp32\b", r"\bstm32\b", r"\bmicrocontrollers?\b"],
}

# Complexity indicators
COMPLEXITY_INDICATORS = {
    "beginner": [
        r"\bbeginner\b", r"\bsimple\b", r"\beasy\b", r"\bbasic\b",
        r"\bintro(?:duction)?\b", r"\bfirst\s+(?:time|project)\b",
    ],
    "advanced": [
        r"\badvanced\b", r"\bcomplex\b", r"\bprofessional\b",
        r"\bhigh[- ]performance\b", r"\boptimiz\w+\b", r"\bprecision\b",
    ],
}


def _count_pattern_matches(text: str, patterns: list[str]) -> tuple[int, list[str]]:
    """Count pattern matches and return matched keywords."""
    text_lower = text.lower()
    count = 0
    keywords = []
    for pattern in patterns:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        if matches:
            count += len(matches)
            keywords.extend(matches)
    return count, keywords


def _detect_domain(text: str) -> str:
    """Detect the technical domain of the query."""
    text_lower = text.lower()

    # First check priority patterns - these override general scoring
    for domain, patterns in DOMAIN_PRIORITY_PATTERNS.items():
        score, _ = _count_pattern_matches(text_lower, patterns)
        if score > 0:
            logger.debug("Priority domain match: %s (score=%d)", domain, score)
            return domain

    # Fall back to general scoring
    domain_scores = {}
    for domain, patterns in DOMAIN_PATTERNS.items():
        score, _ = _count_pattern_matches(text_lower, patterns)
        if score > 0:
            domain_scores[domain] = score

    if not domain_scores:
        return "general"

    # Return highest scoring domain
    return max(domain_scores, key=domain_scores.get)


def _detect_complexity(text: str) -> str:
    """Detect complexity level of the query."""
    text_lower = text.lower()

    for level, patterns in COMPLEXITY_INDICATORS.items():
        score, _ = _count_pattern_matches(text_lower, patterns)
        if score > 0:
            return level

    return "intermediate"  # Default


def _extract_keywords(text: str, domain: str) -> list[str]:
    """Extract key technical terms from the query."""
    keywords = []

    # Extract domain-specific terms (these are technical terms, keep them)
    if domain in DOMAIN_PATTERNS:
        _, domain_keywords = _count_pattern_matches(text.lower(), DOMAIN_PATTERNS[domain])
        keywords.extend(domain_keywords[:5])

    # Extract component names (often capitalized or have numbers)
    # e.g., ESP32, STM32, BLDC, IMU, PCB, etc.
    component_pattern = r'\b[A-Z][A-Z0-9]{2,}[A-Z0-9]*\b'
    components = re.findall(component_pattern, text)
    keywords.extend(components[:5])

    # Extract quoted terms
    quoted = re.findall(r'"([^"]+)"', text)
    keywords.extend(quoted[:2])

    # Filter out non-useful terms
    useless_terms = {
        "how", "to", "build", "make", "create", "design", "using", "with",
        "for", "and", "the", "diy", "bom", "pcb",  # Too generic or common
    }

    filtered = []
    for kw in keywords:
        kw_clean = kw.strip().lower()
        if kw_clean not in useless_terms and len(kw_clean) > 2:
            # Keep original case for acronyms
            filtered.append(kw if kw.isupper() else kw_clean)

    return list(set(filtered))[:8]


def classify_intent(text: str) -> IntentClassification:
    """Classify the intent of a research query.

    Uses regex patterns for fast classification with high confidence.
    """
    text_lower = text.lower()

    # Score BUILD indicators
    build_strong, build_keywords = _count_pattern_matches(text_lower, BUILD_INDICATORS["strong"])
    build_moderate, build_mod_kw = _count_pattern_matches(text_lower, BUILD_INDICATORS["moderate"])
    build_score = build_strong * 2 + build_moderate

    # Score ANALYZE indicators
    analyze_strong, analyze_keywords = _count_pattern_matches(text_lower, ANALYZE_INDICATORS["strong"])
    analyze_moderate, analyze_mod_kw = _count_pattern_matches(text_lower, ANALYZE_INDICATORS["moderate"])
    analyze_score = analyze_strong * 2 + analyze_moderate

    # Determine intent (don't use matched phrases as keywords - they're intent indicators, not search terms)
    if build_score > analyze_score and build_score >= 2:
        intent = QueryIntent.BUILD
        confidence = min(0.95, 0.6 + build_score * 0.1)
    elif analyze_score > build_score and analyze_score >= 2:
        intent = QueryIntent.ANALYZE
        confidence = min(0.95, 0.6 + analyze_score * 0.1)
    elif build_score > 0:
        # Default to BUILD for ambiguous technical queries
        intent = QueryIntent.BUILD
        confidence = 0.5 + build_score * 0.1
    else:
        # Default to LEARN for very ambiguous queries
        intent = QueryIntent.LEARN
        confidence = 0.4

    # Detect domain and complexity
    domain = _detect_domain(text)
    complexity = _detect_complexity(text)

    # Extract technical keywords (not intent indicators)
    all_keywords = _extract_keywords(text, domain)

    logger.info(
        "Intent classified: %s (%.2f confidence), domain=%s, complexity=%s, keywords=%s",
        intent.value, confidence, domain, complexity, all_keywords[:5]
    )

    return IntentClassification(
        primary_intent=intent,
        confidence=confidence,
        keywords_detected=all_keywords,
        domain=domain,
        complexity=complexity,
    )


