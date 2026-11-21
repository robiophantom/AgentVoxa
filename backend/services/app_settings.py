from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from models.app_config import AppSetting

settings = get_settings()
_cache: dict[str, tuple[float, str]] = {}
_CACHE_TTL_SECONDS = 10


def _defaults() -> dict[str, str]:
    return {
        "answer_provider": "groq",
        "answer_model": "openai/gpt-oss-120b",
        "tts_provider": "elevenlabs",
        "elevenlabs_voice_id": settings.elevenlabs_voice_id,
        "sarvam_voice_id": settings.sarvam_voice_id,
        "max_upload_size_mb": str(settings.max_upload_size_mb),
        "chunk_size_tokens": str(settings.chunk_size_tokens),
    }


async def get_app_setting(db: AsyncSession, key: str) -> str:
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    result = await db.execute(select(AppSetting.value).where(AppSetting.key == key))
    value = result.scalar_one_or_none()
    resolved = value if value is not None else _defaults().get(key, "")
    _cache[key] = (now, resolved)
    return resolved


async def get_answer_config(db: AsyncSession) -> tuple[str, str]:
    provider = await get_app_setting(db, "answer_provider")
    model = await get_app_setting(db, "answer_model")
    return provider or "groq", model or "openai/gpt-oss-120b"


async def set_app_setting(db: AsyncSession, key: str, value: str) -> None:
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    _cache.pop(key, None)
    await db.commit()


async def get_all_app_settings(db: AsyncSession) -> dict[str, str]:
    result = await db.execute(select(AppSetting))
    stored = {row.key: row.value for row in result.scalars().all()}
    defaults = _defaults()
    defaults.update(stored)
    return defaults
