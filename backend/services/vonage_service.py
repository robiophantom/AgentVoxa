"""
Vonage call handling service.
Handles NCCO responses for inbound calls and WebSocket audio bridging via Pipecat.
"""
from __future__ import annotations

import json

from core.config import get_settings

settings = get_settings()


def build_answer_ncco(websocket_url: str) -> list[dict]:
    """
    Return a Vonage NCCO that connects the call audio stream to our WebSocket endpoint.
    The WebSocket endpoint uses Pipecat for real-time STT/TTS processing.
    """
    return [
        {
            "action": "talk",
            "text": "Hello! You have reached AgentVoxa, your AI receptionist. Please hold while I connect you.",
            "language": "en-US",
            "style": 0,
        },
        {
            "action": "connect",
            "endpoint": [
                {
                    "type": "websocket",
                    "uri": websocket_url,
                    "content-type": "audio/l16;rate=16000",
                    "headers": {
                        "service": "agentvoxa",
                    },
                }
            ],
        },
    ]


def build_transfer_ncco(to_number: str) -> list[dict]:
    """NCCO to transfer call to human staff."""
    return [
        {
            "action": "talk",
            "text": "Please hold while I transfer you to a human staff member.",
            "language": "en-US",
        },
        {
            "action": "connect",
            "from": settings.vonage_phone_number,
            "endpoint": [{"type": "phone", "number": to_number}],
        },
    ]


def build_hangup_ncco(message: str = "Thank you for calling. Goodbye!") -> list[dict]:
    return [{"action": "talk", "text": message, "language": "en-US"}]
