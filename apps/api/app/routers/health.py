"""Health and config endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.flow_config import read_flows_yaml, reload_config, save_flows_yaml
from app.graph import create_compiled_graph
from app.config import settings
from app.models import FlowConfigUpdate, BotsConfigUpdate
from app.user_context import get_user_id
from .shared import set_graph, get_graph

import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health", "config"])


@router.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0", "engine": "langgraph"}


@router.get("/config/flows")
async def get_flow_config_endpoint(user_id: str = Depends(get_user_id)):
    """Return current YAML config text."""
    return {"yaml": read_flows_yaml()}


@router.put("/config/flows")
async def update_flow_config(body: FlowConfigUpdate, user_id: str = Depends(get_user_id)):
    """Validate YAML, rebuild graph, hot-swap. Takes effect on next request."""
    try:
        new_config = reload_config(body.yaml_text)
        new_graph = await create_compiled_graph(settings.postgres_url, flow_config=new_config)
        set_graph(new_graph)  # atomic pointer swap
        save_flows_yaml(body.yaml_text)
        return {"ok": True, "agents": list(new_config.agents.keys())}
    except Exception as e:
        logger.error("Flow config update failed: %s", e, exc_info=True)
        return {"ok": False, "error": str(e)}


@router.get("/config/bots")
async def get_bots_config_endpoint(user_id: str = Depends(get_user_id)):
    """Return current bots.yaml config text."""
    from app.bot_config import read_bots_yaml
    return {"yaml": read_bots_yaml()}


@router.put("/config/bots")
async def update_bots_config(body: BotsConfigUpdate, user_id: str = Depends(get_user_id)):
    """Validate YAML, hot-reload bots config."""
    try:
        from app.bot_config import reload_bots_config, save_bots_yaml
        new_config = reload_bots_config(body.yaml_text)
        save_bots_yaml(body.yaml_text)
        return {"ok": True, "bots": list(new_config.bots.keys())}
    except Exception as e:
        logger.error("Bots config update failed: %s", e, exc_info=True)
        return {"ok": False, "error": str(e)}
