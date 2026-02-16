from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from langchain_core.tools import tool

from app.config import settings
from app.db import get_conn
from app.resume_store import get_resume, list_resumes
from app.user_context import current_user_id

logger = logging.getLogger(__name__)


def _uid() -> str:
    """Get the current user_id from context."""
    return current_user_id.get()


# ──────────────────────────────────────────────────────────────
#  RESUME TOOLS
# ──────────────────────────────────────────────────────────────


@tool
async def review_resume(resume_id: str = "") -> str:
    """Retrieve and return the user's uploaded resume text from storage.

    Use this tool whenever you need to read or reference the user's resume.
    If no resume_id is provided, returns the most recently uploaded resume.

    Args:
        resume_id: The resume ID to retrieve. Leave empty to get the latest resume.

    Returns:
        The full resume text, or an error message if not found.
    """
    try:
        if not resume_id:
            resumes = await list_resumes(_uid())
            if not resumes:
                return "No resumes uploaded yet. Ask the user to upload their resume using the panel on the right side."
            resume_id = resumes[-1]

        text = await get_resume(resume_id, _uid())
        if not text:
            available = await list_resumes(_uid())
            return f"Resume '{resume_id}' not found. Available resumes: {available}"

        return f"[Resume ID: {resume_id}]\n\n{text}"
    except Exception as e:
        logger.error("review_resume error: %s", e)
        return f"Error reading resume: {e}"


@tool
async def extract_resume_profile(resume_id: str = "") -> str:
    """Parse the user's resume and extract a structured profile with skills,
    job titles, years of experience, education, and technologies.

    Use this tool when you need structured data about the user's background
    rather than the raw resume text. Returns JSON that you can reason over
    to build strategies, match jobs, or prepare interview materials.

    Args:
        resume_id: The resume ID to parse. Leave empty for the latest resume.

    Returns:
        JSON object with extracted profile fields, or error message.
    """
    try:
        if not resume_id:
            resumes = await list_resumes(_uid())
            if not resumes:
                return json.dumps({"error": "No resumes uploaded yet."})
            resume_id = resumes[-1]

        text = await get_resume(resume_id, _uid())
        if not text:
            return json.dumps({"error": f"Resume '{resume_id}' not found."})

        text_lower = text.lower()
        lines = text.split("\n")

        # Extract job titles found in resume
        title_keywords = [
            "software engineer", "software developer", "data scientist",
            "data engineer", "product manager", "frontend developer",
            "backend developer", "full stack", "fullstack", "devops", "sre",
            "machine learning engineer", "cloud engineer", "solutions architect",
            "technical lead", "tech lead", "engineering manager", "qa engineer",
            "mobile developer", "ios developer", "android developer",
            "security engineer", "platform engineer", "data analyst",
            "site reliability engineer", "staff engineer", "principal engineer",
            "senior software engineer", "senior developer", "web developer",
            "systems engineer", "infrastructure engineer",
        ]
        found_titles = [kw for kw in title_keywords if kw in text_lower]

        # Extract technologies/skills
        tech_keywords = [
            "python", "javascript", "typescript", "java", "c++", "c#", "go",
            "rust", "ruby", "php", "swift", "kotlin", "scala", "r",
            "react", "angular", "vue", "next.js", "node.js", "express",
            "django", "flask", "fastapi", "spring", "rails",
            "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
            "jenkins", "github actions", "ci/cd", "linux",
            "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
            "graphql", "rest api", "microservices", "kafka",
            "machine learning", "deep learning", "tensorflow", "pytorch",
            "sql", "nosql", "git", "agile", "scrum",
        ]
        found_tech = [kw for kw in tech_keywords if kw in text_lower]

        # Estimate years of experience from date patterns
        year_pattern = re.compile(r"(20\d{2}|19\d{2})")
        years_found = sorted(set(int(y) for y in year_pattern.findall(text)))
        experience_years = 0
        if len(years_found) >= 2:
            experience_years = years_found[-1] - years_found[0]

        # Estimate seniority
        seniority = "mid"
        if experience_years >= 10 or any(k in text_lower for k in ["staff", "principal", "director", "vp"]):
            seniority = "senior+"
        elif experience_years >= 5 or "senior" in text_lower:
            seniority = "senior"
        elif experience_years <= 2 or "junior" in text_lower or "intern" in text_lower:
            seniority = "junior"

        # Extract education signals
        education = []
        edu_keywords = ["bachelor", "master", "phd", "ph.d", "mba", "b.s.", "m.s.", "b.a.", "m.a."]
        for line in lines:
            ll = line.lower()
            if any(ek in ll for ek in edu_keywords):
                education.append(line.strip())

        # Extract company names
        companies = []
        company_pattern = re.compile(r"(?:at|@)\s+(.+?)(?:\s*[|,\-–]|$)", re.IGNORECASE)
        for line in lines:
            m = company_pattern.search(line)
            if m:
                companies.append(m.group(1).strip())

        # Count saved jobs to understand pipeline state
        pipeline = {"total": 0, "by_status": {}}
        try:
            async with get_conn() as conn:
                rows = await conn.fetch("SELECT status, COUNT(*) AS cnt FROM saved_jobs GROUP BY status")
                for r in rows:
                    pipeline["by_status"][r["status"]] = r["cnt"]
                    pipeline["total"] += r["cnt"]
        except Exception:
            pass

        profile = {
            "resume_id": resume_id,
            "titles": found_titles,
            "technologies": found_tech,
            "experience_years": experience_years,
            "seniority": seniority,
            "education": education[:5],
            "companies": companies[:10],
            "pipeline": pipeline,
        }

        return json.dumps(profile, indent=2)
    except Exception as e:
        logger.error("extract_resume_profile error: %s", e)
        return json.dumps({"error": str(e)})


# ──────────────────────────────────────────────────────────────
#  JOB SEARCH TOOLS
# ──────────────────────────────────────────────────────────────


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


# ──────────────────────────────────────────────────────────────
#  SAVED JOBS
# ──────────────────────────────────────────────────────────────


@tool
async def get_saved_jobs(status: str = "", limit: int = 20) -> str:
    """Retrieve the user's saved jobs from the database.

    Use this tool to access the user's saved/applied/interview job pipeline.

    Args:
        status: Filter by status: "saved", "applied", "interview", "offer", "rejected".
                Leave empty for all.
        limit: Maximum number of jobs to return (1-50). Default: 20.

    Returns:
        JSON with total count and jobs array with title, company, location, status, salary, url.
    """
    try:
        async with get_conn() as conn:
            if status:
                rows = await conn.fetch(
                    "SELECT * FROM saved_jobs WHERE status = $1 ORDER BY saved_at DESC LIMIT $2",
                    status, limit,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM saved_jobs ORDER BY saved_at DESC LIMIT $1",
                    limit,
                )

        if not rows:
            return json.dumps({
                "total": 0,
                "status_filter": status or None,
                "jobs": [],
            })

        result_jobs = []
        for row in rows:
            r = dict(row)
            salary = None
            if r.get("min_amount") and r.get("max_amount"):
                salary = f"${r['min_amount']:,.0f}-${r['max_amount']:,.0f}"

            result_jobs.append({
                "title": r.get("title", "Unknown"),
                "company": r.get("company", "Unknown"),
                "location": r.get("location", "Not specified"),
                "status": r.get("status", "saved"),
                "salary": salary,
                "url": r.get("job_url", ""),
                "description": (r.get("description") or "")[:500],
            })

        return json.dumps({
            "total": len(result_jobs),
            "status_filter": status or None,
            "jobs": result_jobs,
        })
    except Exception as e:
        logger.error("get_saved_jobs error: %s", e)
        return f"Error retrieving saved jobs: {e}"


@tool
async def save_job(
    title: str,
    company: str,
    job_url: str,
    location: str = "",
    min_amount: float = 0,
    max_amount: float = 0,
    currency: str = "USD",
    description: str = "",
    is_remote: bool = False,
    site: str = "",
    date_posted: str = "",
) -> str:
    """Save a job to the user's pipeline. Use this when you find a good match.

    The job is saved with status 'saved'. Deduplicates by URL — if the job
    is already saved, returns the existing record instead of creating a duplicate.

    Args:
        title: Job title (e.g. "Senior Software Engineer").
        company: Company name.
        job_url: The full URL to the job posting. Must be unique.
        location: Job location (city, state, or "Remote").
        min_amount: Minimum salary (0 if unknown).
        max_amount: Maximum salary (0 if unknown).
        currency: Salary currency code. Default: "USD".
        description: Job description text (first 2000 chars kept).
        is_remote: Whether the job is remote.
        site: Source site (indeed, linkedin, etc.).
        date_posted: Date the job was posted (ISO format or empty).

    Returns:
        JSON with saved job ID and status, or existing job info if duplicate.
    """
    try:
        if not job_url:
            return json.dumps({"error": "job_url is required to save a job."})

        async with get_conn() as conn:
            # Check for duplicate
            existing = await conn.fetchrow(
                "SELECT id, status FROM saved_jobs WHERE job_url = $1", job_url
            )
            if existing:
                return json.dumps({
                    "already_exists": True,
                    "job_id": existing["id"],
                    "status": existing["status"],
                    "message": f"Job already saved (id={existing['id']}, status={existing['status']})",
                })

            # Insert new job
            row = await conn.fetchrow("""
                INSERT INTO saved_jobs
                    (title, company, location, min_amount, max_amount, currency,
                     job_url, date_posted, is_remote, description, site, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'saved')
                RETURNING id
            """,
                title[:200],
                company[:200],
                location[:200],
                min_amount if min_amount > 0 else None,
                max_amount if max_amount > 0 else None,
                currency[:10],
                job_url[:2000],
                date_posted[:50] if date_posted else None,
                is_remote,
                description[:2000],
                site[:50],
            )
            job_id = row["id"]

        return json.dumps({
            "saved": True,
            "job_id": job_id,
            "title": title,
            "company": company,
            "message": f"Saved '{title}' at {company} to pipeline (id={job_id})",
        })
    except Exception as e:
        logger.error("save_job error: %s", e)
        return json.dumps({"error": f"Failed to save job: {e}"})


@tool
async def update_job_stage(job_id: int, new_stage: str, note: str = "") -> str:
    """Move a job to a different stage in the pipeline.

    Use this to progress jobs through the pipeline: saved → applied → interview → offer.
    Or mark jobs as rejected.

    Args:
        job_id: The job ID (from get_saved_jobs or save_job).
        new_stage: New stage: "saved", "applied", "interview", "offer", "rejected".
        note: Optional note explaining the stage change.

    Returns:
        JSON confirming the stage update.
    """
    valid_stages = ("saved", "applied", "interview", "offer", "rejected")
    if new_stage not in valid_stages:
        return json.dumps({"error": f"Invalid stage. Must be one of: {', '.join(valid_stages)}"})
    try:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                "SELECT id, title, company, status FROM saved_jobs WHERE id = $1", job_id
            )
            if not row:
                return json.dumps({"error": f"Job {job_id} not found."})
            old_stage = row["status"]
            note_append = f"\n[{new_stage}] {note}" if note else ""
            await conn.execute(
                "UPDATE saved_jobs SET status = $1, notes = COALESCE(notes, '') || $2, updated_at = NOW() WHERE id = $3",
                new_stage, note_append, job_id,
            )
        return json.dumps({
            "updated": True,
            "job_id": job_id,
            "title": row["title"],
            "company": row["company"],
            "old_stage": old_stage,
            "new_stage": new_stage,
            "message": f"Moved '{row['title']}' at {row['company']} from {old_stage} → {new_stage}",
        })
    except Exception as e:
        logger.error("update_job_stage error: %s", e)
        return json.dumps({"error": str(e)})


@tool
async def add_job_note(job_id: int, note: str) -> str:
    """Add a note to a job in the pipeline.

    Use this to annotate jobs with research findings, interview feedback, etc.

    Args:
        job_id: The job ID.
        note: The note text to append.

    Returns:
        JSON confirming the note was added.
    """
    try:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                "SELECT id, title FROM saved_jobs WHERE id = $1", job_id
            )
            if not row:
                return json.dumps({"error": f"Job {job_id} not found."})
            await conn.execute(
                "UPDATE saved_jobs SET notes = COALESCE(notes, '') || $1, updated_at = NOW() WHERE id = $2",
                f"\n{note}", job_id,
            )
        return json.dumps({"added": True, "job_id": job_id, "message": f"Note added to job {job_id}"})
    except Exception as e:
        logger.error("add_job_note error: %s", e)
        return json.dumps({"error": str(e)})


# ──────────────────────────────────────────────────────────────
#  SEARCH HISTORY & USER INTERESTS
# ──────────────────────────────────────────────────────────────


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


@tool
async def prepare_job_application(
    job_title: str,
    company: str,
    job_description: str,
    resume_id: str = "",
) -> str:
    """Gather resume text and job description into a structured context bundle
    for the agent to generate application materials from.

    Args:
        job_title: The title of the position to apply for.
        company: The company name.
        job_description: The full job description text.
        resume_id: Resume ID to use. Leave empty for the latest resume.

    Returns:
        Combined resume + job context for the agent to reason over.
    """
    try:
        if not resume_id:
            resumes = await list_resumes(_uid())
            if not resumes:
                return "No resume uploaded. Please upload your resume first."
            resume_id = resumes[-1]

        resume_text = await get_resume(resume_id, _uid())
        if not resume_text:
            return f"Resume '{resume_id}' not found."

        return (
            f"[RESUME]\n{resume_text[:4000]}\n\n"
            f"[TARGET POSITION]\nTitle: {job_title}\nCompany: {company}\n\n"
            f"[JOB DESCRIPTION]\n{job_description[:3000]}"
        )
    except Exception as e:
        logger.error("prepare_job_application error: %s", e)
        return f"Error preparing application: {e}"


@tool
async def generate_cover_letter(
    job_title: str,
    company: str,
    job_description: str,
    resume_id: str = "",
    tone: str = "professional",
) -> str:
    """Gather resume and job details for cover letter generation.

    Args:
        job_title: The title of the position to apply for.
        company: The company name.
        job_description: The full job description text.
        resume_id: Resume ID to use. Leave empty for the latest resume.
        tone: Writing tone — "professional", "enthusiastic", or "concise". Default: "professional".

    Returns:
        Combined resume + job context with tone preference.
    """
    try:
        if not resume_id:
            resumes = await list_resumes(_uid())
            if not resumes:
                return "No resume uploaded. Please upload your resume first."
            resume_id = resumes[-1]

        resume_text = await get_resume(resume_id, _uid())
        if not resume_text:
            return f"Resume '{resume_id}' not found."

        return (
            f"[RESUME]\n{resume_text[:3000]}\n\n"
            f"[TARGET]\nTitle: {job_title}\nCompany: {company}\nTone: {tone}\n\n"
            f"[JOB DESCRIPTION]\n{job_description[:2500]}"
        )
    except Exception as e:
        logger.error("generate_cover_letter error: %s", e)
        return f"Error generating cover letter: {e}"


# ──────────────────────────────────────────────────────────────
#  JOB PIPELINE TOOLS
# ──────────────────────────────────────────────────────────────


@tool
async def get_job_pipeline(status: str = "") -> str:
    """Get jobs organized by pipeline stage.

    Returns JSON with jobs grouped by status: saved, applied, interview, offer, rejected.

    Args:
        status: Optional filter for a specific stage. Leave empty for all stages.

    Returns:
        JSON with jobs grouped by pipeline stage.
    """
    try:
        async with get_conn() as conn:
            if status:
                rows = await conn.fetch(
                    "SELECT * FROM saved_jobs WHERE status = $1 ORDER BY saved_at DESC", status
                )
            else:
                rows = await conn.fetch("SELECT * FROM saved_jobs ORDER BY saved_at DESC")

        pipeline: dict[str, list] = {
            "saved": [], "applied": [], "interview": [], "offer": [], "rejected": []
        }
        for row in rows:
            r = dict(row)
            stage = r.get("status", "saved")
            if stage in pipeline:
                pipeline[stage].append(r)
            else:
                pipeline["saved"].append(r)

        return json.dumps(pipeline, default=str)
    except Exception as e:
        logger.error("get_job_pipeline error: %s", e)
        return f"Error getting job pipeline: {e}"


@tool
async def update_job_pipeline_stage(job_id: int, new_status: str) -> str:
    """Move a job to a new pipeline stage.

    Args:
        job_id: The saved job ID.
        new_status: New status (saved, applied, interview, offer, rejected).

    Returns:
        Confirmation message.
    """
    try:
        async with get_conn() as conn:
            result = await conn.execute(
                "UPDATE saved_jobs SET status = $1, updated_at = NOW() WHERE id = $2",
                new_status, job_id,
            )
            updated = result.split()[-1]  # "UPDATE N"

        if updated != "0":
            return f"Job {job_id} moved to '{new_status}' stage."
        return f"Job {job_id} not found."
    except Exception as e:
        logger.error("update_job_pipeline_stage error: %s", e)
        return f"Error updating job stage: {e}"


# ──────────────────────────────────────────────────────────────
#  WEB SEARCH (Tavily)
# ──────────────────────────────────────────────────────────────


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


# ──────────────────────────────────────────────────────────────
#  LEETCODE TOOLS
# ──────────────────────────────────────────────────────────────


@tool
def get_leetcode_progress() -> str:
    """Get the user's LeetCode practice progress.

    Returns JSON with solved count, streak, mastery by topic, recent problems.
    """
    # This returns mock data initially; real data comes from PostgreSQL via db.py
    return json.dumps({
        "total_solved": 0,
        "total_attempted": 0,
        "streak": 0,
        "problems": [],
        "mastery": [],
        "message": "No LeetCode data yet. Start practicing to track progress!",
    })


@tool
def select_leetcode_problems(topics: str = "arrays,dp", difficulty: str = "medium", count: int = 3) -> str:
    """Select LeetCode problems for practice based on weak topics.

    Args:
        topics: Comma-separated topics to practice (e.g., "graphs,dp").
        difficulty: easy, medium, or hard.
        count: Number of problems to select.

    Returns:
        JSON with selected problems.
    """
    # Curated problem set by topic — covers all major interview patterns
    problem_bank = {
        "arrays": [
            {"id": 1, "title": "Two Sum", "difficulty": "easy", "pattern": "hash map", "url": "https://leetcode.com/problems/two-sum/"},
            {"id": 217, "title": "Contains Duplicate", "difficulty": "easy", "pattern": "hash set", "url": "https://leetcode.com/problems/contains-duplicate/"},
            {"id": 238, "title": "Product of Array Except Self", "difficulty": "medium", "pattern": "prefix sum", "url": "https://leetcode.com/problems/product-of-array-except-self/"},
            {"id": 15, "title": "3Sum", "difficulty": "medium", "pattern": "two pointers", "url": "https://leetcode.com/problems/3sum/"},
            {"id": 11, "title": "Container With Most Water", "difficulty": "medium", "pattern": "two pointers", "url": "https://leetcode.com/problems/container-with-most-water/"},
            {"id": 42, "title": "Trapping Rain Water", "difficulty": "hard", "pattern": "two pointers / stack", "url": "https://leetcode.com/problems/trapping-rain-water/"},
            {"id": 128, "title": "Longest Consecutive Sequence", "difficulty": "medium", "pattern": "hash set", "url": "https://leetcode.com/problems/longest-consecutive-sequence/"},
            {"id": 41, "title": "First Missing Positive", "difficulty": "hard", "pattern": "cyclic sort", "url": "https://leetcode.com/problems/first-missing-positive/"},
        ],
        "sliding_window": [
            {"id": 121, "title": "Best Time to Buy and Sell Stock", "difficulty": "easy", "pattern": "sliding window", "url": "https://leetcode.com/problems/best-time-to-buy-and-sell-stock/"},
            {"id": 3, "title": "Longest Substring Without Repeating Characters", "difficulty": "medium", "pattern": "sliding window + hash", "url": "https://leetcode.com/problems/longest-substring-without-repeating-characters/"},
            {"id": 424, "title": "Longest Repeating Character Replacement", "difficulty": "medium", "pattern": "sliding window", "url": "https://leetcode.com/problems/longest-repeating-character-replacement/"},
            {"id": 76, "title": "Minimum Window Substring", "difficulty": "hard", "pattern": "sliding window + hash", "url": "https://leetcode.com/problems/minimum-window-substring/"},
            {"id": 239, "title": "Sliding Window Maximum", "difficulty": "hard", "pattern": "monotonic deque", "url": "https://leetcode.com/problems/sliding-window-maximum/"},
        ],
        "binary_search": [
            {"id": 704, "title": "Binary Search", "difficulty": "easy", "pattern": "binary search", "url": "https://leetcode.com/problems/binary-search/"},
            {"id": 33, "title": "Search in Rotated Sorted Array", "difficulty": "medium", "pattern": "modified binary search", "url": "https://leetcode.com/problems/search-in-rotated-sorted-array/"},
            {"id": 153, "title": "Find Minimum in Rotated Sorted Array", "difficulty": "medium", "pattern": "binary search", "url": "https://leetcode.com/problems/find-minimum-in-rotated-sorted-array/"},
            {"id": 4, "title": "Median of Two Sorted Arrays", "difficulty": "hard", "pattern": "binary search", "url": "https://leetcode.com/problems/median-of-two-sorted-arrays/"},
            {"id": 875, "title": "Koko Eating Bananas", "difficulty": "medium", "pattern": "binary search on answer", "url": "https://leetcode.com/problems/koko-eating-bananas/"},
        ],
        "linked_list": [
            {"id": 206, "title": "Reverse Linked List", "difficulty": "easy", "pattern": "in-place reversal", "url": "https://leetcode.com/problems/reverse-linked-list/"},
            {"id": 21, "title": "Merge Two Sorted Lists", "difficulty": "easy", "pattern": "merge", "url": "https://leetcode.com/problems/merge-two-sorted-lists/"},
            {"id": 141, "title": "Linked List Cycle", "difficulty": "easy", "pattern": "fast & slow pointers", "url": "https://leetcode.com/problems/linked-list-cycle/"},
            {"id": 143, "title": "Reorder List", "difficulty": "medium", "pattern": "fast & slow + reverse", "url": "https://leetcode.com/problems/reorder-list/"},
            {"id": 19, "title": "Remove Nth Node From End of List", "difficulty": "medium", "pattern": "two pointers", "url": "https://leetcode.com/problems/remove-nth-node-from-end-of-list/"},
            {"id": 23, "title": "Merge k Sorted Lists", "difficulty": "hard", "pattern": "heap / divide & conquer", "url": "https://leetcode.com/problems/merge-k-sorted-lists/"},
            {"id": 138, "title": "Copy List with Random Pointer", "difficulty": "medium", "pattern": "hash map", "url": "https://leetcode.com/problems/copy-list-with-random-pointer/"},
        ],
        "trees": [
            {"id": 226, "title": "Invert Binary Tree", "difficulty": "easy", "pattern": "DFS", "url": "https://leetcode.com/problems/invert-binary-tree/"},
            {"id": 104, "title": "Maximum Depth of Binary Tree", "difficulty": "easy", "pattern": "DFS", "url": "https://leetcode.com/problems/maximum-depth-of-binary-tree/"},
            {"id": 100, "title": "Same Tree", "difficulty": "easy", "pattern": "DFS", "url": "https://leetcode.com/problems/same-tree/"},
            {"id": 102, "title": "Binary Tree Level Order Traversal", "difficulty": "medium", "pattern": "BFS", "url": "https://leetcode.com/problems/binary-tree-level-order-traversal/"},
            {"id": 98, "title": "Validate Binary Search Tree", "difficulty": "medium", "pattern": "DFS + range", "url": "https://leetcode.com/problems/validate-binary-search-tree/"},
            {"id": 236, "title": "Lowest Common Ancestor of a Binary Tree", "difficulty": "medium", "pattern": "DFS", "url": "https://leetcode.com/problems/lowest-common-ancestor-of-a-binary-tree/"},
            {"id": 124, "title": "Binary Tree Maximum Path Sum", "difficulty": "hard", "pattern": "DFS + global max", "url": "https://leetcode.com/problems/binary-tree-maximum-path-sum/"},
            {"id": 297, "title": "Serialize and Deserialize Binary Tree", "difficulty": "hard", "pattern": "BFS / DFS", "url": "https://leetcode.com/problems/serialize-and-deserialize-binary-tree/"},
            {"id": 105, "title": "Construct Binary Tree from Preorder and Inorder Traversal", "difficulty": "medium", "pattern": "recursion + hash", "url": "https://leetcode.com/problems/construct-binary-tree-from-preorder-and-inorder-traversal/"},
        ],
        "graphs": [
            {"id": 200, "title": "Number of Islands", "difficulty": "medium", "pattern": "BFS / DFS", "url": "https://leetcode.com/problems/number-of-islands/"},
            {"id": 133, "title": "Clone Graph", "difficulty": "medium", "pattern": "BFS + hash", "url": "https://leetcode.com/problems/clone-graph/"},
            {"id": 207, "title": "Course Schedule", "difficulty": "medium", "pattern": "topological sort", "url": "https://leetcode.com/problems/course-schedule/"},
            {"id": 417, "title": "Pacific Atlantic Water Flow", "difficulty": "medium", "pattern": "multi-source BFS", "url": "https://leetcode.com/problems/pacific-atlantic-water-flow/"},
            {"id": 684, "title": "Redundant Connection", "difficulty": "medium", "pattern": "union find", "url": "https://leetcode.com/problems/redundant-connection/"},
            {"id": 743, "title": "Network Delay Time", "difficulty": "medium", "pattern": "Dijkstra", "url": "https://leetcode.com/problems/network-delay-time/"},
            {"id": 269, "title": "Alien Dictionary", "difficulty": "hard", "pattern": "topological sort", "url": "https://leetcode.com/problems/alien-dictionary/"},
            {"id": 787, "title": "Cheapest Flights Within K Stops", "difficulty": "medium", "pattern": "Bellman-Ford / BFS", "url": "https://leetcode.com/problems/cheapest-flights-within-k-stops/"},
        ],
        "dp": [
            {"id": 70, "title": "Climbing Stairs", "difficulty": "easy", "pattern": "1D DP", "url": "https://leetcode.com/problems/climbing-stairs/"},
            {"id": 198, "title": "House Robber", "difficulty": "medium", "pattern": "1D DP", "url": "https://leetcode.com/problems/house-robber/"},
            {"id": 322, "title": "Coin Change", "difficulty": "medium", "pattern": "unbounded knapsack", "url": "https://leetcode.com/problems/coin-change/"},
            {"id": 300, "title": "Longest Increasing Subsequence", "difficulty": "medium", "pattern": "1D DP + binary search", "url": "https://leetcode.com/problems/longest-increasing-subsequence/"},
            {"id": 1143, "title": "Longest Common Subsequence", "difficulty": "medium", "pattern": "2D DP", "url": "https://leetcode.com/problems/longest-common-subsequence/"},
            {"id": 518, "title": "Coin Change II", "difficulty": "medium", "pattern": "unbounded knapsack", "url": "https://leetcode.com/problems/coin-change-ii/"},
            {"id": 72, "title": "Edit Distance", "difficulty": "medium", "pattern": "2D DP", "url": "https://leetcode.com/problems/edit-distance/"},
            {"id": 312, "title": "Burst Balloons", "difficulty": "hard", "pattern": "interval DP", "url": "https://leetcode.com/problems/burst-balloons/"},
            {"id": 10, "title": "Regular Expression Matching", "difficulty": "hard", "pattern": "2D DP", "url": "https://leetcode.com/problems/regular-expression-matching/"},
            {"id": 152, "title": "Maximum Product Subarray", "difficulty": "medium", "pattern": "DP with min/max", "url": "https://leetcode.com/problems/maximum-product-subarray/"},
        ],
        "strings": [
            {"id": 242, "title": "Valid Anagram", "difficulty": "easy", "pattern": "hash map / sort", "url": "https://leetcode.com/problems/valid-anagram/"},
            {"id": 49, "title": "Group Anagrams", "difficulty": "medium", "pattern": "hash map", "url": "https://leetcode.com/problems/group-anagrams/"},
            {"id": 20, "title": "Valid Parentheses", "difficulty": "easy", "pattern": "stack", "url": "https://leetcode.com/problems/valid-parentheses/"},
            {"id": 5, "title": "Longest Palindromic Substring", "difficulty": "medium", "pattern": "expand from center / DP", "url": "https://leetcode.com/problems/longest-palindromic-substring/"},
            {"id": 647, "title": "Palindromic Substrings", "difficulty": "medium", "pattern": "expand from center", "url": "https://leetcode.com/problems/palindromic-substrings/"},
            {"id": 271, "title": "Encode and Decode Strings", "difficulty": "medium", "pattern": "design", "url": "https://leetcode.com/problems/encode-and-decode-strings/"},
        ],
        "heap": [
            {"id": 703, "title": "Kth Largest Element in a Stream", "difficulty": "easy", "pattern": "min heap", "url": "https://leetcode.com/problems/kth-largest-element-in-a-stream/"},
            {"id": 215, "title": "Kth Largest Element in an Array", "difficulty": "medium", "pattern": "quickselect / heap", "url": "https://leetcode.com/problems/kth-largest-element-in-an-array/"},
            {"id": 347, "title": "Top K Frequent Elements", "difficulty": "medium", "pattern": "heap / bucket sort", "url": "https://leetcode.com/problems/top-k-frequent-elements/"},
            {"id": 295, "title": "Find Median from Data Stream", "difficulty": "hard", "pattern": "two heaps", "url": "https://leetcode.com/problems/find-median-from-data-stream/"},
            {"id": 621, "title": "Task Scheduler", "difficulty": "medium", "pattern": "greedy / heap", "url": "https://leetcode.com/problems/task-scheduler/"},
        ],
        "backtracking": [
            {"id": 78, "title": "Subsets", "difficulty": "medium", "pattern": "backtracking", "url": "https://leetcode.com/problems/subsets/"},
            {"id": 46, "title": "Permutations", "difficulty": "medium", "pattern": "backtracking", "url": "https://leetcode.com/problems/permutations/"},
            {"id": 39, "title": "Combination Sum", "difficulty": "medium", "pattern": "backtracking", "url": "https://leetcode.com/problems/combination-sum/"},
            {"id": 79, "title": "Word Search", "difficulty": "medium", "pattern": "backtracking + DFS", "url": "https://leetcode.com/problems/word-search/"},
            {"id": 51, "title": "N-Queens", "difficulty": "hard", "pattern": "backtracking", "url": "https://leetcode.com/problems/n-queens/"},
            {"id": 131, "title": "Palindrome Partitioning", "difficulty": "medium", "pattern": "backtracking", "url": "https://leetcode.com/problems/palindrome-partitioning/"},
        ],
        "greedy": [
            {"id": 55, "title": "Jump Game", "difficulty": "medium", "pattern": "greedy", "url": "https://leetcode.com/problems/jump-game/"},
            {"id": 45, "title": "Jump Game II", "difficulty": "medium", "pattern": "greedy BFS", "url": "https://leetcode.com/problems/jump-game-ii/"},
            {"id": 134, "title": "Gas Station", "difficulty": "medium", "pattern": "greedy", "url": "https://leetcode.com/problems/gas-station/"},
            {"id": 846, "title": "Hand of Straights", "difficulty": "medium", "pattern": "greedy + hash", "url": "https://leetcode.com/problems/hand-of-straights/"},
            {"id": 763, "title": "Partition Labels", "difficulty": "medium", "pattern": "greedy", "url": "https://leetcode.com/problems/partition-labels/"},
        ],
        "intervals": [
            {"id": 57, "title": "Insert Interval", "difficulty": "medium", "pattern": "intervals", "url": "https://leetcode.com/problems/insert-interval/"},
            {"id": 56, "title": "Merge Intervals", "difficulty": "medium", "pattern": "sort + merge", "url": "https://leetcode.com/problems/merge-intervals/"},
            {"id": 435, "title": "Non-overlapping Intervals", "difficulty": "medium", "pattern": "greedy intervals", "url": "https://leetcode.com/problems/non-overlapping-intervals/"},
            {"id": 252, "title": "Meeting Rooms", "difficulty": "easy", "pattern": "sort", "url": "https://leetcode.com/problems/meeting-rooms/"},
            {"id": 253, "title": "Meeting Rooms II", "difficulty": "medium", "pattern": "heap / sweep line", "url": "https://leetcode.com/problems/meeting-rooms-ii/"},
        ],
        "stack": [
            {"id": 155, "title": "Min Stack", "difficulty": "medium", "pattern": "stack design", "url": "https://leetcode.com/problems/min-stack/"},
            {"id": 150, "title": "Evaluate Reverse Polish Notation", "difficulty": "medium", "pattern": "stack", "url": "https://leetcode.com/problems/evaluate-reverse-polish-notation/"},
            {"id": 739, "title": "Daily Temperatures", "difficulty": "medium", "pattern": "monotonic stack", "url": "https://leetcode.com/problems/daily-temperatures/"},
            {"id": 84, "title": "Largest Rectangle in Histogram", "difficulty": "hard", "pattern": "monotonic stack", "url": "https://leetcode.com/problems/largest-rectangle-in-histogram/"},
            {"id": 853, "title": "Car Fleet", "difficulty": "medium", "pattern": "stack + sort", "url": "https://leetcode.com/problems/car-fleet/"},
        ],
        "trie": [
            {"id": 208, "title": "Implement Trie (Prefix Tree)", "difficulty": "medium", "pattern": "trie", "url": "https://leetcode.com/problems/implement-trie-prefix-tree/"},
            {"id": 211, "title": "Design Add and Search Words Data Structure", "difficulty": "medium", "pattern": "trie + DFS", "url": "https://leetcode.com/problems/design-add-and-search-words-data-structure/"},
            {"id": 212, "title": "Word Search II", "difficulty": "hard", "pattern": "trie + backtracking", "url": "https://leetcode.com/problems/word-search-ii/"},
        ],
        "union_find": [
            {"id": 323, "title": "Number of Connected Components in an Undirected Graph", "difficulty": "medium", "pattern": "union find", "url": "https://leetcode.com/problems/number-of-connected-components-in-an-undirected-graph/"},
            {"id": 128, "title": "Longest Consecutive Sequence", "difficulty": "medium", "pattern": "union find / hash set", "url": "https://leetcode.com/problems/longest-consecutive-sequence/"},
            {"id": 305, "title": "Number of Islands II", "difficulty": "hard", "pattern": "union find", "url": "https://leetcode.com/problems/number-of-islands-ii/"},
        ],
        "bit_manipulation": [
            {"id": 136, "title": "Single Number", "difficulty": "easy", "pattern": "XOR", "url": "https://leetcode.com/problems/single-number/"},
            {"id": 191, "title": "Number of 1 Bits", "difficulty": "easy", "pattern": "bit counting", "url": "https://leetcode.com/problems/number-of-1-bits/"},
            {"id": 338, "title": "Counting Bits", "difficulty": "easy", "pattern": "DP + bits", "url": "https://leetcode.com/problems/counting-bits/"},
            {"id": 371, "title": "Sum of Two Integers", "difficulty": "medium", "pattern": "bit manipulation", "url": "https://leetcode.com/problems/sum-of-two-integers/"},
        ],
        "math": [
            {"id": 48, "title": "Rotate Image", "difficulty": "medium", "pattern": "matrix", "url": "https://leetcode.com/problems/rotate-image/"},
            {"id": 54, "title": "Spiral Matrix", "difficulty": "medium", "pattern": "matrix", "url": "https://leetcode.com/problems/spiral-matrix/"},
            {"id": 73, "title": "Set Matrix Zeroes", "difficulty": "medium", "pattern": "matrix in-place", "url": "https://leetcode.com/problems/set-matrix-zeroes/"},
            {"id": 202, "title": "Happy Number", "difficulty": "easy", "pattern": "fast & slow", "url": "https://leetcode.com/problems/happy-number/"},
            {"id": 50, "title": "Pow(x, n)", "difficulty": "medium", "pattern": "fast exponentiation", "url": "https://leetcode.com/problems/powx-n/"},
        ],
        "design": [
            {"id": 146, "title": "LRU Cache", "difficulty": "medium", "pattern": "hash map + doubly linked list", "url": "https://leetcode.com/problems/lru-cache/"},
            {"id": 460, "title": "LFU Cache", "difficulty": "hard", "pattern": "hash map + doubly linked list", "url": "https://leetcode.com/problems/lfu-cache/"},
            {"id": 380, "title": "Insert Delete GetRandom O(1)", "difficulty": "medium", "pattern": "hash map + array", "url": "https://leetcode.com/problems/insert-delete-getrandom-o1/"},
            {"id": 355, "title": "Design Twitter", "difficulty": "medium", "pattern": "heap + hash map", "url": "https://leetcode.com/problems/design-twitter/"},
        ],
    }

    topic_list = [t.strip().lower() for t in topics.split(",")]
    selected = []
    for topic in topic_list:
        problems = problem_bank.get(topic, [])
        filtered = [p for p in problems if p["difficulty"] == difficulty] or problems
        selected.extend(filtered[:count])

    available_topics = sorted(problem_bank.keys())

    return json.dumps({
        "topics": topic_list,
        "difficulty": difficulty,
        "total_in_bank": sum(len(v) for v in problem_bank.values()),
        "available_topics": available_topics,
        "problems": selected[:count],
    })


@tool
def log_leetcode_attempt_tool(problem_id: int, solved: bool, time_minutes: int = 0) -> str:
    """Log a LeetCode problem attempt.

    Args:
        problem_id: The LeetCode problem number.
        solved: Whether the user solved it.
        time_minutes: Time spent in minutes.

    Returns:
        Confirmation message.
    """
    return json.dumps({
        "logged": True,
        "problem_id": problem_id,
        "solved": solved,
        "time_minutes": time_minutes,
        "message": f"Logged attempt for problem {problem_id}. {'Solved!' if solved else 'Keep practicing!'}",
    })


# ──────────────────────────────────────────────────────────────
#  INTEGRATION / NOTIFICATION TOOLS
# ──────────────────────────────────────────────────────────────


@tool
def send_notification(channel: str, message: str, bot_name: str = "") -> str:
    """Send a notification through a configured channel (Telegram, Slack, Discord, or webhook).

    Use this tool to send bot outputs, alerts, or reports to external platforms.
    The channel must be pre-configured in the bot's integration settings.

    Args:
        channel: The channel type — "telegram", "slack", "discord", or "webhook".
        message: The message text to send. Supports markdown formatting.
        bot_name: The bot sending the notification (for attribution in the message).

    Returns:
        JSON with delivery status.
    """
    try:
        channel = channel.lower().strip()
        supported = ("telegram", "slack", "discord", "webhook")
        if channel not in supported:
            return json.dumps({
                "sent": False,
                "error": f"Unknown channel '{channel}'. Supported: {', '.join(supported)}.",
            })

        sender = bot_name or "Nexus Bot"

        # ── Telegram ──────────────────────────────────────────
        if channel == "telegram":
            token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
            chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
            if not token:
                return json.dumps({"sent": False, "channel": "telegram",
                                   "error": "TELEGRAM_BOT_TOKEN not configured."})
            if not chat_id:
                return json.dumps({"sent": False, "channel": "telegram",
                                   "error": "TELEGRAM_CHAT_ID not configured."})

            # Telegram limit is 4096 chars; split if needed
            header = f"*{sender}*\n\n"
            max_len = 4096 - len(header)
            chunks = [message[i:i + max_len] for i in range(0, len(message), max_len)]

            api_url = f"https://api.telegram.org/bot{token}/sendMessage"
            sent_count = 0
            with httpx.Client(timeout=15) as client:
                for chunk in chunks:
                    text = header + chunk if sent_count == 0 else chunk
                    resp = client.post(api_url, json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True,
                    })
                    if resp.status_code == 200:
                        sent_count += 1
                    else:
                        return json.dumps({
                            "sent": False, "channel": "telegram",
                            "error": f"Telegram API error {resp.status_code}: {resp.text[:300]}",
                            "chunks_sent": sent_count,
                        })

            return json.dumps({"sent": True, "channel": "telegram",
                               "chunks_sent": sent_count})

        # ── Slack ─────────────────────────────────────────────
        if channel == "slack":
            webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
            if not webhook_url:
                return json.dumps({"sent": False, "channel": "slack",
                                   "error": "SLACK_WEBHOOK_URL not configured."})

            payload = {
                "text": f"*{sender}*\n{message}",
                "username": sender,
                "icon_emoji": ":robot_face:",
            }
            with httpx.Client(timeout=15) as client:
                resp = client.post(webhook_url, json=payload)
                if resp.status_code == 200:
                    return json.dumps({"sent": True, "channel": "slack"})
                return json.dumps({"sent": False, "channel": "slack",
                                   "error": f"Slack returned {resp.status_code}: {resp.text[:300]}"})

        # ── Discord ───────────────────────────────────────────
        if channel == "discord":
            webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
            if not webhook_url:
                return json.dumps({"sent": False, "channel": "discord",
                                   "error": "DISCORD_WEBHOOK_URL not configured."})

            # Discord limit is 2000 chars
            content = f"**{sender}**\n{message}"
            if len(content) > 2000:
                content = content[:1997] + "..."

            payload = {"content": content, "username": sender}
            with httpx.Client(timeout=15) as client:
                resp = client.post(webhook_url, json=payload)
                if resp.status_code in (200, 204):
                    return json.dumps({"sent": True, "channel": "discord"})
                return json.dumps({"sent": False, "channel": "discord",
                                   "error": f"Discord returned {resp.status_code}: {resp.text[:300]}"})

        # ── Generic webhook ───────────────────────────────────
        if channel == "webhook":
            webhook_url = os.environ.get("WEBHOOK_URL", "")
            if not webhook_url:
                return json.dumps({"sent": False, "channel": "webhook",
                                   "error": "WEBHOOK_URL not configured."})

            payload = {
                "source": "jobflow",
                "bot_name": sender,
                "message": message,
                "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            }
            with httpx.Client(timeout=15) as client:
                resp = client.post(webhook_url, json=payload)
                resp.raise_for_status()
            return json.dumps({"sent": True, "channel": "webhook",
                               "status_code": resp.status_code})

        return json.dumps({"sent": False, "error": "Unhandled channel."})
    except Exception as e:
        logger.error("send_notification error: %s", e)
        return json.dumps({"sent": False, "error": str(e)})


@tool
def call_webhook(url: str, method: str = "POST", payload: str = "{}") -> str:
    """Call an external webhook or API endpoint.

    Use this tool to integrate with external services, MCP servers, or custom APIs.
    The bot can use this to send data to any HTTP endpoint.

    Args:
        url: The full URL of the webhook or API endpoint.
        method: HTTP method — "GET" or "POST". Default: "POST".
        payload: JSON string payload for POST requests.

    Returns:
        JSON with the response status and body preview.
    """
    try:
        method = method.upper().strip()
        if method not in ("GET", "POST"):
            return json.dumps({"error": "Only GET and POST methods are supported."})

        # Security: only allow https and known safe domains
        if not url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            return json.dumps({"error": "Only HTTPS URLs or localhost are allowed for security."})

        with httpx.Client(timeout=30) as client:
            if method == "POST":
                try:
                    body = json.loads(payload)
                except json.JSONDecodeError:
                    return json.dumps({"error": "Invalid JSON payload."})
                resp = client.post(url, json=body)
            else:
                resp = client.get(url)

            return json.dumps({
                "status_code": resp.status_code,
                "body_preview": resp.text[:2000],
                "headers": dict(list(resp.headers.items())[:10]),
            })
    except Exception as e:
        logger.error("call_webhook error: %s", e)
        return json.dumps({"error": f"Webhook call failed: {e}"})


# ──────────────────────────────────────────────────────────────
#  PREP MATERIALS TOOL
# ──────────────────────────────────────────────────────────────


@tool
async def generate_prep_materials(
    material_type: str,
    title: str,
    content: str,
    company: str = "",
    role: str = "",
    resources: str = "[]",
    scheduled_date: str = "",
    agent_source: str = "",
) -> str:
    """Save structured prep materials (interview prep, system design, LeetCode plans,
    company research) to the database for display on the Prep page.

    Call this tool at the end of your analysis to persist prep materials so the user
    can review them later on the Prep page.

    Args:
        material_type: Type of material — "interview", "system_design", "leetcode", "company_research", or "general".
        title: A descriptive title for the material (e.g. "Amazon SDE2 Interview Prep").
        content: JSON string containing the structured content. Structure depends on type.
        company: Company name if applicable.
        role: Target role if applicable.
        resources: JSON array of resource objects [{title, url, type}].
        scheduled_date: ISO date string for scheduled prep (e.g. "2024-03-15").
        agent_source: Name of the agent that created this material.

    Returns:
        JSON with saved status and material_id.
    """
    valid_types = ("interview", "system_design", "leetcode", "company_research", "general")
    if material_type not in valid_types:
        return json.dumps({"error": f"Invalid material_type. Must be one of: {', '.join(valid_types)}"})

    try:
        # Validate content is valid JSON
        try:
            content_parsed = json.loads(content) if isinstance(content, str) else content
        except json.JSONDecodeError:
            # If not valid JSON, wrap the string as a content object
            content_parsed = {"text": content}

        # Validate resources
        try:
            resources_parsed = json.loads(resources) if isinstance(resources, str) else resources
            if not isinstance(resources_parsed, list):
                resources_parsed = []
        except json.JSONDecodeError:
            resources_parsed = []

        from app.db import create_prep_material
        material_id = await create_prep_material(
            material_type=material_type,
            title=title[:500],
            content=content_parsed,
            company=company[:200] if company else None,
            role=role[:200] if role else None,
            agent_source=agent_source[:100] if agent_source else None,
            resources=resources_parsed,
            scheduled_date=scheduled_date[:50] if scheduled_date else None,
        )

        return json.dumps({
            "saved": True,
            "material_id": material_id,
            "material_type": material_type,
            "title": title,
            "message": f"Prep material '{title}' saved (id={material_id})",
        })
    except Exception as e:
        logger.error("generate_prep_materials error: %s", e)
        return json.dumps({"error": f"Failed to save prep material: {e}"})


# ──────────────────────────────────────────────────────────────
#  BOT MANAGEMENT TOOL
# ──────────────────────────────────────────────────────────────


@tool
def manage_bot(
    action: str,
    bot_name: str = "",
    bot_config: str = "{}",
) -> str:
    """Manage bots from within agent conversations — start, stop, pause, resume,
    create new bots, or list all bot states.

    Use this tool when you want to trigger another bot to do work, or when the user
    asks to create a new specialized bot based on your recommendations.

    Args:
        action: The action to perform — "start", "stop", "pause", "resume", "create", or "list".
        bot_name: The bot name (required for start/stop/pause/resume, used as name for create).
        bot_config: JSON string with bot configuration for "create" action. Fields:
                     display_name, description, model, temperature, max_tokens, tools (array),
                     prompt, schedule_type (interval/cron), schedule_hours, schedule_hour,
                     schedule_minute, requires_approval, timeout_minutes.

    Returns:
        JSON with the action result.
    """
    valid_actions = ("start", "stop", "pause", "resume", "create", "list")
    if action not in valid_actions:
        return json.dumps({"error": f"Invalid action. Must be one of: {', '.join(valid_actions)}"})

    try:
        from app.bot_manager import bot_manager

        if action == "list":
            states = bot_manager.get_all_states()
            return json.dumps({
                "action": "list",
                "bots": [
                    {
                        "name": s.get("name"),
                        "display_name": s.get("display_name"),
                        "status": s.get("status"),
                        "enabled": s.get("enabled"),
                        "last_run_at": s.get("last_run_at"),
                        "cooldown_until": s.get("cooldown_until"),
                        "runs_today": s.get("runs_today", 0),
                        "last_activated_by": s.get("last_activated_by"),
                        "total_runs": s.get("total_runs", 0),
                    }
                    for s in states
                ],
            })

        if not bot_name:
            return json.dumps({"error": f"bot_name is required for action '{action}'"})

        # For start/stop/pause/resume, bridge to async bot_manager methods
        if action in ("start", "stop", "pause", "resume"):
            loop = asyncio.get_event_loop()
            if action == "start":
                coro = bot_manager.start_bot(bot_name, trigger_type="agent")
            elif action == "stop":
                coro = bot_manager.stop_bot(bot_name)
            elif action == "pause":
                coro = bot_manager.pause_bot(bot_name)
            else:
                coro = bot_manager.resume_bot(bot_name)

            # LangChain tools run in a thread executor; schedule the coroutine on the event loop
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            result = future.result(timeout=30)
            return json.dumps({"action": action, "bot_name": bot_name, **result})

        # Create action
        if action == "create":
            try:
                config = json.loads(bot_config) if isinstance(bot_config, str) else bot_config
            except json.JSONDecodeError:
                return json.dumps({"error": "Invalid JSON in bot_config"})

            from app.bot_config import BotConfig, BotScheduleConfig

            schedule_type = config.get("schedule_type", "interval")
            if schedule_type == "interval":
                schedule = BotScheduleConfig(type="interval", hours=config.get("schedule_hours", 6))
            elif schedule_type == "cron":
                schedule = BotScheduleConfig(
                    type="cron",
                    hour=config.get("schedule_hour", 0),
                    minute=config.get("schedule_minute", 0),
                )
            else:
                return json.dumps({"error": "schedule_type must be 'interval' or 'cron'"})

            new_config = BotConfig(
                name=bot_name,
                display_name=config.get("display_name", bot_name),
                description=config.get("description", ""),
                model=config.get("model", "default"),
                temperature=config.get("temperature", 0.3),
                max_tokens=config.get("max_tokens", 4096),
                tools=config.get("tools", []),
                prompt=config.get("prompt", ""),
                schedule=schedule,
                requires_approval=config.get("requires_approval", False),
                timeout_minutes=config.get("timeout_minutes", 10),
                is_custom=True,
            )

            loop = asyncio.get_event_loop()
            future = asyncio.run_coroutine_threadsafe(
                bot_manager.create_custom_bot(new_config), loop
            )
            result = future.result(timeout=30)
            return json.dumps({"action": "create", "bot_name": bot_name, **result})

        return json.dumps({"error": "Unhandled action"})
    except Exception as e:
        logger.error("manage_bot error: %s", e)
        return json.dumps({"error": f"Bot management failed: {e}"})


# ──────────────────────────────────────────────────────────────
#  JOURNAL ENTRY TOOL
# ──────────────────────────────────────────────────────────────


@tool
async def add_journal_entry(
    title: str,
    content: str,
    entry_type: str = "note",
    agent: str = "",
    priority: str = "medium",
    tags: str = "[]",
) -> str:
    """Write a journal entry to the Inbox/Journal page. Use this to record insights,
    recommendations, action items, or daily summaries that the user should see.

    Any agent or bot can call this tool to post standalone notes, insights, and
    recommendations that appear in the user's Journal tab.

    Args:
        title: A short, descriptive title for the entry.
        content: The full content in markdown format.
        entry_type: Type of entry — "insight", "recommendation", "summary", "note", or "action_item".
        agent: The name of the agent or bot creating this entry.
        priority: Priority level — "low", "medium", or "high".
        tags: JSON array of tag strings (e.g. '["interview", "amazon"]').

    Returns:
        JSON with saved status and entry_id.
    """
    valid_types = ("insight", "recommendation", "summary", "note", "action_item")
    if entry_type not in valid_types:
        return json.dumps({"error": f"Invalid entry_type. Must be one of: {', '.join(valid_types)}"})

    valid_priorities = ("low", "medium", "high")
    if priority not in valid_priorities:
        return json.dumps({"error": f"Invalid priority. Must be one of: {', '.join(valid_priorities)}"})

    try:
        try:
            tags_parsed = json.loads(tags) if isinstance(tags, str) else tags
            if not isinstance(tags_parsed, list):
                tags_parsed = []
        except json.JSONDecodeError:
            tags_parsed = []

        from app.db import create_journal_entry
        entry_id = await create_journal_entry(
            title=title[:500],
            content=content[:10000],
            entry_type=entry_type,
            agent=agent[:100] if agent else None,
            priority=priority,
            tags=tags_parsed,
        )

        return json.dumps({
            "saved": True,
            "entry_id": entry_id,
            "entry_type": entry_type,
            "title": title,
            "message": f"Journal entry '{title}' saved (id={entry_id})",
        })
    except Exception as e:
        logger.error("add_journal_entry error: %s", e)
        return json.dumps({"error": f"Failed to save journal entry: {e}"})


# ──────────────────────────────────────────────────────────────
#  TOOL COLLECTIONS (for binding to agents)
# ──────────────────────────────────────────────────────────────

JOB_INTAKE_TOOLS = [search_jobs, review_resume, extract_resume_profile, get_saved_jobs, web_search]
RESUME_TAILOR_TOOLS = [review_resume, extract_resume_profile]
RECRUITER_CHAT_TOOLS = [review_resume, search_jobs, web_search]
INTERVIEW_PREP_TOOLS = [review_resume, extract_resume_profile, search_jobs, web_search]
LEETCODE_COACH_TOOLS = [get_leetcode_progress, select_leetcode_problems, log_leetcode_attempt_tool, web_search]

ALL_TOOLS = [
    review_resume,
    extract_resume_profile,
    search_jobs,
    search_jobs_for_resume,
    get_saved_jobs,
    get_search_history,
    get_user_job_interests,
    prepare_job_application,
    generate_cover_letter,
    get_job_pipeline,
    update_job_pipeline_stage,
    get_leetcode_progress,
    select_leetcode_problems,
    log_leetcode_attempt_tool,
    web_search,
    send_notification,
    call_webhook,
    save_job,
    add_job_note,
    generate_prep_materials,
    manage_bot,
    add_journal_entry,
]


# ──────────────────────────────────────────────────────────────
#  SWARM TOOL — request_agent_help
# ──────────────────────────────────────────────────────────────

import threading

# Thread-safe pending list — LangChain tools run synchronously in thread executor,
# so we use a threading.Lock instead of asyncio primitives. The swarm orchestrator
# drains this list after each agent finishes.
_request_agent_help_lock = threading.Lock()
_request_agent_help_pending: list[dict] = []


@tool
def request_agent_help(agent_name: str, task: str, urgency: str = "normal") -> str:
    """Pull another agent into the debate to challenge, fact-check, or expand on a topic.

    Use this when:
    - You think someone's advice needs to be challenged or fact-checked by a specialist
    - A critical angle is missing and another agent has the expertise to cover it
    - You need real data to back up or counter a claim in the thread
    - The user needs a perspective that's outside your expertise

    Be SPECIFIC about the task — frame it as a debate challenge, not a generic request.

    GOOD examples:
    - request_agent_help("salary_tracker", "Fact-check the salary ranges mentioned — pull real L5 comp data from levels.fyi for this market")
    - request_agent_help("daily_coach", "Nobody has addressed the emotional side of this layoff. The user needs support, not just tactics.")
    - request_agent_help("network_mapper", "Challenge my advice to just apply online — find warm connections at these companies instead")

    BAD examples:
    - request_agent_help("salary_tracker", "help with salary")  # too vague
    - request_agent_help("daily_coach", "say something nice")   # not a real task

    Args:
        agent_name: The agent to call (e.g. "salary_tracker", "interview_prep", "daily_coach").
        task: A specific debate challenge — what to fact-check, counter, or add.
        urgency: Priority level — "high", "normal", or "low". Default: "normal".

    Returns:
        JSON confirming the agent has been called into the debate.
    """
    valid_urgencies = ("high", "normal", "low")
    if urgency not in valid_urgencies:
        urgency = "normal"

    # Validate agent_name against known personalities
    try:
        from app.thought_engine import get_all_personalities
        known = get_all_personalities()
        if agent_name not in known:
            # Try normalizing
            normalized = agent_name.strip().lower().replace(" ", "_")
            if normalized not in known:
                available = ", ".join(sorted(known.keys()))
                return json.dumps({
                    "success": False,
                    "error": f"Unknown agent '{agent_name}'. Available: {available}",
                })
            agent_name = normalized

        personality = known[agent_name]
        display_name = personality.get("display_name", agent_name)
        expertise = personality.get("bio", "")
    except Exception:
        display_name = agent_name.replace("_", " ").title()
        expertise = ""

    request = {
        "agent_name": agent_name,
        "task": task,
        "urgency": urgency,
    }

    with _request_agent_help_lock:
        _request_agent_help_pending.append(request)

    return json.dumps({
        "success": True,
        "agent_name": agent_name,
        "display_name": display_name,
        "expertise": expertise,
        "message": f"{display_name} has been called into the debate. They'll respond to: {task}",
    })


def drain_pending_agent_requests() -> list[dict]:
    """Drain and return all pending agent help requests (called by orchestrator)."""
    with _request_agent_help_lock:
        pending = list(_request_agent_help_pending)
        _request_agent_help_pending.clear()
    return pending


# ──────────────────────────────────────────────────────────────
#  BUILDER TOOL — dispatch_builder
# ──────────────────────────────────────────────────────────────

_dispatch_builder_lock = threading.Lock()
_dispatch_builder_pending: list[dict] = []


@tool
def dispatch_builder(title: str, description: str, sections: str = "[]") -> str:
    """Dispatch a background builder to create a rich tutorial on the Prep page.

    The builder runs asynchronously — you'll see progress in the thread.
    Use this when you want to create detailed learning materials:
    tutorials, problem sets, study guides, visual walkthroughs.

    Args:
        title: Tutorial title (e.g. "Core Tree Patterns Visual Walkthrough")
        description: What the tutorial should cover — be specific about structure
        sections: JSON array of section headings to include (e.g. '["Intro", "DFS vs BFS", "Practice"]')

    Returns:
        JSON confirming the builder has been dispatched.
    """
    request = {
        "title": title,
        "description": description,
        "sections": sections,
    }

    with _dispatch_builder_lock:
        _dispatch_builder_pending.append(request)

    return json.dumps({
        "success": True,
        "title": title,
        "message": f"Builder dispatched for '{title}'. It will generate a rich tutorial and save it to the Prep page. Progress will appear in the thread.",
    })


def drain_pending_builder_dispatches() -> list[dict]:
    """Drain and return all pending builder dispatch requests (called by orchestrator)."""
    with _dispatch_builder_lock:
        pending = list(_dispatch_builder_pending)
        _dispatch_builder_pending.clear()
    return pending


# ──────────────────────────────────────────────────────────────
#  GROUP CHAT TOOLS
# ──────────────────────────────────────────────────────────────

# Context variable to track the current group chat (set by orchestrator)
_current_group_chat_id: int | None = None
_current_group_chat_lock = threading.Lock()


def set_current_group_chat(chat_id: int | None) -> None:
    """Set the current group chat context (called by orchestrator)."""
    global _current_group_chat_id
    with _current_group_chat_lock:
        _current_group_chat_id = chat_id


def get_current_group_chat() -> int | None:
    """Get the current group chat ID."""
    with _current_group_chat_lock:
        return _current_group_chat_id


@tool
def tag_agent_in_chat(
    agent_name: str,
    message: str,
    challenge_type: str = "question",
) -> str:
    """Tag another agent in the current group chat to get their input.

    Use this when you want to:
    - Ask a specific agent a question
    - Challenge their previous statement
    - Request they verify/research something
    - Signal agreement or disagreement with their position

    The tagged agent will respond in the next turn.

    Args:
        agent_name: The agent to tag (e.g. "market_intel", "researcher", "tech_analyst")
        message: Your message directed at that agent
        challenge_type: Type of engagement — "question", "challenge", "request", "agree", "disagree"

    Returns:
        Confirmation that the agent has been tagged for the next turn.
    """
    valid_types = ("question", "challenge", "request", "agree", "disagree")
    if challenge_type not in valid_types:
        challenge_type = "question"

    group_chat_id = get_current_group_chat()

    # Validate agent_name against known personalities AND dynamic agents
    normalized = agent_name.strip().lower().replace(" ", "_").replace("-", "")
    display_name = None

    # Check dynamic agents first (they're spawned at runtime)
    try:
        from app.group_chat.dynamic_agents import get_dynamic_agent
        dynamic = get_dynamic_agent(normalized)
        if dynamic:
            agent_name = normalized
            display_name = dynamic.display_name
    except Exception:
        pass

    # If not a dynamic agent, check static personalities
    if not display_name:
        try:
            from app.thought_engine import get_all_personalities
            known = get_all_personalities()
            if normalized in known:
                agent_name = normalized
                personality = known[normalized]
                display_name = personality.get("display_name", agent_name)
            elif agent_name in known:
                personality = known[agent_name]
                display_name = personality.get("display_name", agent_name)
            else:
                # Collect all available agents (static + dynamic)
                from app.group_chat.dynamic_agents import list_dynamic_agents
                dynamic_names = [d.name for d in list_dynamic_agents(group_chat_id)]
                all_available = sorted(set(known.keys()) | set(dynamic_names))
                return json.dumps({
                    "success": False,
                    "error": f"Unknown agent '{agent_name}'. Available: {', '.join(all_available)}",
                })
        except Exception:
            display_name = agent_name.replace("_", " ").title()

    return json.dumps({
        "success": True,
        "agent_name": agent_name,
        "display_name": display_name,
        "challenge_type": challenge_type,
        "group_chat_id": group_chat_id,
        "message": f"@{agent_name} has been tagged ({challenge_type}). They'll respond to: {message[:100]}...",
    })


@tool
def spawn_agent(
    agent_name: str,
    role: str = "",
    expertise: str = "",
    responsibilities: str = "",
    reason: str = "",
) -> str:
    """Spawn a new specialized agent to join the current group discussion.

    Use this when the discussion needs expertise that no current participant has.
    The new agent will be created dynamically and join the conversation.

    Examples of agents you can spawn:
    - "NASAAdvisor" - Space systems expert with NASA background
    - "MITProfessor" - Academic expert for theoretical analysis
    - "SystemsEngineer" - Practical implementation specialist
    - "RadiationEngineer" - Specialist for radiation hardening
    - "ProcurementSpecialist" - Expert on vendors and pricing
    - "BusinessAnalyst" - ROI and market analysis expert

    The agent's expertise is inferred from their name, but you can customize:

    Args:
        agent_name: Name of the agent (e.g., "NASAAdvisor", "MITProfessor").
                   Name format determines their role: suffix like "Advisor",
                   "Engineer", "Professor" sets behavior. Prefix like "NASA",
                   "MIT" sets domain expertise.
        role: Optional custom role title (e.g., "Radiation Hardening Specialist")
        expertise: Optional comma-separated expertise areas to add
        responsibilities: Optional specific responsibilities for this discussion
        reason: Why this agent is needed (helps them contribute effectively)

    Returns:
        Confirmation that the agent has been spawned and will participate.
    """
    from app.group_chat.dynamic_agents import (
        DynamicAgentFactory,
        register_dynamic_agent,
        get_dynamic_agent,
    )

    group_chat_id = get_current_group_chat()
    current_agent = _get_current_agent()

    # Clean the name
    clean_name = re.sub(r"[^a-zA-Z0-9]", "", agent_name)
    if not clean_name:
        return json.dumps({
            "success": False,
            "error": "Invalid agent name. Use names like 'NASAAdvisor' or 'SystemsEngineer'.",
        })

    # Check if already exists
    existing = get_dynamic_agent(clean_name)
    if existing:
        return json.dumps({
            "success": True,
            "agent_name": clean_name.lower(),
            "display_name": existing.display_name,
            "status": "already_exists",
            "message": f"{existing.display_name} is already in the discussion.",
        })

    # Get topic from context
    topic = _get_current_topic() or "general discussion"

    try:
        # Create the dynamic agent using the factory
        # This allows ANY agent to be spawned based on name parsing
        # e.g., "NASAAdvisor", "RadiationSpecialist", "QuantumPhysicist"
        dynamic_agent = DynamicAgentFactory.create_from_mention(
            name=clean_name,
            topic=topic,
            spawned_by=current_agent or "system",
            spawn_reason=reason,
            group_chat_id=group_chat_id,
        )

        # Apply customizations if provided
        if role:
            dynamic_agent.role = role
        if expertise:
            extra_expertise = [e.strip() for e in expertise.split(",")]
            dynamic_agent.expertise.extend(extra_expertise)
        if responsibilities:
            dynamic_agent.responsibilities = responsibilities

        # Register the agent in memory
        # The orchestrator's parse_mentions will add them to DB when @mentioned
        register_dynamic_agent(dynamic_agent)

        logger.info(
            "Dynamic agent spawned: %s (%s) for chat %d by %s",
            dynamic_agent.display_name, dynamic_agent.role, group_chat_id or 0, current_agent
        )

        return json.dumps({
            "success": True,
            "agent_name": dynamic_agent.name,
            "display_name": dynamic_agent.display_name,
            "role": dynamic_agent.role,
            "domain": dynamic_agent.domain,
            "expertise": dynamic_agent.expertise[:5],
            "spawned_by": current_agent,
            "group_chat_id": group_chat_id,
            "status": "spawned",
            "instructions": f"IMPORTANT: To bring {dynamic_agent.display_name} into the discussion, "
                           f"you MUST mention them with @{dynamic_agent.name} in your response. "
                           f"They will then join and contribute their {dynamic_agent.role} expertise.",
        })

    except Exception as e:
        logger.error("Failed to spawn agent %s: %s", agent_name, e)
        return json.dumps({
            "success": False,
            "error": f"Failed to spawn agent: {str(e)}",
        })


# Context helpers for spawn_agent
_current_topic: str = ""
_current_agent: str = ""


def set_current_context(topic: str = "", agent: str = "") -> None:
    """Set the current execution context for tools."""
    global _current_topic, _current_agent
    if topic:
        _current_topic = topic
    if agent:
        _current_agent = agent


def _get_current_topic() -> str:
    return _current_topic


def _get_current_agent() -> str:
    return _current_agent


@tool
async def propose_prompt_change(
    field: str,
    new_value: str,
    rationale: str,
) -> str:
    """Propose a change to your own system prompt based on learnings.

    Use this when you've discovered something that should permanently
    change how you operate. Changes are applied immediately (autonomous mode).

    Args:
        field: What to change — "prompt", "tools", "temperature", "quality_criteria", "description"
        new_value: The proposed new value (for prompt, this will be appended; for lists, provide JSON)
        rationale: Why this change will improve your performance (be specific)

    Returns:
        Proposal ID, status, and whether it was auto-applied.
    """
    valid_fields = ("prompt", "tools", "temperature", "quality_criteria", "description", "max_tokens")
    if field not in valid_fields:
        return json.dumps({
            "success": False,
            "error": f"Invalid field. Must be one of: {', '.join(valid_fields)}",
        })

    # Get the calling agent's name from context
    # (This is typically set by the orchestrator before invoking the tool)
    agent_name = "unknown"
    try:
        import inspect
        frame = inspect.currentframe()
        # Try to get agent name from call context
        if frame and frame.f_back and frame.f_back.f_locals:
            agent_name = frame.f_back.f_locals.get("agent", "unknown")
    except Exception:
        pass

    group_chat_id = get_current_group_chat()

    try:
        from app.group_chat.prompt_evolution import create_and_apply_proposal
        result = await create_and_apply_proposal(
            agent=agent_name,
            field=field,
            new_value=new_value,
            rationale=rationale,
            group_chat_id=group_chat_id,
            user_id=_uid(),
        )

        return json.dumps({
            "success": True,
            **result,
            "message": f"Prompt change proposal created and auto-applied for field '{field}'.",
        })

    except Exception as e:
        logger.error("propose_prompt_change error: %s", e)
        return json.dumps({
            "success": False,
            "error": str(e),
        })


@tool
async def start_group_chat(
    topic: str,
    initial_message: str,
    suggested_participants: str,
    urgency: str = "normal",
) -> str:
    """Start a group discussion when you discover something worth debating.

    Use this when:
    - You've found conflicting information that needs multiple perspectives
    - A topic requires expertise from several domains
    - You want to brainstorm or research a complex question
    - A significant insight warrants group deliberation

    Args:
        topic: The discussion topic (e.g. "emerging battery technology for EV products")
        initial_message: Your opening message to kick off the discussion
        suggested_participants: JSON array of agent names to invite (e.g. '["researcher", "market_intel"]')
        urgency: Priority level — "high", "normal", or "low". Default: "normal".

    Returns:
        JSON with the new group chat ID and status.
    """
    valid_urgencies = ("high", "normal", "low")
    if urgency not in valid_urgencies:
        urgency = "normal"

    try:
        participants = json.loads(suggested_participants) if isinstance(suggested_participants, str) else suggested_participants
        if not isinstance(participants, list) or len(participants) < 1:
            return json.dumps({
                "success": False,
                "error": "suggested_participants must be a JSON array with at least 1 agent",
            })
    except json.JSONDecodeError:
        return json.dumps({
            "success": False,
            "error": "suggested_participants must be valid JSON array",
        })

    # Validate participants against known agents
    try:
        from app.thought_engine import get_all_personalities
        known = get_all_personalities()
        validated_participants = []
        for p in participants:
            if p in known:
                validated_participants.append(p)
            else:
                normalized = p.strip().lower().replace(" ", "_")
                if normalized in known:
                    validated_participants.append(normalized)

        if len(validated_participants) < 1:
            available = ", ".join(sorted(known.keys()))
            return json.dumps({
                "success": False,
                "error": f"No valid participants found. Available agents: {available}",
            })

        participants = validated_participants
    except Exception as e:
        logger.warning("Could not validate participants: %s", e)

    # Determine initiator (the calling agent)
    initiator = "agent"
    try:
        import inspect
        frame = inspect.currentframe()
        if frame and frame.f_back and frame.f_back.f_locals:
            initiator = frame.f_back.f_locals.get("agent", "agent")
    except Exception:
        pass

    # Add initiator to participants if not already included
    if initiator not in participants and initiator != "agent":
        participants.insert(0, initiator)

    try:
        from app.db import create_group_chat, create_timeline_post
        from app.group_chat.orchestrator import start_orchestrator
        from app.group_chat.controls import GroupChatConfig

        user_id = _uid()

        # Create config based on urgency
        config = GroupChatConfig()
        if urgency == "high":
            config.max_turns = 30
            config.turn_timeout_seconds = 20
        elif urgency == "low":
            config.max_turns = 15
            config.turn_timeout_seconds = 45

        # Create the group chat
        chat_id = await create_group_chat(
            topic=topic,
            participants=participants,
            initiator=initiator,
            config={
                "max_turns": config.max_turns,
                "max_tokens": config.max_tokens,
                "turn_mode": config.turn_mode,
                "urgency": urgency,
            },
            user_id=user_id,
        )

        # Create initial timeline post
        await create_timeline_post(
            agent=initiator,
            post_type="group_chat_start",
            content=initial_message,
            context={
                "group_chat_id": chat_id,
                "topic": topic,
                "participants": participants,
            },
            user_id=user_id,
        )

        # Start the orchestrator (runs in background)
        await start_orchestrator(chat_id, config)

        return json.dumps({
            "success": True,
            "group_chat_id": chat_id,
            "topic": topic,
            "participants": participants,
            "urgency": urgency,
            "message": f"Group chat started on '{topic}' with {len(participants)} participants.",
        })

    except Exception as e:
        logger.error("start_group_chat error: %s", e)
        return json.dumps({
            "success": False,
            "error": str(e),
        })


# ═══════════════════════════════════════════════════════════════════════════════
# WORKSPACE COLLABORATION TOOLS
# ═══════════════════════════════════════════════════════════════════════════════


@tool
def read_workspace() -> str:
    """Read the current state of the shared workspace.

    Use this to see:
    - The main goal and sub-goals
    - Available tasks you can claim
    - Tasks currently being worked on
    - Findings from other agents
    - Pending decisions that need votes

    Returns:
        A summary of the workspace state including tasks, findings, and decisions.
    """
    from app.group_chat.workspace import get_workspace

    group_chat_id = get_current_group_chat()
    if not group_chat_id:
        return json.dumps({
            "success": False,
            "error": "No active group chat context",
        })

    workspace = get_workspace(group_chat_id)
    if not workspace:
        return json.dumps({
            "success": False,
            "error": "No workspace found for this chat",
        })

    return json.dumps({
        "success": True,
        "summary": workspace.get_summary(),
        "available_tasks": [t.to_dict() for t in workspace.get_available_tasks()],
        "recent_findings": [f.to_dict() for f in list(workspace.findings.values())[-5:]],
        "pending_decisions": [d.to_dict() for d in workspace.get_pending_decisions()],
        "approved_decisions": [d.to_dict() for d in workspace.get_approved_decisions()],
    })


@tool
def add_finding(
    content: str,
    category: str = "insight",
    confidence: float = 0.7,
    tags: str = "",
) -> str:
    """Add a finding, insight, or piece of research to the shared workspace.

    Use this when you've discovered something valuable that other agents should know:
    - Research results from web searches
    - Key insights or conclusions
    - Important data points
    - Recommendations

    Args:
        content: The finding content (what you discovered or concluded)
        category: Type of finding - "research", "insight", "data", "recommendation"
        confidence: How confident you are (0.0-1.0), default 0.7
        tags: Comma-separated tags for categorization

    Returns:
        Confirmation with finding ID that others can reference.
    """
    from app.group_chat.workspace import get_workspace

    group_chat_id = get_current_group_chat()
    current_agent = _get_current_agent()

    if not group_chat_id:
        return json.dumps({"success": False, "error": "No active group chat"})

    workspace = get_workspace(group_chat_id)
    if not workspace:
        return json.dumps({"success": False, "error": "No workspace found"})

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    result = workspace.add_finding(
        content=content,
        source_agent=current_agent or "unknown",
        category=category,
        confidence=confidence,
        tags=tag_list,
    )

    # Handle duplicate rejection
    if isinstance(result, tuple):
        success, message = result
        return json.dumps({
            "success": False,
            "error": "DUPLICATE_REJECTED",
            "message": message,
            "instruction": "Reference the existing finding instead of restating it. Add NEW information only.",
        })

    # Success - finding was added
    return json.dumps({
        "success": True,
        "finding_id": result.id,
        "message": f"Finding recorded. Other agents can reference it as {result.id}.",
    })


@tool
def claim_task(task_id: str) -> str:
    """Claim a task from the workspace to work on.

    Check available tasks with read_workspace first, then claim one that
    matches your expertise. Only claim tasks you can actually complete.

    Args:
        task_id: The ID of the task to claim (e.g., "task_1")

    Returns:
        Success/failure message with task details.
    """
    from app.group_chat.workspace import get_workspace

    group_chat_id = get_current_group_chat()
    current_agent = _get_current_agent()

    if not group_chat_id:
        return json.dumps({"success": False, "error": "No active group chat"})

    workspace = get_workspace(group_chat_id)
    if not workspace:
        return json.dumps({"success": False, "error": "No workspace found"})

    success, message = workspace.claim_task(task_id, current_agent or "unknown")

    if success:
        task = workspace.tasks.get(task_id)
        return json.dumps({
            "success": True,
            "message": message,
            "task": task.to_dict() if task else None,
            "instructions": "Work on this task and call complete_task when done.",
        })
    else:
        return json.dumps({"success": False, "error": message})


@tool
def complete_task(task_id: str, result: str) -> str:
    """Mark a task as completed with your result.

    Call this after you've finished working on a claimed task.
    Provide a clear result that others can build upon.

    Args:
        task_id: The ID of the task you completed
        result: The outcome/result of your work (be specific and useful)

    Returns:
        Confirmation that the task is marked complete.
    """
    from app.group_chat.workspace import get_workspace

    group_chat_id = get_current_group_chat()
    current_agent = _get_current_agent()

    if not group_chat_id:
        return json.dumps({"success": False, "error": "No active group chat"})

    workspace = get_workspace(group_chat_id)
    if not workspace:
        return json.dumps({"success": False, "error": "No workspace found"})

    success, message = workspace.complete_task(task_id, current_agent or "unknown", result)

    return json.dumps({
        "success": success,
        "message": message if success else None,
        "error": message if not success else None,
    })


@tool
def propose_decision(
    title: str,
    description: str,
    rationale: str = "",
) -> str:
    """Propose a decision for the group to vote on.

    Use this when you've reached a conclusion that needs group consensus:
    - "Use approach X over approach Y"
    - "Recommend product Z for this use case"
    - "Focus on priority A before priority B"

    Other agents will vote, and the decision is approved when majority agrees.

    Args:
        title: Short title for the decision (e.g., "Use Redis for caching")
        description: Detailed description of what you're proposing
        rationale: Why you're proposing this (evidence, reasoning)

    Returns:
        Decision ID that others can vote on.
    """
    from app.group_chat.workspace import get_workspace

    group_chat_id = get_current_group_chat()
    current_agent = _get_current_agent()

    if not group_chat_id:
        return json.dumps({"success": False, "error": "No active group chat"})

    workspace = get_workspace(group_chat_id)
    if not workspace:
        return json.dumps({"success": False, "error": "No workspace found"})

    decision = workspace.propose_decision(
        title=title,
        description=description,
        proposed_by=current_agent or "unknown",
        rationale=rationale,
    )

    return json.dumps({
        "success": True,
        "decision_id": decision.id,
        "message": f"Decision proposed: {title}. Other agents can vote with vote_on_decision.",
        "current_votes": {
            "for": decision.votes_for,
            "against": decision.votes_against,
        },
    })


@tool
def vote_on_decision(
    decision_id: str,
    vote: bool,
    reason: str = "",
) -> str:
    """Vote on a proposed decision.

    Check pending decisions with read_workspace, then vote based on your
    expertise and perspective.

    Args:
        decision_id: The ID of the decision (e.g., "decision_1")
        vote: True to support, False to oppose
        reason: Optional explanation for your vote

    Returns:
        Updated vote counts and whether decision was resolved.
    """
    from app.group_chat.workspace import get_workspace

    group_chat_id = get_current_group_chat()
    current_agent = _get_current_agent()

    if not group_chat_id:
        return json.dumps({"success": False, "error": "No active group chat"})

    workspace = get_workspace(group_chat_id)
    if not workspace:
        return json.dumps({"success": False, "error": "No workspace found"})

    success, message = workspace.vote_on_decision(
        decision_id=decision_id,
        agent=current_agent or "unknown",
        vote=vote,
        reason=reason,
    )

    if success:
        decision = workspace.decisions.get(decision_id)
        return json.dumps({
            "success": True,
            "message": message,
            "current_votes": {
                "for": decision.votes_for if decision else [],
                "against": decision.votes_against if decision else [],
            },
            "status": decision.status.value if decision else "unknown",
        })
    else:
        return json.dumps({"success": False, "error": message})


@tool
def create_task(
    title: str,
    description: str,
) -> str:
    """Create a new task in the workspace for the team.

    Use this when you identify work that needs to be done but you're not
    the right agent to do it, or when breaking down a complex problem.

    Args:
        title: Short task title
        description: What needs to be done (be specific)

    Returns:
        Task ID that agents can claim.
    """
    from app.group_chat.workspace import get_workspace

    group_chat_id = get_current_group_chat()
    current_agent = _get_current_agent()

    if not group_chat_id:
        return json.dumps({"success": False, "error": "No active group chat"})

    workspace = get_workspace(group_chat_id)
    if not workspace:
        return json.dumps({"success": False, "error": "No workspace found"})

    task = workspace.create_task(
        title=title,
        description=description,
        created_by=current_agent or "unknown",
    )

    return json.dumps({
        "success": True,
        "task_id": task.id,
        "message": f"Task created: {title}. Agents can claim it with claim_task.",
    })


# Registry for config-driven tool resolution (name → tool object)
TOOL_REGISTRY: dict[str, object] = {
    "review_resume": review_resume,
    "extract_resume_profile": extract_resume_profile,
    "search_jobs": search_jobs,
    "search_jobs_for_resume": search_jobs_for_resume,
    "get_saved_jobs": get_saved_jobs,
    "prepare_job_application": prepare_job_application,
    "generate_cover_letter": generate_cover_letter,
    "get_job_pipeline": get_job_pipeline,
    "update_job_stage": update_job_stage,
    "get_leetcode_progress": get_leetcode_progress,
    "select_leetcode_problems": select_leetcode_problems,
    "log_leetcode_attempt_tool": log_leetcode_attempt_tool,
    "web_search": web_search,
    "get_search_history": get_search_history,
    "get_user_job_interests": get_user_job_interests,
    "send_notification": send_notification,
    "call_webhook": call_webhook,
    "save_job": save_job,
    "add_job_note": add_job_note,
    "generate_prep_materials": generate_prep_materials,
    "manage_bot": manage_bot,
    "add_journal_entry": add_journal_entry,
    "request_agent_help": request_agent_help,
    "dispatch_builder": dispatch_builder,
    "tag_agent_in_chat": tag_agent_in_chat,
    "spawn_agent": spawn_agent,
    "propose_prompt_change": propose_prompt_change,
    "start_group_chat": start_group_chat,
    # Workspace collaboration tools
    "read_workspace": read_workspace,
    "add_finding": add_finding,
    "claim_task": claim_task,
    "complete_task": complete_task,
    "propose_decision": propose_decision,
    "vote_on_decision": vote_on_decision,
    "create_task": create_task,
}

ALL_TOOLS.append(request_agent_help)
ALL_TOOLS.append(dispatch_builder)
ALL_TOOLS.append(tag_agent_in_chat)
ALL_TOOLS.append(spawn_agent)
ALL_TOOLS.append(propose_prompt_change)
ALL_TOOLS.append(start_group_chat)
# Workspace collaboration tools
ALL_TOOLS.append(read_workspace)
ALL_TOOLS.append(add_finding)
ALL_TOOLS.append(claim_task)
ALL_TOOLS.append(complete_task)
ALL_TOOLS.append(propose_decision)
ALL_TOOLS.append(vote_on_decision)
ALL_TOOLS.append(create_task)
