"""Token counting and cost tracking for bot runs.

LangChain AsyncCallbackHandler that captures prompt_tokens / completion_tokens
from every LLM call and computes cost using per-model pricing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler

logger = logging.getLogger(__name__)

# Per-model pricing (USD per 1K tokens) — update as pricing changes
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-2024-08-06": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o-mini-2024-07-18": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
}

# Default pricing for unknown models
DEFAULT_PRICING = {"input": 0.003, "output": 0.015}


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute cost in USD for a given model and token counts."""
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    cost = (input_tokens / 1000.0) * pricing["input"] + (output_tokens / 1000.0) * pricing["output"]
    return round(cost, 6)


@dataclass
class TokenUsageRecord:
    """Accumulated token usage for a single bot run."""
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    model: str = ""
    calls: int = 0


class TokenCountingCallback(AsyncCallbackHandler):
    """Async callback handler that tracks token usage across LLM calls.

    Accumulates totals per run. Attach to a ChatOpenAI model via callbacks=[cb].
    """

    def __init__(self) -> None:
        super().__init__()
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.cost: float = 0.0
        self.model: str = ""
        self.calls: int = 0

    async def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Called when an LLM call finishes. Extract token usage from response."""
        try:
            if not hasattr(response, "llm_output") or response.llm_output is None:
                # Try generations-level token usage (newer LangChain)
                for gen_list in response.generations:
                    for gen in gen_list:
                        info = getattr(gen, "generation_info", {}) or {}
                        usage = info.get("token_usage") or info.get("usage") or {}
                        if usage:
                            self._accumulate(usage, info.get("model_name", ""))
                return

            llm_output = response.llm_output
            usage = llm_output.get("token_usage", {})
            model = llm_output.get("model_name", "")
            if usage:
                self._accumulate(usage, model)
        except Exception as e:
            logger.debug("TokenCountingCallback.on_llm_end error: %s", e)

    def _accumulate(self, usage: dict, model: str) -> None:
        prompt = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0) or 0
        completion = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0) or 0
        self.input_tokens += prompt
        self.output_tokens += completion
        self.calls += 1
        if model:
            self.model = model
        self.cost += compute_cost(self.model or "gpt-4o", prompt, completion)

    def get_usage(self) -> TokenUsageRecord:
        return TokenUsageRecord(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cost=round(self.cost, 6),
            model=self.model,
            calls=self.calls,
        )

    def reset(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost = 0.0
        self.model = ""
        self.calls = 0


async def persist_token_usage(
    bot_name: str,
    usage: TokenUsageRecord,
) -> None:
    """Write token usage to the token_usage table (upsert daily aggregate)."""
    from app.db import get_conn

    today = date.today().isoformat()

    async with get_conn() as conn:
        await conn.execute("""
            INSERT INTO token_usage (date, bot_name, run_count, input_tokens, output_tokens, cost, model)
            VALUES ($1, $2, 1, $3, $4, $5, $6)
            ON CONFLICT (date, bot_name, model) DO UPDATE SET
                run_count = token_usage.run_count + 1,
                input_tokens = token_usage.input_tokens + $3,
                output_tokens = token_usage.output_tokens + $4,
                cost = token_usage.cost + $5
        """, today, bot_name, usage.input_tokens, usage.output_tokens,
            round(usage.cost, 6), usage.model)
