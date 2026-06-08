"""Qdrant client initialisation with recommended optimizer settings."""
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    OptimizersConfigDiff,
    VectorParams,
)

from core.config import get_settings

settings = get_settings()

# Optimizer settings as requested
_OPTIMIZERS_CONFIG = OptimizersConfigDiff(
    default_segment_number=2,    # Target 2 final segments (prevents hundreds of tiny segments)
    memmap_threshold=20000,      # Switch to mmap after 20k vectors (saves RAM)
    indexing_threshold=20000,    # Build HNSW index after 20k vectors
    flush_interval_sec=5,        # Flush WAL to segments every 5s
    max_optimization_threads=2,  # Background merge threads
)

_client: AsyncQdrantClient | None = None


def get_qdrant_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        if settings.qdrant_url:
            _client = AsyncQdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
                prefer_grpc=False,
            )
        else:
            _client = AsyncQdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                prefer_grpc=False,
            )
    return _client


async def ensure_collection() -> None:
    """Create the Qdrant collection if it does not exist, or update its optimizers."""
    client = get_qdrant_client()
    collections = await client.get_collections()
    existing = [c.name for c in collections.collections]

    if settings.qdrant_collection_name not in existing:
        await client.create_collection(
            collection_name=settings.qdrant_collection_name,
            vectors_config=VectorParams(
                size=settings.embedding_dim,
                distance=Distance.COSINE,
            ),
            optimizers_config=_OPTIMIZERS_CONFIG,
        )
        
        # Create a payload index for full-text search on the 'text' field
        from qdrant_client.models import TextIndexParams, TextIndexType
        await client.create_payload_index(
            collection_name=settings.qdrant_collection_name,
            field_name="text",
            field_schema=TextIndexParams(
                type=TextIndexType.TEXT,
                tokenizer="word",
                min_token_len=2,
                max_token_len=15,
                lowercase=True,
            ),
        )
    else:
        await client.update_collection(
            collection_name=settings.qdrant_collection_name,
            optimizers_config=_OPTIMIZERS_CONFIG,
        )
