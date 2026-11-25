from functools import lru_cache
from typing import Any

import httpx
from postgrest.exceptions import APIError
from supabase import Client, create_client

from app.core.config import settings
from app.db.errors import DatabaseNotConfiguredError, DatabaseOperationError
from app.schemas.submission import NewsSubmissionCreate


@lru_cache
def get_supabase_client() -> Client:
    supabase_url = settings.supabase_url.strip()
    service_role_key = settings.supabase_service_role_key.strip()
    if not supabase_url or not service_role_key:
        raise DatabaseNotConfiguredError("Supabase connection settings are missing.")

    return create_client(supabase_url, service_role_key)


def save_submission(submission: NewsSubmissionCreate) -> dict[str, Any]:
    try:
        response = (
            get_supabase_client()
            .table("news_submissions")
            .insert(submission.model_dump(mode="json", exclude_none=True))
            .select("id,status,created_at")
            .execute()
        )
    except (APIError, httpx.HTTPError) as error:
        raise DatabaseOperationError("Supabase could not save the submission.") from error

    if not response.data:
        raise DatabaseOperationError("Supabase did not return the saved submission.")

    return response.data[0]


def list_submissions(limit: int = 20) -> list[dict[str, Any]]:
    try:
        response = (
            get_supabase_client()
            .table("news_submissions")
            .select(
                "id,headline,article_text,source_name,source_url,status,created_at,analysis_result"
            )
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except (APIError, httpx.HTTPError) as error:
        raise DatabaseOperationError("Supabase could not read submissions.") from error

    return response.data


def delete_submission(submission_id: str) -> bool:
    try:
        response = (
            get_supabase_client()
            .table("news_submissions")
            .delete()
            .eq("id", submission_id)
            .select("id")
            .execute()
        )
    except (APIError, httpx.HTTPError) as error:
        raise DatabaseOperationError("Supabase could not delete the submission.") from error

    return bool(response.data)


def save_analysis_result(submission_id: str, analysis_result: dict[str, Any]) -> None:
    try:
        response = (
            get_supabase_client()
            .table("news_submissions")
            .update({"analysis_result": analysis_result, "status": "analyzed"})
            .eq("id", submission_id)
            .execute()
        )
    except (APIError, httpx.HTTPError) as error:
        raise DatabaseOperationError("Supabase could not save the analysis.") from error
    if not response.data:
        raise DatabaseOperationError("Submission was not found for analysis storage.")
