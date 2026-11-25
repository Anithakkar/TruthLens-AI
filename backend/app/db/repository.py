from typing import Any

from app.core.config import settings
from app.db.errors import DatabaseNotConfiguredError
from app.db.sqlite import (
    delete_submission as delete_sqlite_submission,
    list_submissions as list_sqlite_submissions,
    save_analysis_result as save_sqlite_analysis_result,
    save_submission as save_sqlite_submission,
)
from app.db.supabase import (
    delete_submission as delete_supabase_submission,
    list_submissions as list_supabase_submissions,
    save_analysis_result as save_supabase_analysis_result,
    save_submission as save_supabase_submission,
)
from app.schemas.submission import NewsSubmissionCreate


def save_submission(submission: NewsSubmissionCreate) -> dict[str, Any]:
    if settings.database_provider == "sqlite":
        return save_sqlite_submission(submission)
    if settings.database_provider == "supabase":
        return save_supabase_submission(submission)

    raise DatabaseNotConfiguredError("Unsupported database provider.")


def list_submissions(limit: int = 20) -> list[dict[str, Any]]:
    if settings.database_provider == "sqlite":
        return list_sqlite_submissions(limit)
    if settings.database_provider == "supabase":
        return list_supabase_submissions(limit)

    raise DatabaseNotConfiguredError("Unsupported database provider.")


def delete_submission(submission_id: str) -> bool:
    if settings.database_provider == "sqlite":
        return delete_sqlite_submission(submission_id)
    if settings.database_provider == "supabase":
        return delete_supabase_submission(submission_id)

    raise DatabaseNotConfiguredError("Unsupported database provider.")


def save_analysis_result(submission_id: str, analysis_result: dict[str, Any]) -> None:
    if settings.database_provider == "sqlite":
        save_sqlite_analysis_result(submission_id, analysis_result)
        return
    if settings.database_provider == "supabase":
        save_supabase_analysis_result(submission_id, analysis_result)
        return
    raise DatabaseNotConfiguredError("Unsupported database provider.")


def get_database_status() -> dict[str, object]:
    if settings.database_provider == "sqlite":
        return {"provider": "sqlite", "configured": True, "live": True}
    if settings.database_provider == "supabase":
        configured = bool(
            settings.supabase_url.strip()
            and settings.supabase_service_role_key.strip()
        )
        return {
            "provider": "supabase",
            "configured": configured,
            "live": False,
        }
    return {"provider": "unknown", "configured": False, "live": False}
