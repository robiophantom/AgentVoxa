from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "AgentVoxa"
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    # Database
    database_url: str = ""

    # Qdrant
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "agentvoxa_docs"
    embedding_dim: int = 768  # Gemini text-embedding-004

    # Gemini
    gemini_api_key: str = ""
    gemini_model_name: str = "gemini-2.5-flash"
    gemini_max_output_tokens: int = 4096

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

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
