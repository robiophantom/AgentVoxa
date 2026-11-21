"""Chat router: REST endpoint + WebSocket for real-time chat."""
from __future__ import annotations

import json
import re
import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Response
import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.logs import ChatLog, InterestLevel
from services.agent import generate_answer
from services.app_settings import get_app_setting

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None


class ContactCaptureRequest(BaseModel):
    session_id: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None


def _safe_json_load(text: str | None) -> dict:
    if not text:
        return {}
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _get_log_captured_data(log: ChatLog) -> dict[str, str]:
    metadata = _safe_json_load(log.retrieved_chunks)
    captured_data = metadata.get("captured_data")
    return captured_data if isinstance(captured_data, dict) else {}


def _build_retrieval_metadata(
    chunks: list[dict],
    conversation_summary: str,
    captured_data: dict[str, str],
) -> str:
    return json.dumps(
        {
            "chunks": [c["text"][:200] for c in chunks],
            "conversation_summary": conversation_summary,
            "captured_data": captured_data,
        }
    )


def _extract_contact_data(
    existing_logs: Sequence[ChatLog],
    contact_name: str | None,
    contact_email: str | None,
    contact_phone: str | None,
    new_contact_data: dict[str, str] | None = None,
) -> dict[str, str]:
    extracted: dict[str, str] = {}

    if contact_name and len(contact_name.strip()) >= 2:
        extracted["name"] = contact_name.strip()
    if contact_email:
        email = contact_email.strip()
        if re.match(r"^[^@\s]+@[^\s@]+\.[^\s@]+$", email):
            extracted["email"] = email
    if contact_phone:
        phone = re.sub(r"[^\d+]", "", contact_phone)
        if 10 <= sum(char.isdigit() for char in phone) <= 15:
            extracted["phone"] = phone

    if new_contact_data:
        for k in ("name", "email", "phone"):
            val = new_contact_data.get(k)
            if not val or k in extracted:
                continue
            value = str(val).strip()
            if k == "name" and len(value) >= 2:
                extracted[k] = value
            elif k == "email" and re.match(r"^[^@\s]+@[^\s@]+\.[^\s@]+$", value):
                extracted[k] = value
            elif k == "phone":
                phone = re.sub(r"[^\d+]", "", value)
                if 10 <= sum(char.isdigit() for char in phone) <= 15:
                    extracted[k] = phone

    for log in reversed(existing_logs):
        payload = _get_log_captured_data(log)
        for key in ("name", "email", "phone"):
            if key not in extracted and payload.get(key):
                extracted[key] = str(payload[key]).strip()
        if len(extracted) == 3:
            break

    return extracted


def _build_conversation_summary(
    existing_logs: Sequence[ChatLog],
    user_message: str,
    answer: str,
    admission_interest: bool,
    escalated_to_human: bool,
    extracted_data: dict[str, str],
) -> str:
    turns = [*existing_logs[-3:], None]
    recap_bits: list[str] = []

    for turn in turns:
        if turn is None:
            question = user_message.strip()
            response = answer.strip()
        else:
            question = turn.user_message.strip()
            response = turn.agent_response.strip()

        if question:
            recap_bits.append(f"Q: {question[:120]}")
        if response:
            recap_bits.append(f"A: {response[:120]}")

    status_parts = []
    if admission_interest:
        status_parts.append("admission interest detected")
    if escalated_to_human:
        status_parts.append("escalation requested")
    if extracted_data:
        keys = ", ".join(sorted(extracted_data.keys()))
        status_parts.append(f"captured fields: {keys}")

    summary = " | ".join(recap_bits[:8])
    if status_parts:
        summary = f"{summary} | {'; '.join(status_parts)}"

    return summary[:1000]


async def _fetch_session_logs(db: AsyncSession, session_id: str) -> list[ChatLog]:
    result = await db.execute(
        select(ChatLog)
        .where(ChatLog.session_id == session_id)
        .order_by(ChatLog.created_at.asc(), ChatLog.id.asc())
        .limit(50)
    )
    return list(result.scalars().all())


@router.post("/")
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    session_id = payload.session_id or str(uuid.uuid4())
    existing_logs = await _fetch_session_logs(db, session_id)
    chat_history: list[dict[str, str]] = []
    for log in existing_logs:
        chat_history.append({"role": "user", "content": log.user_message})
        chat_history.append({"role": "assistant", "content": log.agent_response})

    existing_extracted = _extract_contact_data(
        existing_logs,
        payload.contact_name,
        payload.contact_email,
        payload.contact_phone,
    )
    result = await generate_answer(payload.message, chat_history=chat_history, extracted_data=existing_extracted)
    
    extracted_data = _extract_contact_data(
        existing_logs,
        payload.contact_name,
        payload.contact_email,
        payload.contact_phone,
        result.get("contact_info", {})
    )

    if len(extracted_data) >= 1:
        result["admission_interest"] = False

    conversation_summary = _build_conversation_summary(
        existing_logs,
        payload.message,
        result["answer"],
        result["admission_interest"],
        result["escalate_to_human"],
        extracted_data,
    )

    log = ChatLog(
        session_id=session_id,
        user_message=payload.message,
        agent_response=result["answer"],
        retrieved_chunks=_build_retrieval_metadata(
            result["chunks"],
            conversation_summary,
            extracted_data,
        ),
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
        "conversation_summary": conversation_summary,
        "captured_data": extracted_data,
    }


@router.post("/contact")
async def capture_contact(payload: ContactCaptureRequest, db: AsyncSession = Depends(get_db)):
    existing_logs = await _fetch_session_logs(db, payload.session_id)
    extracted_data = _extract_contact_data(
        existing_logs,
        payload.contact_name,
        payload.contact_email,
        payload.contact_phone,
    )

    summary = _build_conversation_summary(
        existing_logs,
        "User provided contact details.",
        "Contact details captured for follow-up.",
        True,
        False,
        extracted_data,
    )

    log = ChatLog(
        session_id=payload.session_id,
        user_message="User provided contact details.",
        agent_response="Contact details captured for follow-up.",
        retrieved_chunks=_build_retrieval_metadata([], summary, extracted_data),
        admission_interest=InterestLevel.high,
        escalated_to_human=False,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
    )
    db.add(log)
    await db.flush()
    await db.commit()

    return {
        "session_id": payload.session_id,
        "saved": True,
        "captured_data": extracted_data,
        "conversation_summary": summary,
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
            existing_logs = await _fetch_session_logs(db, session_id)
            chat_history: list[dict[str, str]] = []
            for log in existing_logs:
                chat_history.append({"role": "user", "content": log.user_message})
                chat_history.append({"role": "assistant", "content": log.agent_response})

            existing_extracted = _extract_contact_data(
                existing_logs,
                payload.get("contact_name"),
                payload.get("contact_email"),
                payload.get("contact_phone"),
            )
            result = await generate_answer(message, chat_history=chat_history, extracted_data=existing_extracted)
            
            extracted_data = _extract_contact_data(
                existing_logs,
                payload.get("contact_name"),
                payload.get("contact_email"),
                payload.get("contact_phone"),
                result.get("contact_info", {})
            )

            if len(extracted_data) >= 1:
                result["admission_interest"] = False

            conversation_summary = _build_conversation_summary(
                existing_logs,
                message,
                result["answer"],
                result["admission_interest"],
                result["escalate_to_human"],
                extracted_data,
            )

            log = ChatLog(
                session_id=session_id,
                user_message=message,
                agent_response=result["answer"],
                retrieved_chunks=_build_retrieval_metadata(
                    result["chunks"],
                    conversation_summary,
                    extracted_data,
                ),
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
                    "conversation_summary": conversation_summary,
                    "captured_data": extracted_data,
                }
            )

    except WebSocketDisconnect:
        pass


@router.get("/tts")
async def get_tts(
    text: str,
    voice_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    from core.config import get_settings
    settings = get_settings()
    provider = await get_app_setting(db, "tts_provider")
    if provider == "browser":
        return Response(status_code=204)

    if provider == "elevenlabs":
        if not settings.elevenlabs_api_key:
            return Response(status_code=503, content="ElevenLabs is not configured")
        selected_voice = voice_id or await get_app_setting(db, "elevenlabs_voice_id") or settings.elevenlabs_voice_id
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{selected_voice}/stream"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": settings.elevenlabs_api_key,
        }
        data = {"text": text, "model_id": "eleven_multilingual_v2"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=data, headers=headers)
            if response.status_code == 200:
                return Response(content=response.content, media_type="audio/mpeg")
            return Response(status_code=response.status_code, content=response.text)

    if provider == "sarvam":
        if not settings.sarvam_api_key:
            return Response(status_code=503, content="Sarvam AI is not configured")
        selected_voice = voice_id or await get_app_setting(db, "sarvam_voice_id")
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.sarvam.ai/text-to-speech",
                headers={"api-subscription-key": settings.sarvam_api_key, "Content-Type": "application/json"},
                json={"text": text, "target_language_code": "en-IN", "speaker": selected_voice or "meera"},
            )
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "audio/wav")
                return Response(content=response.content, media_type=content_type)
            return Response(status_code=response.status_code, content=response.text)

    return Response(status_code=503, content="The selected TTS provider is unavailable")
