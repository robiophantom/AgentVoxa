"""Embedding service using Gemini API (text-embedding-004)."""
from __future__ import annotations

import logging
import google.generativeai as genai
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)

MODEL_NAME = "models/gemini-embedding-2"

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def _call_gemini_embed(texts: list[str]) -> list[list[float]]:
    try:
        result = genai.embed_content(
            model=MODEL_NAME,
            content=texts,
            task_type="retrieval_document",
            output_dimensionality=settings.embedding_dim
        )
        # The result['embedding'] is either a list of floats (if single string passed) 
        # or a list of lists of floats (if list passed). 
        # Since we always pass a list (even if batch size 1), we return the list of lists.
        return result['embedding']
    except Exception as e:
        logger.error(f"Gemini embedding failed: {e}")
        raise

def embed_texts(texts: list[str], batch_size: int = 8) -> list[list[float]]:
    """Return a list of L2-normalised float embeddings for each input text using Gemini."""
    if not texts:
        return []
        
    all_embeddings = []
    
    # Process in batches to respect rate limits and payload sizes
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_embeddings = _call_gemini_embed(batch)
        all_embeddings.extend(batch_embeddings)
        
    return all_embeddings

def embed_single(text: str) -> list[float]:
    """Convenience wrapper for a single text."""
    return embed_texts([text])[0]
