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
    gemini_model_name: str = "gemini-2.5-flash"
    gemini_max_output_tokens: int = 4096

    # ElevenLabs
    elevenlabs_api_key: str = "sk_68578c809ada68a8e1f35b8f3c0e5ed5fbf0d7fe3f69fdb8"
    elevenlabs_voice_id: str = "cgSgspJ2msm6clMCkdW9"

    # Vapi
    vapi_api_key: str = ""
    vapi_webhook_secret: str = ""
    vapi_phone_number: str = ""
    human_staff_number: str = ""

    # Admin bootstrap
    admin_bootstrap_token: str = ""

    # Upload limits
    max_upload_size_mb: int = 50
    chunk_size_tokens: int = 512

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
