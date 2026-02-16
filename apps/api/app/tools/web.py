"""Web search tool using Tavily."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from app.config import settings

logger = logging.getLogger(__name__)


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for real-time information using Tavily.

    Use this tool to research companies, find salary data, look up recent
    interview experiences, find LeetCode tutorials, or get any current
    information not available in other tools.

    Args:
        query: The search query (e.g. "Amazon SDE interview questions 2024",
               "Google software engineer salary levels.fyi").
        max_results: Maximum number of results to return (1-10). Default: 5.

    Returns:
        JSON with search results including title, url, and content snippet.
    """
    if not settings.tavily_api_key:
        return json.dumps({
            "error": "Web search not configured. Set TAVILY_API_KEY in .env to enable.",
            "results": [],
        })

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(
            query=query,
            max_results=min(max_results, 10),
            search_depth="advanced",
        )

        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:2000],
                "score": r.get("score", 0),
            })

        return json.dumps({
            "query": query,
            "results": results,
        })
    except ImportError:
        return json.dumps({
            "error": "tavily-python not installed. Run: pip install tavily-python",
            "results": [],
        })
    except Exception as e:
        logger.error("web_search error: %s", e)
        return json.dumps({
            "error": f"Web search failed: {e}",
            "results": [],
        })
