"""Gemini-powered agent: builds prompt from retrieved chunks, answers queries."""
from __future__ import annotations

import logging
import re

import google.generativeai as genai

from core.config import get_settings
from services.rag import hybrid_search

settings = get_settings()
logger = logging.getLogger(__name__)

_CANNOT_ANSWER_PHRASES = [
    "i don't know",
    "i do not know",
    "cannot answer",
    "not sure",
    "no information",
    "outside my knowledge",
]

SYSTEM_PROMPT = """You are AgentVoxa, a helpful AI receptionist for a college/university.
Your role is to assist students and prospective applicants with queries about courses,
admissions, fees, facilities, scholarships, and campus life.

Guidelines:
- Be warm, professional, and concise.
- Answer only based on the context provided below.
- If the context does not contain enough information to answer confidently, say exactly:
  "I'm sorry, I don't have enough information to answer that. Please call our human staff."
- If the caller/user seems interested in admission, ask for their name, email, and phone number.
- Do not fabricate information.
- Do not write # from chunks in the output.
"""


def _configure_gemini() -> None:
    if settings.gemini_api_key:
        genai.configure(api_key=settings.gemini_api_key)


_configure_gemini()


def _build_context(chunks: list[dict]) -> str:
    if not chunks:
        return "No relevant documents found."
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[{i}] (from {c.get('filename','?')}): {c['text']}")
    return "\n\n".join(parts)


def _build_chat_history(chat_history: list[dict] | None) -> str:
    if not chat_history:
        return "No prior conversation."

    formatted: list[str] = []
    for turn in chat_history[-12:]:
        role = turn.get("role", "user")
        content = str(turn.get("content", "")).strip()
        if not content:
            continue
        speaker = "User" if role == "user" else "Assistant"
        formatted.append(f"{speaker}: {content}")

    return "\n".join(formatted) if formatted else "No prior conversation."


def _detect_admission_interest(text: str) -> bool:
    keywords = [
        "admission",
        "apply",
        "application",
        "enroll",
        "enrollment",
        "join",
        "fee structure",
        "scholarship",
        "intake",
        "course",
    ]
    lower = text.lower()
    return any(kw in lower for kw in keywords)


def _cannot_answer(response: str) -> bool:
    lower = response.lower()
    return any(phrase in lower for phrase in _CANNOT_ANSWER_PHRASES)


def _fallback_from_chunks(chunks: list[dict]) -> str:
    """Provide a deterministic answer when LLM call fails."""
    if not chunks:
        return (
            "I'm sorry, I don't have enough information to answer that right now. "
            "Please call our human staff."
        )

    lines: list[str] = []
    for idx, chunk in enumerate(chunks[:3], 1):
        snippet = str(chunk.get("text", "")).strip().replace("\n", " ")
        if len(snippet) > 220:
            snippet = f"{snippet[:217].rstrip()}..."
        if snippet:
            lines.append(f"{idx}. {snippet}")

    if not lines:
        return (
            "I'm sorry, I don't have enough information to answer that right now. "
            "Please call our human staff."
        )

    return "Here is what I found in our documents:\n" + "\n".join(lines)


async def generate_answer(
    user_message: str,
    chat_history: list[dict] | None = None,
) -> dict:
    """
    Returns:
        {
            "answer": str,
            "chunks": list[dict],
            "admission_interest": bool,
            "escalate_to_human": bool,
        }
    """
    chunks = await hybrid_search(user_message, top_k=5)
    context = _build_context(chunks)
    history_text = _build_chat_history(chat_history)

    prompt = f"""{SYSTEM_PROMPT}

--- CONTEXT START ---
{context}
--- CONTEXT END ---

--- CHAT HISTORY START ---
{history_text}
--- CHAT HISTORY END ---

User query: {user_message}

Answer:"""

    answer = ""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        answer = response.text.strip()
    except Exception as exc:
        logger.exception("Gemini response generation failed")
        answer = _fallback_from_chunks(chunks)

    escalate = _cannot_answer(answer)
    admission_interest = _detect_admission_interest(user_message) or _detect_admission_interest(answer)

    if escalate:
        answer += f"\n\nFor immediate help, please call our human staff at {settings.human_staff_number}."

    return {
        "answer": answer,
        "chunks": chunks,
        "admission_interest": admission_interest,
        "escalate_to_human": escalate,
    }
