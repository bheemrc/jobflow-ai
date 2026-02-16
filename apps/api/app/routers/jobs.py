"""Job pipeline endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request

from app.db import get_jobs_pipeline, update_job_stage as db_update_job_stage, log_activity
from app.models import JobStageUpdate
from app.user_context import get_user_id
from app.bot_manager import bot_manager

router = APIRouter(tags=["jobs"])


@router.get("/jobs/pipeline")
async def jobs_pipeline(user_id: str = Depends(get_user_id)):
    """Get jobs grouped by pipeline stage."""
    pipeline = await get_jobs_pipeline(user_id=user_id)
    # Serialize datetime fields
    for stage, jobs in pipeline.items():
        for job in jobs:
            for key in ("saved_at", "updated_at"):
                if key in job and hasattr(job[key], "isoformat"):
                    job[key] = job[key].isoformat()
    return pipeline


@router.post("/api/v1/jobs/search")
async def search_jobs_endpoint(request: Request, user_id: str = Depends(get_user_id)):
    """Search for jobs using JSearch (RapidAPI)."""
    body = await request.json()
    from app.jsearch import jsearch
    jobs = await asyncio.to_thread(
        jsearch,
        search_term=body.get("search_term", ""),
        location=body.get("location"),
        site_name=body.get("site_name"),
        results_wanted=body.get("results_wanted", 20),
        is_remote=body.get("is_remote", False),
        hours_old=body.get("hours_old"),
    )

    # Record search action in dossier (non-blocking)
    try:
        from app.dna.dossier import record_user_action
        asyncio.create_task(record_user_action("search", {"query": body.get("search_term", "")}, user_id=user_id))
    except Exception:
        pass

    return {"jobs": jobs}


@router.patch("/jobs/{job_id}/stage")
async def update_job_stage_endpoint(job_id: int, body: JobStageUpdate, user_id: str = Depends(get_user_id)):
    """Move a job to a new pipeline stage."""
    await db_update_job_stage(job_id, body.status, user_id=user_id)
    await log_activity("system", "Job stage changed", f"Job {job_id} → {body.status}")

    # Emit event for bot triggers + thought engine
    event_name = f"stage_{body.status}"
    await bot_manager.handle_event(event_name, {"job_id": job_id, "stage": body.status})

    return {"ok": True, "job_id": job_id, "status": body.status}
