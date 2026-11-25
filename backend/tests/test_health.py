from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.model import is_model_ready, is_transformer_model_ready


client = TestClient(app)


def test_root_url_points_to_api_docs_and_health() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "TruthLens AI API",
        "status": "ok",
        "docs": "/docs",
        "health": "/api/health",
    }


def test_health_check_returns_ok() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "TruthLens AI API",
        "api_version": "0.1.0",
    }


def test_analysis_status_matches_local_model_artifact() -> None:
    response = client.get("/api/analysis/status")

    assert response.status_code == 200
    assert response.json()["available"] is is_model_ready()


def test_local_frontend_origins_are_allowed_by_cors() -> None:
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        response = client.options(
            "/api/submissions",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def test_security_headers_are_added() -> None:
    response = client.get("/api/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_configuration_status_never_exposes_secrets() -> None:
    response = client.get("/api/configuration")

    assert response.status_code == 200
    body = response.json()
    assert "database" in body
    assert "model_provider" in body
    assert body["model_ready"] is is_model_ready()
    assert body["transformer_selected"] is (settings.model_provider == "transformer")
    assert body["transformer_configured"] is is_transformer_model_ready()
    assert "fact_check_configured" in body
    serialized = str(body).lower()
    assert "supabase_service_role_key" not in serialized
    assert "google_fact_check_api_key" not in serialized
