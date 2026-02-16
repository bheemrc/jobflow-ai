"""Journal entries endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.db import get_journal_entries, mark_journal_read, pin_journal_entry, delete_journal_entry
from app.user_context import get_user_id

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("")
async def list_journal(
    entry_type: str | None = None,
    is_read: str | None = None,
    limit: int = 50,
    user_id: str = Depends(get_user_id),
):
    """List journal entries with optional filters."""
    read_filter = None
    if is_read is not None:
        read_filter = is_read.lower() in ("true", "1", "yes")
    entries = await get_journal_entries(
        entry_type=entry_type, is_read=read_filter, limit=limit, user_id=user_id,
    )
    return {"entries": entries}


@router.patch("/{entry_id}/read")
async def mark_journal_read_endpoint(entry_id: int, user_id: str = Depends(get_user_id)):
    """Mark a journal entry as read."""
    await mark_journal_read(entry_id)
    return {"ok": True}


@router.patch("/{entry_id}/pin")
async def pin_journal_entry_endpoint(entry_id: int, request: Request, user_id: str = Depends(get_user_id)):
    """Toggle pin on a journal entry."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    pinned = body.get("pinned", True)
    await pin_journal_entry(entry_id, pinned)
    return {"ok": True, "pinned": pinned}


@router.delete("/{entry_id}")
async def delete_journal_entry_endpoint(entry_id: int, user_id: str = Depends(get_user_id)):
    """Delete a journal entry."""
    await delete_journal_entry(entry_id)
    return {"ok": True}
