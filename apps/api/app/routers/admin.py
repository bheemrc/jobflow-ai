"""Admin endpoints for system configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.user_context import get_user_id

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reload-config")
async def reload_config_endpoint(user_id: str = Depends(get_user_id)):
    """Hot-reload bot configuration from bots.yaml."""
    from app.group_chat.reload import reload_bot_config
    result = await reload_bot_config()
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Reload failed"))
    return result
