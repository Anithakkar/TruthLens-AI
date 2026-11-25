import httpx

from app.core.config import settings
from app.services.fact_checks import search_fact_checks


def test_fact_check_search_returns_unconfigured_status(monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_fact_check_api_key", "")

    result = search_fact_checks("Example headline")

    assert result["status"] == "not_configured"
    assert result["items"] == []


def test_fact_check_search_extracts_publisher_reviews(monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_fact_check_api_key", "test-key")

    def fake_get(url, params, timeout):
        assert params["query"] == "Example headline"
        return httpx.Response(
            200,
            json={
                "claims": [
                    {
                        "text": "Claim under review",
                        "claimReview": [
                            {
                                "publisher": {"name": "Example Fact Check"},
                                "title": "Review of the claim",
                                "textualRating": "Unproven",
                                "url": "https://example.test/review",
                                "reviewDate": "2025-01-02",
                            }
                        ],
                    }
                ]
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr("app.services.fact_checks.httpx.get", fake_get)

    result = search_fact_checks("Example headline")

    assert result["status"] == "matches"
    assert result["items"][0]["publisher"] == "Example Fact Check"
    assert result["items"][0]["url"] == "https://example.test/review"
