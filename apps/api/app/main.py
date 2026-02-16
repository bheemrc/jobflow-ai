"""FastAPI application for Nexus AI — LangGraph-powered multi-agent system."""

from __future__ import annotations

# Load .env BEFORE any other app imports so OPENAI_API_KEY is in os.environ
from dotenv import load_dotenv
load_dotenv()

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db, close_db
from app.flow_config import load_flow_config
from app.graph import create_compiled_graph
from app.bot_manager import bot_manager
from app.thought_engine import (
    initialize_triggers as init_thought_triggers,
    start_scheduler as start_thought_scheduler,
    stop_scheduler as stop_thought_scheduler,
)
from app.routers import (
    set_graph,
    health_router,
    coach_router,
    approvals_router,
    agents_router,
    jobs_router,
    leetcode_router,
    events_router,
    resume_router,
    bots_router,
    prep_router,
    journal_router,
    timeline_router,
    dna_router,
    katalyst_router,
    admin_dna_router,
    prompt_proposals_router,
    admin_router,
    group_chats_router,
    research_router,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------- Lifespan ----------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting Nexus AI Service on port %s", settings.port)
    await init_db()
    flow_config = load_flow_config()
    graph = await create_compiled_graph(settings.postgres_url, flow_config=flow_config)
    set_graph(graph)
    logger.info("LangGraph orchestrator compiled and ready (config-driven)")

    # Initialize bot manager
    try:
        await bot_manager.initialize()
        logger.info("BotManager initialized")
    except Exception as e:
        logger.warning("BotManager initialization failed: %s (bots will be unavailable)", e)

    # Initialize thought engine triggers + scheduler
    try:
        await init_thought_triggers()
        await start_thought_scheduler()
        logger.info("Thought engine initialized with scheduler")
    except Exception as e:
        logger.warning("Thought engine initialization failed: %s", e)

    # DNA pulse is now started by bot_manager via PulseRunner

    yield

    # Shutdown scheduled triggers
    try:
        await stop_thought_scheduler()
    except Exception:
        pass

    # Shutdown bot manager
    try:
        await bot_manager.shutdown()
    except Exception:
        pass

    await close_db()
    logger.info("Nexus AI Service shutting down")


# ---------- App ----------

app = FastAPI(
    title="Nexus AI Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all modular routers
app.include_router(health_router)
app.include_router(coach_router)
app.include_router(approvals_router)
app.include_router(agents_router)
app.include_router(jobs_router)
app.include_router(leetcode_router)
app.include_router(events_router)
app.include_router(resume_router)
app.include_router(bots_router)
app.include_router(prep_router)
app.include_router(journal_router)
app.include_router(timeline_router)
app.include_router(dna_router)
app.include_router(katalyst_router)
app.include_router(admin_dna_router)
app.include_router(prompt_proposals_router)
app.include_router(admin_router)
app.include_router(group_chats_router)
app.include_router(research_router)


# ---------- Runner ----------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
