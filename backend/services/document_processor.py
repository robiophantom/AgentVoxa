"""Document ingestion pipeline: validate → extract text → chunk → embed → upsert."""
from __future__ import annotations

import io
import uuid
from pathlib import Path

import tiktoken
from docx import Document as DocxDocument
from pypdf import PdfReader
from qdrant_client.models import PointStruct

from core.config import get_settings
from core.qdrant import get_qdrant_client
from services.embedding import embed_texts

settings = get_settings()

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/markdown",
    "text/plain",
}
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}
MAX_BYTES = settings.max_upload_size_mb * 1024 * 1024


def validate_file(filename: str, content: bytes, mime_type: str) -> None:
    """Raise ValueError if the file is invalid."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}")
    if len(content) > MAX_BYTES:
        raise ValueError(
            f"File size {len(content) / 1024 / 1024:.1f} MB exceeds limit of {settings.max_upload_size_mb} MB."
        )


def extract_text(filename: str, content: bytes) -> str:
    """Extract plain text from PDF, DOCX, MD, or TXT."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    elif ext == ".docx":
        doc = DocxDocument(io.BytesIO(content))
        return "\n".join(para.text for para in doc.paragraphs)
    else:  # .md / .txt
        return content.decode("utf-8", errors="replace")


def _count_tokens(text: str, enc) -> int:
    return len(enc.encode(text))


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    """Window-based chunking: split on newlines then merge into ~chunk_size token windows."""
    enc = tiktoken.get_encoding("cl100k_base")
    sentences = [s.strip() for s in text.split("\n") if s.strip()]

    chunks: list[str] = []
    current_tokens: list[str] = []
    current_count = 0

    for sentence in sentences:
        s_tokens = enc.encode(sentence)
        if current_count + len(s_tokens) > chunk_size and current_tokens:
            chunks.append(enc.decode(current_tokens))
            # Keep overlap
            overlap_tokens = current_tokens[-overlap:] if overlap else []
            current_tokens = overlap_tokens + s_tokens
            current_count = len(current_tokens)
        else:
            current_tokens.extend(s_tokens)
            current_count += len(s_tokens)

    if current_tokens:
        chunks.append(enc.decode(current_tokens))

    return [c for c in chunks if c.strip()]


async def ingest_document(
    document_id: int,
    filename: str,
    content: bytes,
) -> list[str]:
    """
    Full ingestion pipeline.
    Returns list of Qdrant point IDs upserted.
    """
    text = extract_text(filename, content)
    chunks = chunk_text(text, chunk_size=settings.chunk_size_tokens)

    if not chunks:
        return []

    # Generate embeddings in batch, reduced size to prevent PyTorch OOM
    embeddings = embed_texts(chunks, batch_size=2)

    # Build Qdrant points
    point_ids: list[str] = []
    points: list[PointStruct] = []

    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        point_id = str(uuid.uuid4())
        point_ids.append(point_id)
        points.append(
            PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "document_id": document_id,
                    "filename": filename,
                    "chunk_index": idx,
                    "text": chunk,
                },
            )
        )

    client = get_qdrant_client()

    # Upsert in batches of 100
    batch_size = 8
    for i in range(0, len(points), batch_size):
        await client.upsert(
            collection_name=settings.qdrant_collection_name,
            points=points[i : i + batch_size],
            wait=True,
        )

    return point_ids


async def delete_document_chunks(document_id: int) -> int:
    """Delete all Qdrant chunks belonging to document_id. Returns number of deleted points."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    client = get_qdrant_client()
    result = await client.delete(
        collection_name=settings.qdrant_collection_name,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=document_id),
                )
            ]
        ),
    )
    return result.operation_id or 0
