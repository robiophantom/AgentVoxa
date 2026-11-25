from fastapi.testclient import TestClient

from main import app
from routers.admin import _json_or_default


FRONTEND_ORIGIN = "https://agentvoxa-frontend.onrender.com"


def test_call_log_json_metadata_ignores_invalid_legacy_values():
    assert _json_or_default("{broken", []) == []
    assert _json_or_default('{"tool": "rag"}', {}) == {"tool": "rag"}


def test_application_cors_adds_headers_to_internal_errors():
    async def fail():
        raise RuntimeError("database query failed")

    app.app.add_api_route("/__test_server_error", fail, methods=["GET"])
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        "/__test_server_error",
        headers={"Origin": FRONTEND_ORIGIN},
    )

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN
