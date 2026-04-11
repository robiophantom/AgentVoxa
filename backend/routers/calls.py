"""
Exotel calling router.
- /answer  : Exotel calls this when a call is received (NCCO response).
- /event   : Exotel call event webhook.
- /ws/{uuid}: WebSocket endpoint for Exotel audio stream (Pipecat STT/TTS).
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import select
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
from services.stt_local import get_local_stt

router = APIRouter(prefix="/calls", tags=["calls"])
settings = get_settings()
logger = logging.getLogger(__name__)

NO_INPUT_TIMEOUT_SECONDS = 8
MAX_TRANSCRIPT_CHARS = 500
MAX_RESPONSE_CHARS = 700
MAX_TTS_CHUNK_CHARS = 160
PCM_SAMPLE_RATE = 16000
PCM_BYTES_PER_SECOND = 32000
MAX_RAW_AUDIO_SECONDS = 12
MIN_RAW_AUDIO_SECONDS = 1


def _normalize_event(msg: dict) -> str:
    event = str(msg.get("event") or "").strip().lower()
    event_aliases = {
        "websocket:connected": "connected",
        "websocket_connected": "connected",
        "connection:open": "connected",
        "start": "connected",
        "connected": "connected",
        "websocket:disconnected": "disconnected",
        "websocket_disconnected": "disconnected",
        "connection:closed": "disconnected",
        "stop": "disconnected",
        "disconnected": "disconnected",
        "transcription": "transcription",
        "transcript": "transcription",
        "recognition": "transcription",
        "recognition:result": "transcription",
        "asr:result": "transcription",
        "speech:transcription": "transcription",
        "speech:final": "transcription",
        "speech:partial": "transcription_partial",
        "transcription:partial": "transcription_partial",
        "asr:partial": "transcription_partial",
        "media": "audio_media",
        "audio": "audio_media",
        "input_audio_buffer.speech_started": "speech_started",
        "input_audio_buffer.speech_stopped": "speech_stopped",
        "user:speech-started": "speech_started",
        "user:speech-stopped": "speech_stopped",
    }
    return event_aliases.get(event, event)


def _extract_transcript(msg: dict) -> str:
    body = msg.get("body") if isinstance(msg.get("body"), dict) else {}
    data = msg.get("data") if isinstance(msg.get("data"), dict) else {}
    payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}

    candidates = [
        msg.get("transcript"),
        msg.get("text"),
        msg.get("message"),
        msg.get("utterance"),
        msg.get("final_transcript"),
        body.get("transcript"),
        body.get("text"),
        body.get("utterance"),
        body.get("final_transcript"),
        body.get("speech"),
        data.get("transcript"),
        data.get("text"),
        payload.get("transcript"),
        payload.get("text"),
        payload.get("speech"),
    ]
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _is_final_transcript(msg: dict, normalized_event: str) -> bool:
    if normalized_event == "transcription_partial":
        return False
    if normalized_event == "transcription":
        if "is_final" in msg:
            return bool(msg.get("is_final"))
        if "final" in msg:
            return bool(msg.get("final"))
        body = msg.get("body") if isinstance(msg.get("body"), dict) else {}
        if "is_final" in body:
            return bool(body.get("is_final"))
        if "final" in body:
            return bool(body.get("final"))
        return True
    return False


def _infer_event_from_payload(msg: dict) -> str:
    normalized = _normalize_event(msg)
    if normalized:
        return normalized

    if _extract_transcript(msg):
        return "transcription"

    if isinstance(msg.get("media"), dict) or isinstance(msg.get("audio"), dict):
        return "audio_media"

    return "unknown"


def _extract_audio_bytes(msg: dict) -> bytes:
    media = msg.get("media") if isinstance(msg.get("media"), dict) else {}
    body = msg.get("body") if isinstance(msg.get("body"), dict) else {}
    payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}

    b64_candidates = [
        media.get("payload"),
        media.get("data"),
        body.get("audio"),
        body.get("payload"),
        payload.get("audio"),
        payload.get("payload"),
    ]
    for value in b64_candidates:
        if isinstance(value, str) and value:
            try:
                return base64.b64decode(value)
            except Exception:
                continue
    return b""


def _clamp_text(text: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _chunk_for_tts(text: str, chunk_size: int = MAX_TTS_CHUNK_CHARS) -> list[str]:
    clean = _clamp_text(text, MAX_RESPONSE_CHARS)
    if not clean:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", clean)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) > chunk_size:
            words = sentence.split()
            part = ""
            for word in words:
                proposal = (part + " " + word).strip()
                if len(proposal) <= chunk_size:
                    part = proposal
                else:
                    if part:
                        chunks.append(part)
                    part = word
            if part:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(part)
            continue

        proposal = (current + " " + sentence).strip()
        if len(proposal) <= chunk_size:
            current = proposal
        else:
            if current:
                chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return chunks


async def _send_play_audio(websocket: WebSocket, text: str) -> None:
    for chunk in _chunk_for_tts(text):
        await websocket.send_json({"event": "playAudio", "body": {"text": chunk}})


async def _stop_current_tts(websocket: WebSocket) -> None:
    # Different providers use different stop event names; send best-effort variants.
    for event_name in ("stopAudio", "clearAudio", "interrupt"):
        try:
            await websocket.send_json({"event": event_name})
        except Exception:
            return


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
        result = await db.execute(select(CallLog).where(CallLog.exotel_call_uuid == call_uuid))
        existing_log = result.scalar_one_or_none()
        if existing_log:
            existing_log.call_status = "started"
            if caller_number:
                existing_log.caller_number = caller_number
        else:
            db.add(
                CallLog(
                    exotel_call_uuid=call_uuid,
                    caller_number=caller_number,
                    call_status="started",
                )
            )
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
    transcript_buffer = ""
    raw_audio_buffer = bytearray()
    escalated = False
    admission_interest_detected = False
    tts_active = False
    user_spoke = False
    stt = get_local_stt()

    async def _handle_user_text(user_text: str) -> None:
        nonlocal admission_interest_detected, escalated, tts_active, user_spoke
        user_text = _clamp_text(user_text, MAX_TRANSCRIPT_CHARS)
        if not user_text:
            return

        user_spoke = True
        tts_active = False
        transcript_parts.append(f"User: {user_text}")

        result = await generate_answer(user_text)
        answer = _clamp_text(str(result.get("answer") or ""), MAX_RESPONSE_CHARS)
        if not answer:
            answer = (
                "I'm sorry, I don't have enough information to answer that right now. "
                "Please call our human staff."
            )
        transcript_parts.append(f"Agent: {answer}")

        if result["admission_interest"]:
            admission_interest_detected = True

        if result["escalate_to_human"]:
            escalated = True
            ncco = build_transfer_ncco(settings.human_staff_number)
            await websocket.send_json({"event": "transfer", "ncco": ncco})
            return

        await _send_play_audio(websocket, answer)
        tts_active = False

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
            try:
                data = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=NO_INPUT_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                if not user_spoke and not tts_active:
                    await _send_play_audio(
                        websocket,
                        "I am listening. Please tell me how I can help you.",
                    )
                    tts_active = True
                continue
            except WebSocketDisconnect:
                break
            except RuntimeError as exc:
                # Starlette raises this if receive() is called after disconnect.
                if "disconnect message has been received" in str(exc):
                    break
                raise

            if data.get("type") == "websocket.disconnect":
                break

            # Exotel sends binary audio frames
            if "bytes" in data:
                raw_chunk = data.get("bytes") or b""
                if raw_chunk:
                    raw_audio_buffer.extend(raw_chunk)
                    max_bytes = PCM_BYTES_PER_SECOND * MAX_RAW_AUDIO_SECONDS
                    if len(raw_audio_buffer) > max_bytes:
                        raw_audio_buffer[:] = raw_audio_buffer[-max_bytes:]

            # Exotel also sends JSON control messages
            elif "text" in data:
                try:
                    msg = json.loads(data["text"])
                except json.JSONDecodeError:
                    continue

                event = _infer_event_from_payload(msg)

                if event == "connected":
                    # Send a greeting TTS response
                    await _send_play_audio(
                        websocket,
                        "Hello! I am AgentVoxa. How can I help you today?",
                    )
                    tts_active = False

                elif event == "speech_started":
                    user_spoke = True
                    if tts_active:
                        await _stop_current_tts(websocket)
                        tts_active = False
                    raw_audio_buffer.clear()

                elif event == "speech_stopped":
                    tts_active = False
                    if stt.available and len(raw_audio_buffer) >= PCM_BYTES_PER_SECOND * MIN_RAW_AUDIO_SECONDS:
                        user_text = stt.transcribe_pcm16le(bytes(raw_audio_buffer), sample_rate=PCM_SAMPLE_RATE)
                        raw_audio_buffer.clear()
                        await _handle_user_text(user_text)

                elif event == "audio_media":
                    raw = _extract_audio_bytes(msg)
                    if raw:
                        raw_audio_buffer.extend(raw)
                        max_bytes = PCM_BYTES_PER_SECOND * MAX_RAW_AUDIO_SECONDS
                        if len(raw_audio_buffer) > max_bytes:
                            raw_audio_buffer[:] = raw_audio_buffer[-max_bytes:]

                elif event in {"transcription", "transcription_partial"}:
                    partial_text = _extract_transcript(msg)
                    if not partial_text:
                        continue

                    transcript_buffer = _clamp_text(partial_text, MAX_TRANSCRIPT_CHARS)
                    if not _is_final_transcript(msg, event):
                        continue

                    user_text = transcript_buffer
                    transcript_buffer = ""
                    if user_text:
                        await _handle_user_text(user_text)

                elif event == "disconnected":
                    break

                else:
                    logger.debug("Unhandled websocket message for call %s: %s", call_uuid, msg)

    except WebSocketDisconnect:
        pass
    finally:
        # Save call log
        full_transcript = "\n".join(transcript_parts)
        result = await db.execute(select(CallLog).where(CallLog.exotel_call_uuid == call_uuid))
        call_log = result.scalar_one_or_none()
        if call_log is None:
            call_log = CallLog(exotel_call_uuid=call_uuid)
            db.add(call_log)

        call_log.transcript = full_transcript
        call_log.call_status = "completed"
        call_log.admission_interest = (
            InterestLevel.high if admission_interest_detected else InterestLevel.none
        )
        call_log.escalated_to_human = escalated
        call_log.ended_at = datetime.now(timezone.utc)

        try:
            await db.commit()
        except Exception:
            logger.exception("Failed to save call log for %s", call_uuid)
            await db.rollback()
