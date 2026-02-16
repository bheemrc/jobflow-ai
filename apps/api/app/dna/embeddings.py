"""OpenAI embedding generation + cosine similarity.

Uses text-embedding-3-small (API-only, no pgvector).
Embeddings stored as FLOAT8[] in PostgreSQL.
Cosine similarity computed in Python with numpy.
"""

from __future__ import annotations

import logging
import os
from typing import Sequence

logger = logging.getLogger(__name__)

# Lazy-loaded at first use
_client = None
_np = None

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    return _client


def _get_numpy():
    global _np
    if _np is None:
        import numpy as np
        _np = np
    return _np


async def generate_embedding(text: str) -> list[float]:
    """Generate an embedding vector for the given text.

    Uses text-embedding-3-small via the sync OpenAI client
    (wrapped in asyncio.to_thread for non-blocking).
    """
    import asyncio

    def _embed():
        client = _get_client()
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text[:8000],  # Max input tokens safety
        )
        return response.data[0].embedding

    return await asyncio.to_thread(_embed)


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts in a single API call."""
    import asyncio

    if not texts:
        return []

    def _embed_batch():
        client = _get_client()
        truncated = [t[:8000] for t in texts]
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=truncated,
        )
        return [item.embedding for item in response.data]

    return await asyncio.to_thread(_embed_batch)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Compute cosine similarity between two vectors using numpy."""
    np = _get_numpy()
    va = np.array(a, dtype=np.float64)
    vb = np.array(b, dtype=np.float64)
    dot = np.dot(va, vb)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def find_most_similar(
    target_embedding: Sequence[float],
    candidates: list[dict],
    embedding_key: str = "embedding",
    threshold: float = 0.85,
) -> list[tuple[dict, float]]:
    """Find candidates with cosine similarity above threshold.

    Returns list of (candidate_dict, similarity_score) sorted by score DESC.
    """
    results = []
    for candidate in candidates:
        emb = candidate.get(embedding_key)
        if not emb:
            continue
        sim = cosine_similarity(target_embedding, emb)
        if sim >= threshold:
            results.append((candidate, sim))
    results.sort(key=lambda x: x[1], reverse=True)
    return results
