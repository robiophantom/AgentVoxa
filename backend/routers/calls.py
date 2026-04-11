"""
Vonage calling router.
- /answer  : Vonage calls this when a call is received (NCCO response).
- /event   : Vonage call event webhook.
- /ws/{uuid}: WebSocket endpoint for Vonage audio stream (Pipecat STT/TTS).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_db
from models.logs import CallLog, InterestLevel
from services.agent import generate_answer
from services.vonage_service import (
    build_answer_ncco,
    build_hangup_ncco,
    build_transfer_ncco,
)

router = APIRouter(prefix="/calls", tags=["calls"])
settings = get_settings()


@router.post("/answer")
async def answer_call(request: Request):
    """Vonage Answer URL – returns NCCO to connect call to our WebSocket."""
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    call_uuid = body.get("uuid", str(uuid.uuid4()))

    ws_url = f"wss://{request.headers.get('host', 'localhost')}/api/calls/ws/{call_uuid}"
    ncco = build_answer_ncco(ws_url)
    return ncco


@router.post("/event")
async def call_event(request: Request, db: AsyncSession = Depends(get_db)):
    """Vonage Event URL – receives call lifecycle events."""
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    call_uuid = body.get("uuid", "unknown")
    status = body.get("status", "unknown")
    caller_number = body.get("from", None)

    if status == "started":
        existing_log = CallLog(
            vonage_call_uuid=call_uuid,
            caller_number=caller_number,
            call_status="started",
        )
        db.add(existing_log)
        await db.flush()

    return {"status": "ok"}


@router.websocket("/ws/{call_uuid}")
async def call_websocket(
    websocket: WebSocket,
    call_uuid: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Real-time audio WebSocket for Vonage call.
    Receives PCM audio from Vonage, uses Pipecat for STT,
    passes transcript to agent, then uses Pipecat TTS for response.

    NOTE: Pipecat pipeline integration is scaffolded here.
    Full Pipecat pipeline wiring (VAD, STT engine, TTS engine) should be
    completed when Pipecat configuration and API keys are finalised.
    """
    await websocket.accept()

    transcript_parts: list[str] = []
    escalated = False
    admission_interest_detected = False

    # ── Pipecat placeholder ──────────────────────────────────────────────────
    # TODO: Initialise Pipecat pipeline here:
    #   pipeline = Pipeline([
    #       VonageAudioSource(websocket),
    #       SileroVADAnalyzer(),
    #       DeepgramSTTService(api_key=...),
    #       AgentVoxaProcessor(generate_answer),
    #       CartesiaTTSService(api_key=...),
    #       VonageAudioSink(websocket),
    #   ])
    #   await pipeline.run()
    # ────────────────────────────────────────────────────────────────────────

    try:
        while True:
            data = await websocket.receive()

            # Vonage sends binary audio frames
            if "bytes" in data:
                # Placeholder: in production, feed to Pipecat VAD/STT
                pass

            # Vonage also sends JSON control messages
            elif "text" in data:
                try:
                    msg = json.loads(data["text"])
                except json.JSONDecodeError:
                    continue

                event = msg.get("event")

                if event == "websocket:connected":
                    # Send a greeting TTS response
                    await websocket.send_json(
                        {
                            "event": "playAudio",
                            "body": {
                                "text": "Hello! I am AgentVoxa. How can I help you today?",
                            },
                        }
                    )

                elif event == "transcription":
                    user_text = msg.get("transcript", "")
                    if user_text:
                        transcript_parts.append(f"User: {user_text}")
                        result = await generate_answer(user_text)
                        answer = result["answer"]
                        transcript_parts.append(f"Agent: {answer}")

                        if result["admission_interest"]:
                            admission_interest_detected = True

                        if result["escalate_to_human"]:
                            escalated = True
                            # Signal Vonage to transfer the call
                            ncco = build_transfer_ncco(settings.human_staff_number)
                            await websocket.send_json(
                                {"event": "transfer", "ncco": ncco}
                            )
                        else:
                            await websocket.send_json(
                                {"event": "playAudio", "body": {"text": answer}}
                            )

                elif event == "websocket:disconnected":
                    break

    except WebSocketDisconnect:
        pass
    finally:
        # Save call log
        full_transcript = "\n".join(transcript_parts)
        call_log = CallLog(
            vonage_call_uuid=call_uuid,
            transcript=full_transcript,
            call_status="completed",
            admission_interest=(
                InterestLevel.high if admission_interest_detected else InterestLevel.none
            ),
            escalated_to_human=escalated,
            ended_at=datetime.now(timezone.utc),
        )
        db.add(call_log)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
