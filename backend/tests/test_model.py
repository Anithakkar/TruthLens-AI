from app.services.model import is_model_ready, predict_statement


def test_trained_baseline_returns_traceable_non_verdict_explanation() -> None:
    assert is_model_ready()

    result = predict_statement(
        "A public report published today describes a new government research program."
    )

    assert result["benchmark_label"] in {
        "pants-fire",
        "false",
        "barely-true",
        "half-true",
        "mostly-true",
        "true",
    }
    assert 0 <= result["model_score"] <= 1
    assert "not verified evidence" in result["explanation"]
    assert isinstance(result["top_signals"], list)


def test_model_comparison_reports_untrained_transformer_explicitly(monkeypatch) -> None:
    from app.core.config import settings
    from app.services import model

    monkeypatch.setattr(settings, "model_provider", "traditional")
    monkeypatch.setattr(model, "is_transformer_model_ready", lambda: False)
    primary = {
        "benchmark_label": "half-true",
        "label_description": "rated half true in the LIAR benchmark",
    }

    result = model.predict_model_comparison("example statement", primary)

    assert result["traditional"]["status"] == "available"
    assert result["traditional"]["benchmark_label"] == "half-true"
    assert result["transformer"]["status"] == "not_trained"
    assert "Fine-tune" in result["transformer"]["message"]


def test_model_comparison_includes_transformer_when_available(monkeypatch) -> None:
    from app.core.config import settings
    from app.services import model

    monkeypatch.setattr(settings, "model_provider", "traditional")
    monkeypatch.setattr(model, "is_transformer_model_ready", lambda: True)
    monkeypatch.setattr(
        model,
        "_predict_transformer",
        lambda text: {"benchmark_label": "true", "label_description": "transformer result"},
    )
    primary = {
        "benchmark_label": "false",
        "label_description": "traditional result",
    }

    result = model.predict_model_comparison("example statement", primary)

    assert result["traditional"]["status"] == "available"
    assert result["traditional"]["benchmark_label"] == "false"
    assert result["transformer"]["status"] == "available"
    assert result["transformer"]["benchmark_label"] == "true"
