"""Document management router (Admin only)."""
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import require_role
from models.document import Document, DocumentStatus
from models.user import User, UserRole
from services.document_processor import (
    delete_document_chunks,
    ingest_document,
    validate_file,
)

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    content = await file.read()
    mime_type = file.content_type or "application/octet-stream"

    try:
        validate_file(file.filename, content, mime_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Persist file to disk
    safe_name = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        filename=safe_name,
        original_name=file.filename,
        mime_type=mime_type,
        size_bytes=len(content),
        status=DocumentStatus.processing,
        uploaded_by=current_user.id,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    # Ingest asynchronously (inline for simplicity)
    try:
        point_ids = await ingest_document(doc.id, file.filename, content)
        doc.chunk_count = len(point_ids)
        doc.status = DocumentStatus.ready
    except Exception as exc:
        doc.status = DocumentStatus.failed
        doc.error_message = str(exc)

    await db.flush()

    return {
        "id": doc.id,
        "original_name": doc.original_name,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
    }


@router.get("/")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    docs = result.scalars().all()
    return [
        {
            "id": d.id,
            "original_name": d.original_name,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "size_bytes": d.size_bytes,
            "created_at": d.created_at,
        }
        for d in docs
    ]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc: Document | None = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Delete Qdrant chunks
    await delete_document_chunks(document_id)

    # Remove file from disk
    file_path = os.path.join(UPLOAD_DIR, doc.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    await db.delete(doc)
