from services.document_processor import chunk_text
from services.provider import FREE_TIER_MODELS
from routers.chat import _extract_contact_data


def test_chunk_text_returns_windows():
    text = "\n".join([f"Graphic Era University line {index}" for index in range(20)])
    chunks = chunk_text(text, chunk_size=20, overlap=3)
    assert chunks
    assert all(chunk.strip() for chunk in chunks)


def test_free_tier_provider_models_include_groq_default():
    assert "openai/gpt-oss-120b" in FREE_TIER_MODELS["groq"]
    assert "gemini-2.5-flash" in FREE_TIER_MODELS["gemini"]


def test_contact_validation_accepts_valid_and_rejects_invalid_phone():
    result = _extract_contact_data([], "Ravi", "ravi@example.com", "9876543210")
    assert result == {"name": "Ravi", "email": "ravi@example.com", "phone": "9876543210"}

    result = _extract_contact_data([], None, "not-an-email", "123")
    assert result == {}
