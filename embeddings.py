"""Shared Gemini embedding helper for LeaseLens. No local ML/PyTorch required."""
from __future__ import annotations

import math
import os
from functools import lru_cache
from typing import Literal

from google import genai
from google.genai import types

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "384"))

@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not configured")
    return genai.Client(api_key=api_key)


def generate_embedding(
    text: str,
    task_type: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"] = "RETRIEVAL_DOCUMENT",
) -> list[float]:
    """Generate a Gemini embedding, normalized for cosine similarity."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Cannot generate an embedding for empty text")

    result = get_client().models.embed_content(
        model=MODEL_NAME,
        contents=text,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=EMBEDDING_DIMENSIONS,
        ),
    )
    if not result.embeddings or not result.embeddings[0].values:
        raise RuntimeError("Gemini returned an empty embedding")

    vector = [float(value) for value in result.embeddings[0].values]
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSIONS}, got {len(vector)}"
        )

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        raise RuntimeError("Gemini returned a zero-length embedding")
    return [value / norm for value in vector]
