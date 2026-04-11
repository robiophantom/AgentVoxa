"""Gemini-powered agent: builds prompt from retrieved chunks, answers queries."""
from __future__ import annotations

import re

import google.generativeai as genai

from core.config import get_settings
from services.rag import hybrid_search

settings = get_settings()

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

    prompt = f"""{SYSTEM_PROMPT}

--- CONTEXT START ---
{context}
--- CONTEXT END ---

User query: {user_message}

Answer:"""

    answer = ""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        answer = response.text.strip()
    except Exception as exc:
        answer = (
            "I'm sorry, I'm experiencing a technical issue right now. "
            "Please call our human staff for assistance."
        )

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
