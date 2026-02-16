"""Application tools: prepare job applications, generate cover letters."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from app.resume_store import get_resume, list_resumes

from .shared import _uid

logger = logging.getLogger(__name__)


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
