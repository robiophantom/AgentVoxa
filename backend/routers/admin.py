"""Admin dashboard router: logs, insights, user management."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import require_role
from models.logs import ChatLog, CallLog, InterestLevel
from models.user import User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"])


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
    return [
        {
            "id": l.id,
            "session_id": l.session_id,
            "user_message": l.user_message,
            "agent_response": l.agent_response,
            "admission_interest": l.admission_interest,
            "escalated_to_human": l.escalated_to_human,
            "contact_name": l.contact_name,
            "contact_email": l.contact_email,
            "contact_phone": l.contact_phone,
            "created_at": l.created_at,
        }
        for l in logs
    ]


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
            "vonage_call_uuid": l.vonage_call_uuid,
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
