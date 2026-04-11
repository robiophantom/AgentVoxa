"""RAG retrieval: hybrid search (vector + full-text keyword matching)."""
from __future__ import annotations

from qdrant_client.models import Filter, FieldCondition, MatchText

from core.config import get_settings
from core.qdrant import get_qdrant_client
from services.embedding import embed_single

settings = get_settings()


async def vector_search(
    query: str,
    top_k: int = 20,
    score_threshold: float = 0.3,
) -> list[dict]:
    """Dense vector search in Qdrant."""
    client = get_qdrant_client()
    query_vector = embed_single(query)

    results = await client.search(
        collection_name=settings.qdrant_collection_name,
        query_vector=query_vector,
        limit=top_k,
        score_threshold=score_threshold,
        with_payload=True,
    )
    return [
        {
            "id": str(hit.id),
            "score": hit.score,
            "text": hit.payload.get("text", ""),
            "document_id": hit.payload.get("document_id"),
            "filename": hit.payload.get("filename"),
            "chunk_index": hit.payload.get("chunk_index"),
        }
        for hit in results
    ]


async def full_text_search(
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Keyword full-text search using Qdrant payload filter matching."""
    client = get_qdrant_client()
    # Split query into keywords for broad match
    keywords = [w for w in query.split() if len(w) > 3]

    if not keywords:
        return []

    # Use the first keyword as a MatchText filter; combine others via scroll
    fts_filter = Filter(
        should=[
            FieldCondition(key="text", match=MatchText(text=kw))
            for kw in keywords[:5]  # limit to 5 keywords
        ]
    )

    results, _ = await client.scroll(
        collection_name=settings.qdrant_collection_name,
        scroll_filter=fts_filter,
        limit=top_k,
        with_payload=True,
        with_vectors=False,
    )
    return [
        {
            "id": str(r.id),
            "score": 0.5,  # FTS results don't have a relevance score
            "text": r.payload.get("text", ""),
            "document_id": r.payload.get("document_id"),
            "filename": r.payload.get("filename"),
            "chunk_index": r.payload.get("chunk_index"),
        }
        for r in results
    ]


async def hybrid_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Merge vector search and FTS results, de-duplicate by chunk id,
    and rank by vector score (primary) + FTS presence bonus.
    """
    vector_results = await vector_search(query, top_k=top_k)
    fts_results = await full_text_search(query, top_k=top_k)

    seen: dict[str, dict] = {}
    fts_ids = {r["id"] for r in fts_results}

    for r in vector_results:
        seen[r["id"]] = r

    for r in fts_results:
        if r["id"] not in seen:
            seen[r["id"]] = r
        else:
            # Boost score if hit appears in both
            seen[r["id"]]["score"] = min(seen[r["id"]]["score"] + 0.1, 1.0)

    ranked = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]
