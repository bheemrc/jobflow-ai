"""LLM-based gene extraction from bot output.

After a bot runs, this module analyzes its output to extract new genes
(facts, beliefs, insights, goals, hunches) with plain English names.
Uses gpt-4o-mini to keep costs low.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


async def extract_genes_from_output(
    agent: str,
    output: str,
    run_context: dict | None = None,
) -> list[dict]:
    """Extract genes from bot output using LLM analysis.

    Returns list of gene dicts with keys:
    - name: Plain English name (e.g. "Prefers remote backend roles")
    - type: FACT | BELIEF | SKILL | INSIGHT | GOAL | HUNCH
    - description: What this gene means
    - confidence: 0.0-1.0 initial confidence
    - tags: List of tags for categorization
    """
    if not output or len(output) < 50:
        return []

    try:
        from openai import AsyncOpenAI
        import os

        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        context_str = ""
        if run_context:
            context_str = f"\nBot context: {json.dumps(run_context)[:500]}"

        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=1000,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": """You extract knowledge genes from AI agent output.

A gene is an atomic unit of knowledge the agent has learned or discovered.

Gene types:
- FACT: Verified data point (e.g. "User has 5 years Python experience")
- BELIEF: Learned preference or pattern (e.g. "Prefers remote roles")
- SKILL: Capability signal (e.g. "Good at resume keyword optimization")
- INSIGHT: Analysis conclusion (e.g. "FAANG hiring is slowing in Q1")
- GOAL: Active objective discovered (e.g. "Find senior backend roles")
- HUNCH: Low-confidence lead worth tracking (e.g. "Stripe may be expanding")

Rules:
- Every gene MUST have a clear, plain English name (max 60 chars)
- Description should explain what this gene means and why it matters
- Confidence: FACT=0.7, BELIEF=0.5, SKILL=0.6, INSIGHT=0.6, GOAL=0.5, HUNCH=0.3
- Only extract genuinely useful knowledge, not trivial observations
- Max 5 genes per extraction (quality over quantity)
- Tags help categorize (e.g. ["remote", "backend", "python"])

Return JSON: {"genes": [...]}"""},
                {"role": "user", "content": f"""Extract knowledge genes from this agent output:

Agent: {agent}{context_str}

Output:
{output[:3000]}"""},
            ],
        )

        response_text = completion.choices[0].message.content
        data = json.loads(response_text)
        genes = data.get("genes", [])

        # Validate and normalize
        valid_types = {"FACT", "BELIEF", "SKILL", "INSIGHT", "GOAL", "HUNCH"}
        result = []
        for g in genes[:5]:
            if not isinstance(g, dict) or not g.get("name"):
                continue
            gene_type = g.get("type", "FACT").upper()
            if gene_type not in valid_types:
                gene_type = "FACT"
            result.append({
                "name": str(g["name"])[:60],
                "type": gene_type,
                "description": str(g.get("description", ""))[:200],
                "confidence": max(0.1, min(1.0, float(g.get("confidence", 0.5)))),
                "tags": [str(t)[:30] for t in g.get("tags", [])][:5],
            })

        logger.info("Extracted %d genes from %s output", len(result), agent)
        return result

    except Exception as e:
        logger.warning("Gene extraction failed for %s: %s", agent, e)
        return []
