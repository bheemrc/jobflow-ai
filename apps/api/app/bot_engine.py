"""Bot execution engine — runs a single bot autonomously.

For each bot run:
1. Resolve model from config -> ChatOpenAI with TokenCountingCallback
2. Bind tools from TOOL_REGISTRY
3. Build messages from bot prompt
4. Call run_agent_with_tools() (reusing existing tool loop, retry, reflection)
5. Persist results + token usage to DB
6. Publish SSE events via EventBus

Production features:
- Correlation IDs (run_id) on all log entries
- Output size limits to prevent memory issues
- Structured error classification
- Safe DB persistence (errors in persistence don't crash the run)
- Retry-aware event publishing
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.bot_config import BotConfig, BotsFlowConfig
from app.event_bus import event_bus
from app.nodes.tool_executor import run_agent_with_tools
from app.token_tracking import TokenCountingCallback, persist_token_usage

logger = logging.getLogger(__name__)

# Output size limit to prevent memory issues (100KB)
MAX_OUTPUT_SIZE = 100_000
# Maximum retries for DB persistence
DB_PERSIST_RETRIES = 2


class BotRunError(Exception):
    """Structured bot run error with classification."""
    def __init__(self, message: str, error_type: str = "runtime", retriable: bool = False):
        super().__init__(message)
        self.error_type = error_type
        self.retriable = retriable


async def _safe_publish(event: dict) -> None:
    """Publish event to EventBus, swallowing errors to not crash the run."""
    try:
        await event_bus.publish(event)
    except Exception as e:
        logger.warning("Failed to publish event %s: %s", event.get("type"), e)


async def _safe_persist_run(
    run_id: str, bot_name: str, trigger_type: str, started_at: datetime,
) -> None:
    """Persist bot run record with retry, swallowing errors."""
    from app.db import create_bot_run
    for attempt in range(DB_PERSIST_RETRIES + 1):
        try:
            await create_bot_run(
                run_id=run_id, bot_name=bot_name,
                trigger_type=trigger_type, started_at=started_at,
            )
            return
        except Exception as e:
            if attempt < DB_PERSIST_RETRIES:
                await asyncio.sleep(0.5 * (attempt + 1))
            else:
                logger.error("Failed to persist bot run %s after %d attempts: %s",
                             run_id, DB_PERSIST_RETRIES + 1, e)


async def _safe_complete_run(
    run_id: str, status: str, output: str,
    input_tokens: int, output_tokens: int, cost: float,
) -> None:
    """Complete bot run record with retry, swallowing errors."""
    from app.db import complete_bot_run
    for attempt in range(DB_PERSIST_RETRIES + 1):
        try:
            await complete_bot_run(
                run_id=run_id, status=status, output=output,
                input_tokens=input_tokens, output_tokens=output_tokens, cost=cost,
            )
            return
        except Exception as e:
            if attempt < DB_PERSIST_RETRIES:
                await asyncio.sleep(0.5 * (attempt + 1))
            else:
                logger.error("Failed to complete bot run %s after %d attempts: %s",
                             run_id, DB_PERSIST_RETRIES + 1, e)


async def _safe_log(run_id: str, level: str, event_type: str, message: str, data: dict | None = None) -> None:
    """Create bot log entry and publish to SSE for live viewing, swallowing errors."""
    from app.db import create_bot_log
    try:
        await create_bot_log(run_id=run_id, level=level, event_type=event_type, message=message, data=data)
    except Exception as e:
        logger.warning("Failed to create bot log for run %s: %s", run_id, e)
    # Also publish to SSE so the frontend can show live logs
    await _safe_publish({
        "type": "bot_log",
        "run_id": run_id,
        "level": level,
        "event_type": event_type,
        "message": message,
        "data": data,
    })


async def _post_run_events(bot_name: str, all_messages: list, run_id: str) -> None:
    """Scan tool call results and emit events to trigger downstream bots."""
    try:
        from app.bot_manager import bot_manager

        # Emit generic completion event for bot chaining
        await bot_manager.handle_event(f"bot_completed:{bot_name}", {
            "bot_name": bot_name, "run_id": run_id,
        })

        # Scan messages for tool calls → emit relevant events
        jobs_saved = 0
        stage_changes: set[str] = set()
        for msg in all_messages:
            if hasattr(msg, "tool_calls"):
                for tc in msg.tool_calls:
                    if tc.get("name") == "save_job":
                        jobs_saved += 1
                    if tc.get("name") == "update_job_stage":
                        args = tc.get("args", {})
                        if isinstance(args, dict) and args.get("new_stage"):
                            stage_changes.add(args["new_stage"])
            # Also check tool response messages
            if hasattr(msg, "content") and isinstance(msg.content, str):
                content_lower = msg.content.lower()
                if '"saved": true' in content_lower:
                    jobs_saved += 1
                if '"new_stage": "interview"' in content_lower:
                    stage_changes.add("interview")

        if jobs_saved > 0:
            await bot_manager.handle_event("user:job_saved", {
                "bot_name": bot_name, "jobs_saved": jobs_saved, "run_id": run_id,
            })
            logger.info("Bot %s saved %d jobs, emitting user:job_saved event (run=%s)",
                        bot_name, jobs_saved, run_id)

        # Emit stage-specific events for bot triggers (user:stage_interview, etc.)
        for stage in stage_changes:
            event_name = f"user:stage_{stage}"
            await bot_manager.handle_event(event_name, {
                "bot_name": bot_name, "stage": stage, "run_id": run_id,
            })
            logger.info("Bot %s changed job to stage '%s', emitting %s event (run=%s)",
                        bot_name, stage, event_name, run_id)

    except Exception as e:
        logger.warning("Post-run event emission failed for %s: %s", bot_name, e)


def _truncate_output(output: str) -> str:
    """Truncate output to MAX_OUTPUT_SIZE with a notice."""
    if len(output) <= MAX_OUTPUT_SIZE:
        return output
    return output[:MAX_OUTPUT_SIZE] + f"\n\n[Output truncated at {MAX_OUTPUT_SIZE} characters]"


async def _auto_save_bot_output(bot_name: str, display_name: str, output: str, run_id: str) -> None:
    """Automatically save bot output to journal_entries after each run."""
    if not output or len(output) < 50:
        return
    try:
        from app.db import create_journal_entry
        await create_journal_entry(
            title=f"{display_name} run",
            content=output[:5000],
            entry_type="summary",
            agent=bot_name,
            priority="medium",
            tags=[bot_name, "bot_run", run_id],
        )
        logger.info("Auto-saved journal entry for bot %s run %s", bot_name, run_id)
    except Exception as e:
        logger.warning("Failed to auto-save journal for bot %s: %s", bot_name, e)


MAX_AUTO_RETRIES = 2
RETRY_BACKOFF_BASE = 5  # seconds


async def execute_bot_with_retry(
    bot_config: BotConfig,
    bots_flow_config: BotsFlowConfig,
    trigger_type: str = "scheduled",
    context: str | None = None,
    user_id: str = "",
) -> dict:
    """Execute a bot with automatic retry on retriable errors."""
    last_result = {}
    for attempt in range(MAX_AUTO_RETRIES + 1):
        result = await execute_bot(bot_config, bots_flow_config, trigger_type, context=context, user_id=user_id)
        last_result = result
        if result.get("status") != "errored" or not result.get("retriable"):
            return result
        if attempt < MAX_AUTO_RETRIES:
            wait = RETRY_BACKOFF_BASE * (2 ** attempt)
            logger.info("Bot %s failed with retriable error, retrying in %ds (attempt %d/%d)",
                        bot_config.name, wait, attempt + 1, MAX_AUTO_RETRIES)
            await _safe_publish({
                "type": "bot_run_retry",
                "bot_name": bot_config.name,
                "run_id": result.get("run_id"),
                "attempt": attempt + 1,
                "max_retries": MAX_AUTO_RETRIES,
                "wait_seconds": wait,
                "error": result.get("error", ""),
            })
            await asyncio.sleep(wait)
    return last_result


async def execute_bot(
    bot_config: BotConfig,
    bots_flow_config: BotsFlowConfig,
    trigger_type: str = "scheduled",
    context: str | None = None,
    user_id: str = "",
) -> dict:
    """Execute a single bot run end-to-end.

    Args:
        bot_config: The bot's configuration.
        bots_flow_config: The full bots config (for model resolution, tools).
        trigger_type: How this run was triggered ("scheduled", "manual", "event").
        user_id: The user context for tool calls that need it.

    Returns:
        Dict with run results: run_id, status, output, token_usage, etc.
    """
    from app.user_context import current_user_id
    current_user_id.set(user_id)

    run_id = uuid.uuid4().hex[:16]
    bot_name = bot_config.name
    started_at = datetime.now(timezone.utc)

    # Structured logging with correlation ID
    log_ctx = {"run_id": run_id, "bot": bot_name, "trigger": trigger_type}
    logger.info("Bot run starting: %s", log_ctx)

    # Persist run record first (so we can always find it)
    await _safe_persist_run(run_id, bot_name, trigger_type, started_at)

    # Emit run start event
    await _safe_publish({
        "type": "bot_run_start",
        "bot_name": bot_name,
        "run_id": run_id,
        "trigger_type": trigger_type,
    })

    try:
        # 1. Resolve model with token tracking callback
        token_cb = TokenCountingCallback()
        model_name = bots_flow_config.resolve_model(bot_config.model)
        model = ChatOpenAI(
            model=model_name,
            temperature=bot_config.temperature,
            max_tokens=bot_config.max_tokens,
            callbacks=[token_cb],
        )

        # 2. Bind tools
        tools = bots_flow_config.get_tools_for_bot(bot_name)
        if tools:
            model = model.bind_tools(tools)

        await _safe_log(run_id, "info", "model_resolved",
                        f"Using model {model_name} with {len(tools)} tools")

        # 2b. Load genome context for DNA-enabled bots
        genome_prompt = ""
        if bot_config.dna.enabled and bot_config.dna.inject_genome:
            try:
                from app.dna.prompt_builder import build_genome_prompt
                genome_prompt = await build_genome_prompt(bot_name, user_id)
                if genome_prompt:
                    await _safe_log(run_id, "info", "genome_loaded",
                                    f"Loaded genome context ({len(genome_prompt)} chars)")
            except Exception as e:
                logger.debug("Genome loading failed for %s: %s", bot_name, e)

        # 3. Build messages with template variable resolution
        prompt_vars = {
            "date": started_at.strftime("%Y-%m-%d"),
            "time": started_at.strftime("%H:%M UTC"),
            "datetime": started_at.strftime("%Y-%m-%d %H:%M UTC"),
            "bot_name": bot_name,
            "display_name": bot_config.display_name,
            "trigger_type": trigger_type,
            "run_id": run_id,
            "model": model_name,
        }
        resolved_prompt = bot_config.prompt
        for key, val in prompt_vars.items():
            resolved_prompt = resolved_prompt.replace(f"{{{key}}}", val)

        human_content = (
            f"Execute your autonomous task now. "
            f"Today is {started_at.strftime('%A, %B %d, %Y')}. "
            f"This is an automated run (trigger: {trigger_type}). "
            f"Use your tools to gather data, then produce your report."
        )
        if context:
            human_content += (
                f"\n\nAdditional context provided by the user:\n"
                f"{context[:5000]}"
            )

        # Inject genome context into system prompt if available
        full_system_prompt = resolved_prompt
        if genome_prompt:
            full_system_prompt = resolved_prompt + "\n\n" + genome_prompt

        messages = [
            SystemMessage(content=full_system_prompt),
            HumanMessage(content=human_content),
        ]

        # 4. Run agent with tools
        await _safe_log(run_id, "info", "agent_start", "Starting agent execution loop")

        final_message, all_messages = await run_agent_with_tools(
            model=model,
            messages=messages,
            tools=tools,
            config=None,
            max_rounds=bot_config.max_tool_rounds,
            min_tool_calls=bot_config.min_tool_calls,
            max_reflections=bot_config.max_reflections,
            quality_criteria=bot_config.quality_criteria or None,
        )

        raw_output = final_message.content if final_message else ""
        output = _truncate_output(raw_output)
        completed_at = datetime.now(timezone.utc)
        duration_seconds = (completed_at - started_at).total_seconds()

        # 5. Get token usage
        usage = token_cb.get_usage()

        # Persist token usage (non-blocking)
        try:
            await persist_token_usage(bot_name, usage)
        except Exception as e:
            logger.warning("Token usage persist failed for run %s: %s", run_id, e)

        # Complete run in DB
        status = "completed"
        if bot_config.requires_approval and output:
            status = "awaiting_approval"

        await _safe_complete_run(
            run_id=run_id, status=status, output=output,
            input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
            cost=usage.cost,
        )

        # Log completion
        await _safe_log(run_id, "info", "run_complete",
            f"Completed in {duration_seconds:.1f}s",
            {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cost": usage.cost,
                "tool_calls": usage.calls,
                "output_truncated": len(raw_output) > MAX_OUTPUT_SIZE,
            },
        )

        # 6. Emit completion event
        await _safe_publish({
            "type": "bot_run_complete",
            "bot_name": bot_name,
            "run_id": run_id,
            "status": status,
            "duration_seconds": duration_seconds,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost": usage.cost,
            "output_preview": output[:300],
        })

        # Update bot state
        from app.db import update_bot_state
        try:
            await update_bot_state(bot_name, "waiting", last_run_at=completed_at)
        except Exception:
            pass

        logger.info("Bot run complete: run_id=%s tokens=%d/%d cost=$%.4f duration=%.1fs",
                     run_id, usage.input_tokens, usage.output_tokens, usage.cost, duration_seconds)

        result: dict[str, Any] = {
            "run_id": run_id,
            "bot_name": bot_name,
            "status": status,
            "output": output,
            "trigger_type": trigger_type,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": duration_seconds,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost": usage.cost,
        }

        if status == "awaiting_approval":
            await _safe_publish({
                "type": "bot_approval_requested",
                "bot_name": bot_name,
                "run_id": run_id,
                "approval_type": bot_config.approval_type,
                "priority": bot_config.approval_priority,
                "output_preview": output[:500],
            })

        # 7. Auto-save bot output to journal
        await _auto_save_bot_output(bot_name, bot_config.display_name, output, run_id)

        # 7b. DNA: Extract genes from output and write genome YAML
        if bot_config.dna.enabled and bot_config.dna.extract_genes and output:
            try:
                from app.dna.gene_extractor import extract_genes_from_output
                from app.dna import db as dna_db
                from app.dna.models import DECAY_RATES
                from app.dna.genome_writer import write_genome_yaml

                extracted = await extract_genes_from_output(
                    agent=bot_name,
                    output=output,
                    run_context={"trigger_type": trigger_type, "run_id": run_id},
                )
                for g in extracted:
                    await dna_db.create_gene(
                        agent=bot_name,
                        gene_type=g["type"],
                        name=g["name"],
                        description=g.get("description", ""),
                        content=output[:500],
                        confidence=g.get("confidence", 0.5),
                        decay_rate=DECAY_RATES.get(g["type"], 0.03),
                        source=f"bot_run:{run_id}",
                        tags=g.get("tags", []),
                        user_id=user_id,
                    )
                if extracted:
                    await _safe_log(run_id, "info", "genes_extracted",
                                    f"Extracted {len(extracted)} genes")
                # Auto-write genome YAML
                await write_genome_yaml(bot_name, user_id)
            except Exception as e:
                logger.debug("Gene extraction failed for %s: %s", bot_name, e)

        # 8. Post-run event chaining — trigger downstream bots
        await _post_run_events(bot_name, all_messages, run_id)

        # 9. Trigger thought engine for timeline posts
        try:
            from app.thought_engine import handle_event as thought_handle_event
            await thought_handle_event(
                f"bot_completed:{bot_name}",
                {
                    "bot_name": bot_name,
                    "run_id": run_id,
                    "output_preview": output[:500],
                    "status": status,
                },
            )
        except Exception as te:
            logger.debug("Thought engine trigger failed: %s", te)

        return result

    except asyncio.CancelledError:
        logger.info("Bot run cancelled: run_id=%s bot=%s", run_id, bot_name)
        await _safe_publish({
            "type": "bot_run_error",
            "bot_name": bot_name,
            "run_id": run_id,
            "error": "Run was cancelled",
            "error_type": "cancelled",
        })
        await _safe_complete_run(run_id, "cancelled", "", 0, 0, 0)
        await _safe_log(run_id, "warning", "run_cancelled", "Run was cancelled by user or timeout")

        return {
            "run_id": run_id,
            "bot_name": bot_name,
            "status": "cancelled",
            "output": "",
            "error": "Run was cancelled",
            "error_type": "cancelled",
        }

    except Exception as e:
        error_type = "runtime"
        retriable = False
        error_msg = str(e)

        # Classify errors for the frontend
        if "rate_limit" in error_msg.lower() or "429" in error_msg:
            error_type = "rate_limit"
            retriable = True
        elif "timeout" in error_msg.lower():
            error_type = "timeout"
            retriable = True
        elif "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            error_type = "auth"
            retriable = False
        elif "connection" in error_msg.lower():
            error_type = "connection"
            retriable = True

        logger.error("Bot run failed: run_id=%s bot=%s error_type=%s: %s",
                      run_id, bot_name, error_type, e, exc_info=True)

        await _safe_publish({
            "type": "bot_run_error",
            "bot_name": bot_name,
            "run_id": run_id,
            "error": error_msg[:500],
            "error_type": error_type,
            "retriable": retriable,
        })

        await _safe_complete_run(run_id, "errored", "", 0, 0, 0)
        await _safe_log(run_id, "error", "run_error", error_msg[:1000],
                        {"error_type": error_type, "retriable": retriable})

        from app.db import update_bot_state
        try:
            await update_bot_state(bot_name, "errored")
        except Exception:
            pass

        return {
            "run_id": run_id,
            "bot_name": bot_name,
            "status": "errored",
            "output": "",
            "error": error_msg[:500],
            "error_type": error_type,
            "retriable": retriable,
        }
