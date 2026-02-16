"""User interests and search history tools."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from app.db import get_conn

logger = logging.getLogger(__name__)


@tool
async def get_search_history(limit: int = 30) -> str:
    """Get the user's recent job search history from the dashboard.

    Shows what the user has been searching for — search terms, locations,
    remote preferences, and how many results each search returned.
    Use this to understand what kinds of jobs the user is actively looking for.

    Args:
        limit: Maximum number of recent searches to return (1-100). Default: 30.

    Returns:
        JSON with searches array and summary of search patterns.
    """
    try:
        async with get_conn() as conn:
            rows = await conn.fetch(
                "SELECT * FROM search_history ORDER BY searched_at DESC LIMIT $1",
                min(limit, 100),
            )

        if not rows:
            return json.dumps({"total": 0, "searches": [], "message": "No search history yet."})

        searches = []
        term_counts: dict[str, int] = {}
        locations: dict[str, int] = {}
        remote_count = 0

        for row in rows:
            r = dict(row)
            searched_at = r.get("searched_at", "")
            if hasattr(searched_at, "isoformat"):
                searched_at = searched_at.isoformat()
            searches.append({
                "search_term": r.get("search_term", ""),
                "location": r.get("location", ""),
                "is_remote": bool(r.get("is_remote")),
                "site_name": r.get("site_name", ""),
                "results_count": r.get("results_count", 0),
                "searched_at": searched_at,
            })
            term = r.get("search_term", "").lower().strip()
            if term:
                term_counts[term] = term_counts.get(term, 0) + 1
            loc = r.get("location", "").strip()
            if loc:
                locations[loc] = locations.get(loc, 0) + 1
            if r.get("is_remote"):
                remote_count += 1

        # Build summary of patterns
        top_terms = sorted(term_counts.items(), key=lambda x: -x[1])[:10]
        top_locations = sorted(locations.items(), key=lambda x: -x[1])[:5]

        return json.dumps({
            "total": len(searches),
            "searches": searches,
            "patterns": {
                "most_searched_terms": [{"term": t, "count": c} for t, c in top_terms],
                "most_searched_locations": [{"location": l, "count": c} for l, c in top_locations],
                "remote_search_percentage": round(remote_count / len(searches) * 100) if searches else 0,
            },
        })
    except Exception as e:
        logger.error("get_search_history error: %s", e)
        return json.dumps({"error": str(e), "searches": []})


@tool
async def get_user_job_interests() -> str:
    """Analyze the user's saved jobs and search history to build a profile
    of their job search interests and preferences.

    This is the user's "job search journal" — it reveals what kinds of roles,
    companies, industries, locations, and salary ranges they care about.
    Use this to personalize recommendations, interview prep, and resume tailoring.

    Returns:
        JSON with interest patterns extracted from saved jobs and search history.
    """
    try:
        async with get_conn() as conn:
            saved_rows = await conn.fetch("SELECT * FROM saved_jobs ORDER BY saved_at DESC")
            search_rows = await conn.fetch("SELECT * FROM search_history ORDER BY searched_at DESC LIMIT 100")

        if not saved_rows and not search_rows:
            return json.dumps({"error": "No data yet. User needs to search and save jobs first."})

        companies: dict[str, int] = {}
        titles: dict[str, int] = {}
        locations: dict[str, int] = {}
        salary_min_vals: list[float] = []
        salary_max_vals: list[float] = []
        remote_count = 0
        status_counts: dict[str, int] = {}
        tech_mentions: dict[str, int] = {}
        descriptions_text = ""

        tech_keywords = [
            "python", "javascript", "typescript", "java", "c++", "c#", "go",
            "rust", "ruby", "php", "swift", "kotlin", "scala",
            "react", "angular", "vue", "next.js", "node.js", "express",
            "django", "flask", "fastapi", "spring", "rails",
            "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
            "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
            "graphql", "kafka", "spark", "airflow", "snowflake",
            "machine learning", "deep learning", "tensorflow", "pytorch",
            "microservices", "distributed systems",
        ]

        for row in saved_rows:
            r = dict(row)
            company = r.get("company", "").strip()
            if company:
                companies[company] = companies.get(company, 0) + 1
            title = r.get("title", "").strip()
            if title:
                title_lower = title.lower()
                titles[title_lower] = titles.get(title_lower, 0) + 1
            loc = r.get("location", "").strip()
            if loc:
                locations[loc] = locations.get(loc, 0) + 1
            if r.get("min_amount"):
                salary_min_vals.append(float(r["min_amount"]))
            if r.get("max_amount"):
                salary_max_vals.append(float(r["max_amount"]))
            if r.get("is_remote"):
                remote_count += 1
            status = r.get("status", "saved")
            status_counts[status] = status_counts.get(status, 0) + 1

            desc = (r.get("description") or "").lower()
            descriptions_text += " " + desc

        for tech in tech_keywords:
            count = descriptions_text.count(tech)
            if count > 0:
                tech_mentions[tech] = count

        # Analyze search history
        search_terms: dict[str, int] = {}
        search_locations: dict[str, int] = {}
        search_remote = 0
        search_total = len(search_rows)

        for row in search_rows:
            r = dict(row)
            term = r.get("search_term", "").lower().strip()
            if term:
                search_terms[term] = search_terms.get(term, 0) + 1
            loc = r.get("location", "").strip()
            if loc:
                search_locations[loc] = search_locations.get(loc, 0) + 1
            if r.get("is_remote"):
                search_remote += 1

        top_companies = sorted(companies.items(), key=lambda x: -x[1])[:15]
        top_titles = sorted(titles.items(), key=lambda x: -x[1])[:10]
        top_locations = sorted(locations.items(), key=lambda x: -x[1])[:10]
        top_tech = sorted(tech_mentions.items(), key=lambda x: -x[1])[:20]
        top_search_terms = sorted(search_terms.items(), key=lambda x: -x[1])[:10]

        salary_range = None
        if salary_min_vals and salary_max_vals:
            salary_range = {
                "min_low": min(salary_min_vals),
                "min_high": max(salary_min_vals),
                "max_low": min(salary_max_vals),
                "max_high": max(salary_max_vals),
                "avg_min": sum(salary_min_vals) / len(salary_min_vals),
                "avg_max": sum(salary_max_vals) / len(salary_max_vals),
            }

        return json.dumps({
            "saved_jobs_total": len(saved_rows),
            "pipeline": status_counts,
            "target_companies": [{"company": c, "jobs_saved": n} for c, n in top_companies],
            "target_roles": [{"title": t, "count": n} for t, n in top_titles],
            "preferred_locations": [{"location": l, "count": n} for l, n in top_locations],
            "remote_preference": {
                "saved_remote_jobs": remote_count,
                "saved_total": len(saved_rows),
                "remote_percentage": round(remote_count / len(saved_rows) * 100) if saved_rows else 0,
            },
            "salary_range": salary_range,
            "in_demand_technologies": [{"tech": t, "mentions_in_jds": n} for t, n in top_tech],
            "search_activity": {
                "total_searches": search_total,
                "top_search_terms": [{"term": t, "count": n} for t, n in top_search_terms],
                "top_search_locations": [{"location": l, "count": n} for l, n in sorted(search_locations.items(), key=lambda x: -x[1])[:5]],
                "remote_search_percentage": round(search_remote / search_total * 100) if search_total else 0,
            },
        }, indent=2)
    except Exception as e:
        logger.error("get_user_job_interests error: %s", e)
        return json.dumps({"error": str(e)})
