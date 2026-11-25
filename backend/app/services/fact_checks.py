import logging
from typing import Any, Literal

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)
GOOGLE_FACT_CHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


def search_fact_checks(query: str) -> dict[str, Any]:
    if not settings.google_fact_check_api_key:
        return {
            "status": "not_configured",
            "message": "Configure GOOGLE_FACT_CHECK_API_KEY to search public fact-check reviews.",
            "items": [],
        }

    try:
        response = httpx.get(
            GOOGLE_FACT_CHECK_URL,
            params={
                "query": query[:300],
                "key": settings.google_fact_check_api_key,
                "pageSize": 5,
            },
            timeout=8.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Google Fact Check API request failed.")
        return {
            "status": "unavailable",
            "message": "The fact-check search service could not be reached.",
            "items": [],
        }

    raw_claims = response.json().get("claims", [])
    items = [
        item
        for claim in raw_claims
        for item in _extract_reviews(claim)
    ]
    status: Literal["matches", "no_matches"] = "matches" if items else "no_matches"
    return {
        "status": status,
        "message": "External publisher reviews; read the linked review for its context.",
        "items": items[:5],
    }


def _extract_reviews(claim: dict[str, Any]) -> list[dict[str, str]]:
    claim_text = claim.get("text", "")
    extracted = []
    for review in claim.get("claimReview", []):
        url = review.get("url")
        title = review.get("title")
        if not url or not title:
            continue
        extracted.append(
            {
                "claim": claim_text,
                "publisher": review.get("publisher", {}).get("name", "Unknown publisher"),
                "title": title,
                "rating": review.get("textualRating", "Rating not provided"),
                "url": url,
                "review_date": review.get("reviewDate", ""),
            }
        )
    return extracted
