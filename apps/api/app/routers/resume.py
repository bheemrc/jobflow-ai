"""Resume management endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.models import ResumeUploadRequest, ResumeResponse
from app.resume_store import save_resume, get_resume, delete_resume, list_resumes
from app.user_context import get_user_id

router = APIRouter(tags=["resume"])


@router.post("/resume/upload", response_model=ResumeResponse)
async def upload_resume(request: ResumeUploadRequest, user_id: str = Depends(get_user_id)):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Resume text cannot be empty")
    resume_id = await save_resume(request.text, user_id, request.resume_id)

    # Record resume upload in dossier (non-blocking)
    try:
        from app.dna.dossier import record_user_action
        asyncio.create_task(record_user_action("upload_resume", {"filename": request.resume_id or "resume"}, user_id=user_id))
    except Exception:
        pass

    return ResumeResponse(resume_id=resume_id)


@router.get("/resume/{resume_id}", response_model=ResumeResponse)
async def get_resume_endpoint(resume_id: str, user_id: str = Depends(get_user_id)):
    text = await get_resume(resume_id, user_id)
    if text is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    return ResumeResponse(resume_id=resume_id, text=text)


@router.delete("/resume/{resume_id}")
async def delete_resume_endpoint(resume_id: str, user_id: str = Depends(get_user_id)):
    if not await delete_resume(resume_id, user_id):
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"ok": True}


@router.get("/resumes")
async def list_resumes_endpoint(user_id: str = Depends(get_user_id)):
    return {"resumes": await list_resumes(user_id)}
