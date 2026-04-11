"""Chat router: REST endpoint + WebSocket for real-time chat."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.logs import ChatLog, InterestLevel
from services.agent import generate_answer

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None


@router.post("/")
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    session_id = payload.session_id or str(uuid.uuid4())
    result = await generate_answer(payload.message)

    log = ChatLog(
        session_id=session_id,
        user_message=payload.message,
        agent_response=result["answer"],
        retrieved_chunks=json.dumps([c["text"][:200] for c in result["chunks"]]),
        admission_interest=(
            InterestLevel.high if result["admission_interest"] else InterestLevel.none
        ),
        escalated_to_human=result["escalate_to_human"],
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
    )
    db.add(log)
    await db.flush()
    await db.commit()

    return {
        "session_id": session_id,
        "answer": result["answer"],
        "admission_interest": result["admission_interest"],
        "escalate_to_human": result["escalate_to_human"],
    }


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    """
    WebSocket chat endpoint.
    Client sends JSON: {"message": "...", "session_id": "...", ...}
    Server replies JSON: {"answer": "...", "admission_interest": bool, "escalate_to_human": bool}
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())

    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            message = payload.get("message", "").strip()
            if not message:
                await websocket.send_json({"error": "Empty message"})
                continue

            session_id = payload.get("session_id", session_id)
            result = await generate_answer(message)

            log = ChatLog(
                session_id=session_id,
                user_message=message,
                agent_response=result["answer"],
                retrieved_chunks=json.dumps([c["text"][:200] for c in result["chunks"]]),
                admission_interest=(
                    InterestLevel.high if result["admission_interest"] else InterestLevel.none
                ),
                escalated_to_human=result["escalate_to_human"],
                contact_name=payload.get("contact_name"),
                contact_email=payload.get("contact_email"),
                contact_phone=payload.get("contact_phone"),
            )
            db.add(log)
            await db.flush()
            await db.commit()

            await websocket.send_json(
                {
                    "session_id": session_id,
                    "answer": result["answer"],
                    "admission_interest": result["admission_interest"],
                    "escalate_to_human": result["escalate_to_human"],
                }
            )

    except WebSocketDisconnect:
        pass
