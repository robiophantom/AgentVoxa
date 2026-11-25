"""Admin dashboard router: logs, insights, user management."""
import json
import logging
import httpx
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import require_role
from models.logs import ChatLog, CallLog, InterestLevel
from models.user import User, UserRole
from core.config import get_settings
from services.app_settings import get_all_app_settings, set_app_setting
from services.provider import FREE_TIER_MODELS

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()
logger = logging.getLogger(__name__)

class BulkDeleteRequest(BaseModel):
    ids: list[int]


class AppSettingsUpdate(BaseModel):
    answer_provider: str | None = None
    answer_model: str | None = None
    tts_provider: str | None = None
    elevenlabs_voice_id: str | None = None
    sarvam_voice_id: str | None = None
    max_upload_size_mb: int | None = None
    chunk_size_tokens: int | None = None


def _safe_json_load(text: str | None) -> dict:
    if not text:
        return {}
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _parse_chat_metadata(log: ChatLog) -> dict:
    metadata = _safe_json_load(log.retrieved_chunks)
    return {
        "summary": metadata.get("conversation_summary") if isinstance(metadata, dict) else None,
        "captured_data": (
            metadata.get("captured_data")
            if isinstance(metadata.get("captured_data"), dict)
            else {}
        ),
    }


def _json_or_default(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        logger.warning("Ignoring malformed JSON metadata in call log")
        return default


@router.get("/chat-logs")
async def get_chat_logs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
    page: int = 1,
    page_size: int = 50,
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(ChatLog).order_by(ChatLog.created_at.desc()).offset(offset).limit(page_size)
    )
    logs = result.scalars().all()
    response = []
    for log in logs:
        metadata = _parse_chat_metadata(log)
        response.append(
            {
                "id": log.id,
                "session_id": log.session_id,
                "user_message": log.user_message,
                "agent_response": log.agent_response,
                "conversation_summary": metadata["summary"],
                "captured_data": metadata["captured_data"],
                "admission_interest": log.admission_interest,
                "escalated_to_human": log.escalated_to_human,
                "contact_name": log.contact_name,
                "contact_email": log.contact_email,
                "contact_phone": log.contact_phone,
                "created_at": log.created_at,
            }
        )
    return response


@router.get("/chat-conversations")
async def get_chat_conversations(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(ChatLog).order_by(ChatLog.created_at.desc(), ChatLog.id.desc()))
    logs = result.scalars().all()

    sessions: dict[str, list[ChatLog]] = defaultdict(list)
    for log in logs:
        sessions[log.session_id].append(log)

    conversations = []
    for session_id, session_logs in sessions.items():
        latest = session_logs[0]
        metadata = _parse_chat_metadata(latest)

        conversations.append(
            {
                "session_id": session_id,
                "message_count": len(session_logs),
                "latest_at": latest.created_at,
                "summary": metadata["summary"],
                "captured_data": metadata["captured_data"],
                "admission_interest": any(
                    log.admission_interest == InterestLevel.high for log in session_logs
                ),
                "escalated_to_human": any(log.escalated_to_human for log in session_logs),
                "contact_name": latest.contact_name,
                "contact_email": latest.contact_email,
                "contact_phone": latest.contact_phone,
            }
        )

    conversations.sort(key=lambda item: item["latest_at"], reverse=True)
    return conversations


@router.get("/chat-conversations/{session_id}")
async def get_chat_conversation_detail(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(
        select(ChatLog)
        .where(ChatLog.session_id == session_id)
        .order_by(ChatLog.created_at.asc(), ChatLog.id.asc())
    )
    logs = result.scalars().all()

    if not logs:
        return {
            "session_id": session_id,
            "messages": [],
            "summary": None,
            "captured_data": {},
        }

    latest = logs[-1]
    metadata = _parse_chat_metadata(latest)
    return {
        "session_id": session_id,
        "summary": metadata["summary"],
        "captured_data": metadata["captured_data"],
        "contact_name": latest.contact_name,
        "contact_email": latest.contact_email,
        "contact_phone": latest.contact_phone,
        "messages": [
            {
                "id": log.id,
                "user_message": log.user_message,
                "agent_response": log.agent_response,
                "created_at": log.created_at,
                "admission_interest": log.admission_interest,
                "escalated_to_human": log.escalated_to_human,
            }
            for log in logs
        ],
    }

class BulkDeleteSessionsRequest(BaseModel):
    session_ids: list[str]

@router.delete("/chat-sessions", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_chat_sessions(
    payload: BulkDeleteSessionsRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    if not payload.session_ids:
        return
    await db.execute(delete(ChatLog).where(ChatLog.session_id.in_(payload.session_ids)))
    await db.commit()


@router.get("/call-logs")
async def get_call_logs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
    page: int = 1,
    page_size: int = 50,
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(CallLog).order_by(CallLog.started_at.desc()).offset(offset).limit(page_size)
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "vapi_call_id": l.vapi_call_id,
            "caller_number": l.caller_number,
            "transcript": l.transcript,
            "summary": l.summary,
            "duration_seconds": l.duration_seconds,
            "admission_interest": l.admission_interest,
            "escalated_to_human": l.escalated_to_human,
            "call_status": l.call_status,
            "started_at": l.started_at,
            "ended_at": l.ended_at,
            "tool_executions": _json_or_default(l.tool_executions, []),
            "failure_details": _json_or_default(l.failure_details, None),
            "latency_ms": l.latency_ms,
            "cost_metadata": _json_or_default(l.cost_metadata, None),
        }
        for l in logs
    ]


@router.get("/call-logs/{call_id}")
async def get_call_detail(
    call_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(CallLog).where(CallLog.id == call_id))
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return {
        "id": call.id,
        "vapi_call_id": call.vapi_call_id,
        "caller_number": call.caller_number,
        "transcript": call.transcript,
        "summary": call.summary,
        "duration_seconds": call.duration_seconds,
        "admission_interest": call.admission_interest,
        "escalated_to_human": call.escalated_to_human,
        "call_status": call.call_status,
        "started_at": call.started_at,
        "ended_at": call.ended_at,
        "tool_executions": _json_or_default(call.tool_executions, []),
        "failure_details": _json_or_default(call.failure_details, None),
        "latency_ms": call.latency_ms,
        "cost_metadata": _json_or_default(call.cost_metadata, None),
    }


@router.get("/tts/voices")
async def get_tts_voices(
    _: User = Depends(require_role(UserRole.admin)),
):
    voices = {"browser": [{"id": "browser", "name": "Browser default"}], "sarvam": [
        {"id": "meera", "name": "Meera"},
        {"id": "pavithra", "name": "Pavithra"},
        {"id": "maitreyi", "name": "Maitreyi"},
        {"id": "arvind", "name": "Arvind"},
        {"id": "amartya", "name": "Amartya"},
    ], "elevenlabs": []}

    if settings.elevenlabs_api_key:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.elevenlabs.io/v1/voices",
                    headers={"xi-api-key": settings.elevenlabs_api_key},
                )
                if response.status_code == 200:
                    voices["elevenlabs"] = [
                        {"id": voice["voice_id"], "name": voice.get("name", voice["voice_id"])}
                        for voice in response.json().get("voices", [])
                    ]
        except Exception:
            pass

    return voices


@router.delete("/call-logs", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_call_logs(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    if not payload.ids:
        return
    await db.execute(delete(CallLog).where(CallLog.id.in_(payload.ids)))
    await db.commit()


@router.get("/interested-users")
async def get_interested_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    """Return chat logs from users who expressed interest in admission."""
    result = await db.execute(
        select(ChatLog)
        .where(ChatLog.admission_interest == InterestLevel.high)
        .order_by(ChatLog.created_at.desc())
    )
    logs = result.scalars().all()
    
    seen_sessions = set()
    unique_logs = []
    for l in logs:
        if l.session_id not in seen_sessions:
            seen_sessions.add(l.session_id)
            unique_logs.append({
                "session_id": l.session_id,
                "contact_name": l.contact_name,
                "contact_email": l.contact_email,
                "contact_phone": l.contact_phone,
                "sample_message": l.user_message[:120],
                "created_at": l.created_at,
            })
            
    return unique_logs


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    chat_count = await db.scalar(select(func.count()).select_from(ChatLog))
    call_count = await db.scalar(select(func.count()).select_from(CallLog))
    interested_count = await db.scalar(
        select(func.count()).select_from(ChatLog).where(
            ChatLog.admission_interest == InterestLevel.high
        )
    )
    return {
        "total_chats": chat_count,
        "total_calls": call_count,
        "interested_in_admission": interested_count,
    }


@router.get("/settings")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    values = await get_all_app_settings(db)
    return {
        "settings": values,
        "providers": {
            "answer": {
                "gemini": FREE_TIER_MODELS["gemini"],
                "groq": FREE_TIER_MODELS["groq"],
            },
            "tts": ["browser", "elevenlabs", "sarvam"],
        },
    }


@router.put("/settings")
async def update_settings(
    payload: AppSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    allowed_answers = {
        "groq": FREE_TIER_MODELS["groq"],
        "gemini": FREE_TIER_MODELS["gemini"],
    }
    updates = payload.model_dump(exclude_none=True)

    if "answer_provider" in updates and updates["answer_provider"] not in allowed_answers:
        raise HTTPException(status_code=400, detail="Unsupported answer provider")
    if "answer_model" in updates:
        current = await get_all_app_settings(db)
        provider = updates.get("answer_provider") or current["answer_provider"]
        if updates["answer_model"] not in allowed_answers.get(provider, []):
            raise HTTPException(status_code=400, detail="Model is not available for this provider")
    if "tts_provider" in updates and updates["tts_provider"] not in {"browser", "elevenlabs", "sarvam"}:
        raise HTTPException(status_code=400, detail="Unsupported TTS provider")
    if "max_upload_size_mb" in updates and not 1 <= updates["max_upload_size_mb"] <= 50:
        raise HTTPException(status_code=400, detail="Upload limit must be between 1 and 50 MB")
    if "chunk_size_tokens" in updates and not 128 <= updates["chunk_size_tokens"] <= 2048:
        raise HTTPException(status_code=400, detail="Chunk size must be between 128 and 2048 tokens")

    for key, value in updates.items():
        await set_app_setting(db, key, str(value))

    return await get_settings(db=db, _=_)
