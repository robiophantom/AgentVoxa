"""Admin dashboard router: logs, insights, user management."""
import json
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import require_role
from models.logs import ChatLog, CallLog, InterestLevel
from models.user import User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"])


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
        }
        for l in logs
    ]


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
    return [
        {
            "session_id": l.session_id,
            "contact_name": l.contact_name,
            "contact_email": l.contact_email,
            "contact_phone": l.contact_phone,
            "sample_message": l.user_message[:120],
            "created_at": l.created_at,
        }
        for l in logs
    ]


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
