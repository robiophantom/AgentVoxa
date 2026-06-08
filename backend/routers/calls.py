"""
Vapi calling router.
- /vapi/webhook : Handles Vapi tool calls and end-of-call reports.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response, HTTPException
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_db
from models.logs import CallLog, InterestLevel
from services.agent import generate_answer

router = APIRouter(prefix="/calls", tags=["calls"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.post("/vapi/webhook")
async def vapi_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handles webhooks from Vapi, including Tool Calls and End-of-Call reports.
    """
    try:
        payload = await request.json()
    except Exception:
        return {"error": "Invalid JSON"}

    message = payload.get("message", {})
    msg_type = message.get("type")
    call_info = message.get("call", {})
    vapi_call_id = call_info.get("id") or "unknown_call_id"

    # Handle end-of-call report (saving transcript, summary, etc.)
    if msg_type == "end-of-call-report":
        await _handle_end_of_call(call_info, db, vapi_call_id)
        return {"status": "ok"}
    
    # Handle status updates (e.g. ringing, connected)
    elif msg_type == "status-update":
        status = call_info.get("status", "unknown")
        await _update_call_status(call_info, db, vapi_call_id, status)
        return {"status": "ok"}
    
    # Handle tool calls (Vapi STT -> Query -> Tool Call -> RAG -> LLM -> Vapi TTS)
    elif msg_type == "tool-calls":
        results = await _handle_tool_calls(message, db, vapi_call_id)
        return {"results": results}

    # Acknowledge other event types silently
    return {"status": "ignored"}


async def _handle_tool_calls(message: dict, db: AsyncSession, vapi_call_id: str) -> list[dict]:
    results = []
    tool_with_call_list = message.get("toolWithToolCallList", [])
    
    for item in tool_with_call_list:
        tool_call = item.get("toolCall", {})
        tool_call_id = tool_call.get("id")
        arguments = tool_call.get("arguments", {})
        query = arguments.get("query", "")
        
        if not query:
            results.append({
                "toolCallId": tool_call_id,
                "result": "I didn't catch that. Could you repeat?"
            })
            continue

        # Use our RAG agent to generate the answer
        agent_res = await generate_answer(query)
        answer = agent_res.get("answer", "I'm not sure how to answer that.")
        admission_interest = agent_res.get("admission_interest", False)
        escalate = agent_res.get("escalate_to_human", False)

        # We can opportunistically update the call log if admission interest or escalation is detected.
        # This ensures real-time flag updates before the call ends.
        if admission_interest or escalate:
            await _update_call_flags(db, vapi_call_id, admission_interest, escalate)

        results.append({
            "toolCallId": tool_call_id,
            "result": answer
        })
        
    return results


async def _update_call_status(call_info: dict, db: AsyncSession, vapi_call_id: str, status: str):
    customer = call_info.get("customer", {})
    caller_number = customer.get("number")
    
    result = await db.execute(select(CallLog).where(CallLog.vapi_call_id == vapi_call_id))
    log = result.scalar_one_or_none()
    
    if log:
        log.call_status = status
        if caller_number:
            log.caller_number = caller_number
    else:
        db.add(
            CallLog(
                vapi_call_id=vapi_call_id,
                caller_number=caller_number,
                call_status=status
            )
        )
    try:
        await db.commit()
    except Exception:
        logger.exception("Failed to update call status for %s", vapi_call_id)
        await db.rollback()


async def _update_call_flags(db: AsyncSession, vapi_call_id: str, admission_interest: bool, escalate: bool):
    result = await db.execute(select(CallLog).where(CallLog.vapi_call_id == vapi_call_id))
    log = result.scalar_one_or_none()
    
    if log:
        if admission_interest:
            log.admission_interest = InterestLevel.high
        if escalate:
            log.escalated_to_human = True
        try:
            await db.commit()
        except Exception:
            await db.rollback()


async def _handle_end_of_call(call_info: dict, db: AsyncSession, vapi_call_id: str):
    customer = call_info.get("customer", {})
    caller_number = customer.get("number")
    transcript = call_info.get("transcript") or call_info.get("artifact", {}).get("transcript")
    summary = call_info.get("summary") or call_info.get("analysis", {}).get("summary")
    status = call_info.get("status", "completed")
    
    # Try to parse timestamps
    started_at_str = call_info.get("startedAt")
    ended_at_str = call_info.get("endedAt")
    duration_seconds = call_info.get("costBreakdown", {}).get("duration")

    result = await db.execute(select(CallLog).where(CallLog.vapi_call_id == vapi_call_id))
    log = result.scalar_one_or_none()
    
    if not log:
        log = CallLog(vapi_call_id=vapi_call_id, caller_number=caller_number)
        db.add(log)
        
    log.call_status = status
    if transcript:
        log.transcript = transcript
    if summary:
        log.summary = summary
    if caller_number:
        log.caller_number = caller_number
    if duration_seconds:
        log.duration_seconds = duration_seconds
    log.ended_at = datetime.now(timezone.utc)
    
    try:
        await db.commit()
    except Exception:
        logger.exception("Failed to save end-of-call report for %s", vapi_call_id)
        await db.rollback()

@router.post("/vapi/sync")
async def sync_vapi_calls(db: AsyncSession = Depends(get_db)):
    """
    Syncs missing calls from Vapi API directly.
    """
    if not settings.vapi_api_key:
        raise HTTPException(status_code=400, detail="Vapi API key not configured")
        
    headers = {"Authorization": f"Bearer {settings.vapi_api_key}"}
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("https://api.vapi.ai/call", headers=headers, timeout=15.0)
            resp.raise_for_status()
            calls = resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch calls from Vapi: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch calls from Vapi")
            
    synced_count = 0
    for call in calls:
        vapi_call_id = call.get("id")
        if not vapi_call_id:
            continue
            
        result = await db.execute(select(CallLog).where(CallLog.vapi_call_id == vapi_call_id))
        log = result.scalar_one_or_none()
        
        if log:
            continue
            
        status = call.get("status", "completed")
        transcript = call.get("transcript")
        summary = call.get("summary")
        customer = call.get("customer", {})
        caller_number = customer.get("number")
        
        cost_breakdown = call.get("costBreakdown", {})
        duration = cost_breakdown.get("duration", 0)
        
        log = CallLog(
            vapi_call_id=vapi_call_id,
            caller_number=caller_number,
            call_status=status,
            transcript=transcript,
            summary=summary,
            duration_seconds=duration,
        )
        if call.get("endedAt"):
            try:
                ended = call["endedAt"].replace("Z", "+00:00")
                log.ended_at = datetime.fromisoformat(ended)
            except Exception:
                pass
                
        db.add(log)
        synced_count += 1
        
    if synced_count > 0:
        try:
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to commit synced calls: {e}")
            await db.rollback()
            raise HTTPException(status_code=500, detail="Failed to save synced calls")
            
    return {"status": "ok", "synced": synced_count}
