"""Job search tools: search jobs by keywords, location, or resume match."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from app.resume_store import get_resume, list_resumes

from .shared import _uid

logger = logging.getLogger(__name__)


@tool
def search_jobs(
    search_term: str,
    location: str = "",
    site_name: str = "indeed,linkedin",
    results_wanted: int = 15,
    is_remote: bool = False,
    hours_old: int = 0,
) -> str:
    """Search for job listings using JSearch (RapidAPI).

    Use this tool to find jobs by title, keywords, location, remote status, or posting age.

    Args:
        search_term: Job title or keywords (e.g. "software engineer", "data scientist").
        location: City, state, or country. Leave empty for all locations.
        site_name: Comma-separated job sites: indeed, linkedin, glassdoor, zip_recruiter, google.
        results_wanted: Number of results (1-50). Default: 15.
        is_remote: Set to true for remote jobs only.
        hours_old: Only jobs posted within this many hours (24=day, 168=week, 0=no filter).

    Returns:
        JSON with total_found and jobs array containing title, company, location, salary, url, description.
    """
    try:
        from app.jsearch import jsearch as _search
        sites = [s.strip() for s in site_name.split(",")]
        raw_jobs = _search(
            search_term=search_term,
            location=location or None,
            site_name=sites,
            results_wanted=min(results_wanted, 50),
            is_remote=is_remote,
            hours_old=hours_old if hours_old > 0 else None,
        )

        if not raw_jobs:
            return json.dumps({
                "query": search_term,
                "location": location or None,
                "total_found": 0,
                "jobs": [],
                "message": f"No jobs found for '{search_term}'" + (f" in {location}" if location else "") + ". Try broadening search terms.",
            })

        result_jobs = []
        for job in raw_jobs[:results_wanted]:
            min_amt = job.get("min_amount")
            max_amt = job.get("max_amount")
            currency = job.get("currency", "USD")
            salary = None
            if min_amt and max_amt:
                salary = f"{currency} {min_amt:,.0f}-{max_amt:,.0f}"
            elif min_amt:
                salary = f"{currency} {min_amt:,.0f}+"

            result_jobs.append({
                "title": job.get("title", "Unknown"),
                "company": job.get("company", "Unknown"),
                "location": job.get("location", "Not specified"),
                "remote": bool(job.get("is_remote")),
                "salary": salary,
                "url": job.get("job_url", ""),
                "description": (job.get("description") or "")[:500],
                "site": job.get("site", ""),
                "date_posted": job.get("date_posted", ""),
            })

        return json.dumps({
            "query": search_term,
            "location": location or None,
            "total_found": len(raw_jobs),
            "jobs": result_jobs,
        })
    except Exception as e:
        logger.error("search_jobs error: %s", e)
        return f"Job search failed: {e}"


@tool
async def search_jobs_for_resume(resume_id: str = "", num_searches: int = 3) -> str:
    """Automatically search for jobs that match the user's resume.

    Reads the resume, identifies key skills and target roles, then runs
    multiple targeted searches. Use when the user wants automated job matching.

    Args:
        resume_id: Resume ID to match against. Leave empty for the latest resume.
        num_searches: Number of different search queries to run (1-5). Default: 3.

    Returns:
        JSON with search_terms_used, total_found, and deduplicated jobs array.
    """
    try:
        if not resume_id:
            resumes = await list_resumes(_uid())
            if not resumes:
                return "No resume uploaded. Please upload your resume first."
            resume_id = resumes[-1]

        text = await get_resume(resume_id, _uid())
        if not text:
            return f"Resume '{resume_id}' not found."

        text_lower = text.lower()

        potential_titles = []
        title_keywords = [
            "software engineer", "software developer", "data scientist",
            "data engineer", "product manager", "frontend developer",
            "backend developer", "full stack", "devops", "sre",
            "machine learning", "cloud engineer", "solutions architect",
            "technical lead", "engineering manager", "qa engineer",
            "mobile developer", "ios developer", "android developer",
            "security engineer", "platform engineer", "data analyst",
        ]
        for kw in title_keywords:
            if kw in text_lower:
                potential_titles.append(kw)

        if not potential_titles:
            potential_titles = ["software engineer"]

        search_terms = potential_titles[:min(num_searches, 5)]

        from app.jsearch import jsearch as _search
        all_results = []
        for term in search_terms:
            try:
                jobs = _search(
                    search_term=term,
                    site_name=["indeed", "linkedin"],
                    results_wanted=10,
                )
                for job in jobs:
                    job["_search_term"] = term
                all_results.extend(jobs)
            except Exception as e:
                logger.warning("Search for '%s' failed: %s", term, e)

        if not all_results:
            return json.dumps({
                "search_terms_used": search_terms,
                "total_found": 0,
                "jobs": [],
                "message": "No jobs found matching the resume profile. Try uploading a more detailed resume.",
            })

        seen_urls: set[str] = set()
        unique_jobs = []
        for job in all_results:
            url = job.get("job_url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_jobs.append(job)

        result_jobs = []
        for job in unique_jobs[:20]:
            min_amt = job.get("min_amount")
            max_amt = job.get("max_amount")
            salary = None
            if min_amt and max_amt:
                salary = f"${min_amt:,.0f}-${max_amt:,.0f}"

            result_jobs.append({
                "title": job.get("title", "Unknown"),
                "company": job.get("company", "Unknown"),
                "location": job.get("location", "Not specified"),
                "remote": bool(job.get("is_remote")),
                "salary": salary,
                "url": job.get("job_url", ""),
                "description": (job.get("description") or "")[:500],
                "matched_search": job.get("_search_term", ""),
            })

        return json.dumps({
            "search_terms_used": search_terms,
            "total_found": len(unique_jobs),
            "jobs": result_jobs,
        })
    except Exception as e:
        logger.error("search_jobs_for_resume error: %s", e)
        return f"Error searching for resume-matched jobs: {e}"
