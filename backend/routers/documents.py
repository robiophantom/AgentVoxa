"""Document management router (Admin only)."""
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db, async_sessionmaker
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


class BulkDeleteDocsRequest(BaseModel):
    ids: list[int]


async def background_ingest_documents(doc_ids: list[int], file_names: list[str], contents: list[bytes]):
    async with async_sessionmaker() as db:
        for doc_id, file_name, content in zip(doc_ids, file_names, contents):
            try:
                point_ids = await ingest_document(doc_id, file_name, content)
                await db.execute(
                    update(Document)
                    .where(Document.id == doc_id)
                    .values(chunk_count=len(point_ids), status=DocumentStatus.ready)
                )
            except Exception as exc:
                await db.execute(
                    update(Document)
                    .where(Document.id == doc_id)
                    .values(status=DocumentStatus.failed, error_message=str(exc))
                )
        await db.commit()


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    doc_ids = []
    file_names = []
    contents = []
    responses = []

    for file in files:
        content = await file.read()
        mime_type = file.content_type or "application/octet-stream"

        try:
            validate_file(file.filename, content, mime_type)
        except ValueError as exc:
            # Skip invalid files but continue others
            continue

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
        
        doc_ids.append(doc.id)
        file_names.append(file.filename)
        contents.append(content)
        
        responses.append({
            "id": doc.id,
            "original_name": doc.original_name,
            "status": doc.status,
            "chunk_count": doc.chunk_count,
        })

    await db.commit()

    if doc_ids:
        background_tasks.add_task(background_ingest_documents, doc_ids, file_names, contents)

    return responses


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
    await db.commit()


@router.delete("/bulk", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_documents(
    payload: BulkDeleteDocsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    if not payload.ids:
        return
        
    result = await db.execute(select(Document).where(Document.id.in_(payload.ids)))
    docs = result.scalars().all()
    
    for doc in docs:
        await delete_document_chunks(doc.id)
        file_path = os.path.join(UPLOAD_DIR, doc.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            
    await db.execute(delete(Document).where(Document.id.in_(payload.ids)))
    await db.commit()
