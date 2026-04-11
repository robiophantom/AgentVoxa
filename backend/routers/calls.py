"""
Exotel calling router.
- /answer  : Exotel calls this when a call is received (NCCO response).
- /event   : Exotel call event webhook.
- /ws/{uuid}: WebSocket endpoint for Exotel audio stream (Pipecat STT/TTS).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_db
from models.logs import CallLog, InterestLevel
from services.agent import generate_answer
from services.exotel_service import (
    build_answer_ncco,
    build_hangup_ncco,
    build_transfer_ncco,
)

router = APIRouter(prefix="/calls", tags=["calls"])
settings = get_settings()


async def _extract_webhook_payload(request: Request) -> dict:
    """Best-effort parser for Exotel webhooks (JSON, form-encoded, or querystring)."""
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        try:
            payload = await request.json()
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass

    if (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    ):
        try:
            form = await request.form()
            return dict(form)
        except Exception:
            pass

    # Fallback: Exotel (or proxies) may send webhook fields as query params.
    return dict(request.query_params)


def _build_public_ws_url(request: Request, call_uuid: str) -> str:
    """Create a websocket URL that remains valid when served behind a tunnel/proxy."""
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")

    if forwarded_host:
        proto = (forwarded_proto or "https").split(",")[0].strip().lower()
        ws_scheme = "wss" if proto == "https" else "ws"
        host = forwarded_host.split(",")[0].strip()
        return f"{ws_scheme}://{host}/api/calls/ws/{call_uuid}"

    # When behind a tunnel, Host is usually the public tunnel domain.
    host = request.headers.get("host")
    if host:
        proto = (forwarded_proto or request.url.scheme or "https").split(",")[0].strip().lower()
        ws_scheme = "wss" if proto == "https" else "ws"
        return f"{ws_scheme}://{host}/api/calls/ws/{call_uuid}"

    parsed_backend = urlparse(settings.backend_url)
    if parsed_backend.scheme and parsed_backend.netloc:
        ws_scheme = "wss" if parsed_backend.scheme == "https" else "ws"
        return f"{ws_scheme}://{parsed_backend.netloc}/api/calls/ws/{call_uuid}"

    return f"wss://localhost:8000/api/calls/ws/{call_uuid}"


@router.api_route("/answer", methods=["GET", "POST"])
async def answer_call(request: Request):
    """Exotel Answer URL – returns NCCO to connect call to our WebSocket."""
    body = await _extract_webhook_payload(request)
    call_uuid = str(body.get("uuid") or body.get("call_uuid") or uuid.uuid4())

    ws_url = _build_public_ws_url(request, call_uuid)
    ncco = build_answer_ncco(ws_url)
    return ncco


@router.api_route("/event", methods=["GET", "POST"])
async def call_event(request: Request, db: AsyncSession = Depends(get_db)):
    """Exotel Event URL – receives call lifecycle events."""
    body = await _extract_webhook_payload(request)
    call_uuid = body.get("uuid", "unknown")
    status = body.get("status", "unknown")
    caller_number = body.get("from", None)

    if status == "started":
        existing_log = CallLog(
            exotel_call_uuid=call_uuid,
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
    Real-time audio WebSocket for Exotel call.
    Receives PCM audio from Exotel, uses Pipecat for STT,
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
    #       ExotelAudioSource(websocket),
    #       SileroVADAnalyzer(),
    #       WhisperSTTService(model="base"), # Runs locally, completely free
    #       AgentVoxaProcessor(generate_answer),
    #       ElevenLabsTTSService(
    #           api_key=settings.elevenlabs_api_key, 
    #           voice_id=settings.elevenlabs_voice_id
    #       ),
    #       ExotelAudioSink(websocket),
    #   ])
    #   await pipeline.run()
    # ────────────────────────────────────────────────────────────────────────

    try:
        while True:
            data = await websocket.receive()

            # Exotel sends binary audio frames
            if "bytes" in data:
                # Placeholder: in production, feed to Pipecat VAD/STT
                pass

            # Exotel also sends JSON control messages
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
                            # Signal Exotel to transfer the call
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
            exotel_call_uuid=call_uuid,
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
