from __future__ import annotations

import logging
from typing import Awaitable, Callable

import httpx
import google.generativeai as genai

from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

FREE_TIER_MODELS = {
    "groq": [
        "openai/gpt-oss-120b",
        "llama-3.1-8b-instant",
    ],
    "gemini": [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ],
}


async def generate_with_groq(prompt: str, model: str) -> str:
    if not settings.groq_api_key:
        raise RuntimeError("Groq API key is not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_completion_tokens": settings.gemini_max_output_tokens,
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Groq request failed ({response.status_code}): {response.text}")
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


async def generate_with_gemini(prompt: str, model: str) -> str:
    if not settings.gemini_api_key:
        raise RuntimeError("Gemini API key is not configured")
    genai.configure(api_key=settings.gemini_api_key)
    generative_model = genai.GenerativeModel(model)
    response = await _to_thread(generative_model.generate_content, prompt)
    return response.text.strip()


async def _to_thread(func: Callable, *args) -> object:
    import asyncio

    return await asyncio.to_thread(func, *args)


async def generate_answer_with_provider(prompt: str, provider: str, model: str) -> str:
    providers: dict[str, Callable[[str, str], Awaitable[str]]] = {
        "groq": generate_with_groq,
        "gemini": generate_with_gemini,
    }
    if provider not in providers:
        raise RuntimeError(f"Unsupported answer provider: {provider}")

    try:
        return await providers[provider](prompt, model)
    except Exception as primary_error:
        logger.warning("%s answer provider failed: %s", provider, primary_error)
        fallback = "gemini" if provider == "groq" else "groq"
        fallback_model = (
            settings.gemini_model_name
            if fallback == "gemini"
            else settings.groq_model_name
        )
        try:
            return await providers[fallback](prompt, fallback_model)
        except Exception:
            logger.exception("Answer provider fallback also failed")
            raise primary_error
