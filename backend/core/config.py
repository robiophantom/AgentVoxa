from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "AgentVoxa"
    secret_key: str = "change_this_to_a_very_long_random_secret_key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+asyncpg://agentvoxa:agentvoxa_secret@localhost:5432/agentvoxa_db"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "agentvoxa_docs"
    embedding_dim: int = 384  # all-MiniLM-L6-v2

    # Gemini
    gemini_api_key: str = ""

    # ElevenLabs (for TTS)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"  # Default voice ID (Bella)

    # Exotel
    exotel_api_key: str = ""
    exotel_api_secret: str = ""
    exotel_application_id: str = ""
    exotel_private_key_path: str = "./exotel_private.key"
    exotel_phone_number: str = ""
    human_staff_number: str = ""

    # Upload limits
    max_upload_size_mb: int = 50
    chunk_size_tokens: int = 512

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
