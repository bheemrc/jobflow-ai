"""Job pipeline queries."""

from __future__ import annotations

from .core import get_conn


async def get_jobs_pipeline(user_id: str = "") -> dict:
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT * FROM saved_jobs WHERE user_id = $1 ORDER BY saved_at DESC
        """, user_id)
        pipeline: dict[str, list] = {
            "saved": [], "applied": [], "interview": [], "offer": [], "rejected": []
        }
        for r in rows:
            job = dict(r)
            stage = job.get("status", "saved")
            if stage in pipeline:
                pipeline[stage].append(job)
            else:
                pipeline["saved"].append(job)
        return pipeline


async def update_job_stage(job_id: int, new_status: str, user_id: str = "") -> None:
    async with get_conn() as conn:
        await conn.execute("""
            UPDATE saved_jobs SET status = $1, updated_at = NOW() WHERE id = $2 AND user_id = $3
        """, new_status, job_id, user_id)
