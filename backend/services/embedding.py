"""Embedding service using sentence-transformers all-MiniLM-L6-v2."""
from __future__ import annotations

import gc
from functools import lru_cache

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

# Limit PyTorch threads to reduce memory footprint on limited environments (e.g. Render 512MB)
torch.set_num_threads(1)

MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    # Explicitly load on CPU to prevent unnecessary overhead
    return SentenceTransformer(MODEL_NAME, device='cpu')


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
    
    # Free memory immediately after encoding
    gc.collect()
    
    return embeddings.tolist()


def embed_single(text: str) -> list[float]:
    """Convenience wrapper for a single text."""
    return embed_texts([text])[0]
