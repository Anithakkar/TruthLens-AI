from fastapi.testclient import TestClient

from app.api.routes import submissions as analysis_routes
from app.main import app


client = TestClient(app)
PAYLOAD = {
    "headline": "Example public health report",
    "article_text": (
        "This is a sufficiently long sample article submitted for the TruthLens "
        "news analysis endpoint and its explanatory response."
    ),
}


def test_analysis_returns_model_signals_and_separate_fact_checks(monkeypatch) -> None:
    monkeypatch.setattr(
        analysis_routes,
        "predict_statement",
        lambda text: {
            "benchmark_label": "half-true",
            "label_description": "rated half true in the LIAR benchmark",
            "model_score": 0.42,
            "top_signals": [{"term": "public health", "contribution": 0.2}],
            "counter_signals": [],
            "explanation": "A model association, not evidence.",
        },
    )
    monkeypatch.setattr(
        analysis_routes,
        "search_fact_checks",
        lambda query: {
            "status": "no_matches",
            "message": "No external reviews found.",
            "items": [],
        },
    )
    monkeypatch.setattr(
        analysis_routes,
        "predict_model_comparison",
        lambda text, primary: {
            "traditional": {"status": "available", **primary},
            "transformer": {
                "status": "not_trained",
                "message": "Fine-tune the transformer first.",
            },
        },
    )

    response = client.post("/api/analyze", json=PAYLOAD)

    assert response.status_code == 200
    result = response.json()
    assert result["benchmark_label"] == "half-true"
    assert result["model_score"] == 0.42
    assert result["top_signals"][0]["term"] == "public health"
    assert result["model_comparison"]["traditional"]["status"] == "available"
    assert result["model_comparison"]["transformer"]["status"] == "not_trained"
    assert result["fact_checks"]["status"] == "no_matches"
    assert "not a finding of truth or falsity" in result["notice"]


def test_analysis_returns_503_if_model_is_missing(monkeypatch) -> None:
    from app.services.model import ModelNotReadyError

    def missing_model(text):
        raise ModelNotReadyError("Train model first.")

    monkeypatch.setattr(analysis_routes, "predict_statement", missing_model)

    response = client.post("/api/analyze", json=PAYLOAD)

    assert response.status_code == 503
    assert response.json()["detail"] == "Train model first."
