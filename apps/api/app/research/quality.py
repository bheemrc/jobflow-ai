"""Source quality scoring for research results.

Prioritizes authoritative technical sources (GitHub, Hackaday, manufacturer sites)
and deprioritizes SEO spam (market reports, content farms).
"""

from __future__ import annotations

import re
import logging
from urllib.parse import urlparse

from .intent import QueryIntent

logger = logging.getLogger("app.research.quality")


# Source quality tiers
SOURCE_QUALITY_TIERS = {
    "tier1_authoritative": {
        "domains": [
            "github.com",
            "gitlab.com",
            "arxiv.org",
            "ieee.org",
            # Manufacturer sites
            "ti.com",
            "analog.com",
            "st.com",
            "microchip.com",
            "nxp.com",
            "infineon.com",
            "onsemi.com",
            "maxim-ic.com",
            "maximintegrated.com",
        ],
        "score_multiplier": 1.5,
    },
    "tier2_maker_community": {
        "domains": [
            "hackaday.io",
            "hackaday.com",
            "instructables.com",
            "adafruit.com",
            "sparkfun.com",
            "element14.com",
            "eevblog.com",
            "allaboutcircuits.com",
            "circuitdigest.com",
            "electronics-tutorials.ws",
            "electronicshub.org",
            "pcbheaven.com",
            "ladyada.net",
        ],
        "score_multiplier": 1.4,
    },
    "tier3_forums_qa": {
        "domains": [
            "electronics.stackexchange.com",
            "stackoverflow.com",
            "stackexchange.com",
            "reddit.com",
            "discourse.org",
        ],
        "score_multiplier": 1.2,
    },
    "tier4_documentation": {
        "domains": [
            "docs.python.org",
            "docs.rust-lang.org",
            "developer.mozilla.org",
            "learn.microsoft.com",
            "cloud.google.com",
            "aws.amazon.com",
            "platformio.org",
            "arduino.cc",
            "espressif.com",
            "simplefoc.com",
        ],
        "score_multiplier": 1.3,
    },
}

# Domains and patterns to deprioritize
DEPRIORITIZE_CONFIG = {
    "domains": [
        "pinterest.com",
        "alibaba.com",
        "aliexpress.com",
        "made-in-china.com",
        "amazon.com",
        "ebay.com",
        "wish.com",
        "dhgate.com",
        "globalsources.com",
        "indiamart.com",
        # Content farms
        "medium.com",  # Often low quality for technical content
        "quora.com",
        "wikihow.com",
    ],
    "url_patterns": [
        r"market-report",
        r"industry-analysis",
        r"market-forecast",
        r"market-size",
        r"market-research",
        r"industry-report",
        r"/product/",
        r"/buy/",
        r"/shop/",
        r"/cart/",
        r"/checkout/",
        r"affiliate",
        r"sponsored",
    ],
    "title_patterns": [
        r"buy\s+(?:now|online)",
        r"best\s+price",
        r"cheap\s+",
        r"discount",
        r"market\s+(?:size|report|analysis|forecast)",
        r"industry\s+(?:report|analysis)",
        r"\$\d+\.\d+\s*(?:billion|million)",
        r"CAGR",
        r"compound\s+annual",
    ],
    "score_multiplier": 0.3,
}

# Bonus patterns for BUILD intent
BUILD_BONUS_PATTERNS = {
    "url": [
        r"github\.com",
        r"gitlab\.com",
        r"schematic",
        r"circuit",
        r"tutorial",
        r"guide",
        r"diy",
        r"project",
        r"build",
        r"hackaday",
        r"instructables",
    ],
    "title": [
        r"how\s+to\s+(?:build|make|create)",
        r"(?:diy|homemade)",
        r"tutorial",
        r"schematic",
        r"circuit\s+diagram",
        r"step[- ]by[- ]step",
        r"build\s+(?:guide|log|project)",
        r"open\s*source",
        r"arduino|esp32|raspberry\s*pi|stm32",
    ],
    "bonus_multiplier": 1.25,
}


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _check_patterns(text: str, patterns: list[str]) -> bool:
    """Check if any pattern matches the text."""
    text_lower = text.lower()
    for pattern in patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    return False


def calculate_quality_score(
    url: str,
    title: str,
    content: str,
    raw_score: float,
    intent: QueryIntent | None = None,
) -> float:
    """Calculate quality-adjusted relevance score.

    Args:
        url: Result URL
        title: Result title
        content: Result content/snippet
        raw_score: Original score from search engine
        intent: Query intent (BUILD, ANALYZE, etc.)

    Returns:
        Quality-adjusted score
    """
    domain = extract_domain(url)
    url_lower = url.lower()
    title_lower = title.lower()

    score = raw_score if raw_score > 0 else 0.5

    # Check deprioritize patterns first
    if domain in DEPRIORITIZE_CONFIG["domains"]:
        score *= DEPRIORITIZE_CONFIG["score_multiplier"]
        logger.debug("Deprioritized domain %s: %.2f", domain, score)
        return score

    if _check_patterns(url_lower, DEPRIORITIZE_CONFIG["url_patterns"]):
        score *= DEPRIORITIZE_CONFIG["score_multiplier"]
        logger.debug("Deprioritized URL pattern: %.2f", score)
        return score

    if _check_patterns(title_lower, DEPRIORITIZE_CONFIG["title_patterns"]):
        score *= 0.5  # Less aggressive for title matches
        logger.debug("Deprioritized title pattern: %.2f", score)

    # Check quality tiers
    tier_found = False
    for tier_name, tier_config in SOURCE_QUALITY_TIERS.items():
        for tier_domain in tier_config["domains"]:
            if tier_domain in domain:
                score *= tier_config["score_multiplier"]
                tier_found = True
                logger.debug("Boosted %s (%s): %.2f", domain, tier_name, score)
                break
        if tier_found:
            break

    # Apply BUILD intent bonuses
    if intent == QueryIntent.BUILD:
        if _check_patterns(url_lower, BUILD_BONUS_PATTERNS["url"]):
            score *= BUILD_BONUS_PATTERNS["bonus_multiplier"]
        if _check_patterns(title_lower, BUILD_BONUS_PATTERNS["title"]):
            score *= BUILD_BONUS_PATTERNS["bonus_multiplier"]

    return score


def filter_and_rank_results(
    results: list[dict],
    intent: QueryIntent | None = None,
    max_results: int = 10,
) -> list[dict]:
    """Filter and re-rank search results based on quality.

    Args:
        results: List of search result dicts with url, title, content, score
        intent: Query intent for intent-specific boosting
        max_results: Maximum results to return

    Returns:
        Quality-filtered and re-ranked results
    """
    if not results:
        return []

    scored_results = []

    for result in results:
        url = result.get("url", "")
        title = result.get("title", "")
        content = result.get("content", "")
        raw_score = result.get("score", 0.5)

        quality_score = calculate_quality_score(
            url=url,
            title=title,
            content=content,
            raw_score=raw_score,
            intent=intent,
        )

        result_copy = result.copy()
        result_copy["quality_score"] = quality_score
        result_copy["raw_score"] = raw_score
        scored_results.append(result_copy)

    # Sort by quality score descending
    scored_results.sort(key=lambda x: x.get("quality_score", 0), reverse=True)

    # Log quality filtering effect
    if scored_results:
        top_domains = [extract_domain(r["url"]) for r in scored_results[:3]]
        logger.info("Top results after quality filtering: %s", top_domains)

    return scored_results[:max_results]


def get_source_type(url: str) -> str:
    """Categorize a URL by source type.

    Returns one of: github, tutorial, datasheet, forum, documentation, other
    """
    domain = extract_domain(url)
    url_lower = url.lower()

    if "github.com" in domain or "gitlab.com" in domain:
        return "github"

    if any(d in domain for d in ["hackaday", "instructables"]):
        return "tutorial"

    # Path-based tutorial detection (domain alone won't contain paths)
    if ("adafruit.com" in domain and "/learn" in url_lower) or \
       ("sparkfun.com" in domain and "/tutorials" in url_lower):
        return "tutorial"

    if any(d in domain for d in SOURCE_QUALITY_TIERS["tier1_authoritative"]["domains"]):
        if "datasheet" in url_lower or ".pdf" in url_lower:
            return "datasheet"
        return "documentation"

    if any(d in domain for d in SOURCE_QUALITY_TIERS["tier3_forums_qa"]["domains"]):
        return "forum"

    if any(d in domain for d in SOURCE_QUALITY_TIERS["tier4_documentation"]["domains"]):
        return "documentation"

    return "other"


def categorize_results(results: list[dict]) -> dict[str, list[dict]]:
    """Categorize results by source type.

    Returns dict with keys: github, tutorial, datasheet, forum, documentation, other
    """
    categories: dict[str, list[dict]] = {
        "github": [],
        "tutorial": [],
        "datasheet": [],
        "forum": [],
        "documentation": [],
        "other": [],
    }

    for result in results:
        source_type = get_source_type(result.get("url", ""))
        categories[source_type].append(result)

    return categories
