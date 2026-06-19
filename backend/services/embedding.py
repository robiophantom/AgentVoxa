"""Embedding service using sentence-transformers all-MiniLM-L6-v2."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def embed_texts(texts: list[str], batch_size: int = 8) -> list[list[float]]:
    """Return a list of L2-normalised float embeddings for each input text."""
    model = _get_model()
    embeddings: np.ndarray = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return embeddings.tolist()


def embed_single(text: str) -> list[float]:
    """Convenience wrapper for a single text."""
    return embed_texts([text])[0]
