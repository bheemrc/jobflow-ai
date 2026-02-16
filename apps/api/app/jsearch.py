"""Shared helper wrapping JSearch (RapidAPI) into dict format for the frontend."""

import httpx
import logging

from app.config import settings

logger = logging.getLogger(__name__)

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"

# Map hours_old to JSearch date_posted values
_DATE_POSTED_MAP = {
    24: "today",
    72: "3days",
    168: "week",
    720: "month",
}


def _hours_to_date_posted(hours_old: int | None) -> str:
    if not hours_old or hours_old <= 0:
        return "all"
    for threshold, value in sorted(_DATE_POSTED_MAP.items()):
        if hours_old <= threshold:
            return value
    return "month"


def jsearch(
    search_term: str,
    location: str | None = None,
    site_name: list[str] | None = None,
    results_wanted: int = 20,
    is_remote: bool = False,
    hours_old: int | None = None,
) -> list[dict]:
    """Call JSearch API and return list of job dicts matching frontend JobResult shape."""
    if not settings.rapidapi_key:
        raise ValueError("RAPIDAPI_KEY not configured")

    # Build query string: JSearch uses a single "query" param
    query = search_term
    if location:
        query += f" in {location}"
    if is_remote:
        query += " remote"

    params = {
        "query": query,
        "page": 1,
        "num_pages": max(1, (min(results_wanted, 50) + 9) // 10),
        "date_posted": _hours_to_date_posted(hours_old),
        "country": "us",
    }
    if is_remote:
        params["remote_jobs_only"] = "true"

    headers = {
        "x-rapidapi-host": "jsearch.p.rapidapi.com",
        "x-rapidapi-key": settings.rapidapi_key,
    }

    with httpx.Client(timeout=30) as client:
        resp = client.get(JSEARCH_URL, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    raw_jobs = data.get("data", [])

    jobs = []
    for item in raw_jobs[:results_wanted]:
        jobs.append({
            "title": item.get("job_title") or "Unknown",
            "company": item.get("employer_name") or "Unknown",
            "location": item.get("job_location") or "Not specified",
            "min_amount": item.get("job_min_salary"),
            "max_amount": item.get("job_max_salary"),
            "currency": "USD",
            "job_url": item.get("job_apply_link") or "",
            "date_posted": item.get("job_posted_at_datetime_utc", "")[:10] if item.get("job_posted_at_datetime_utc") else "",
            "job_type": item.get("job_employment_type"),
            "is_remote": bool(item.get("job_is_remote")),
            "description": item.get("job_description"),
            "site": item.get("job_publisher") or "",
            "employer_logo": item.get("employer_logo"),
        })
    return jobs
