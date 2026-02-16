"""Job management tools: save jobs, update stages, add notes, pipeline operations."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from app.db import get_conn

logger = logging.getLogger(__name__)


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
