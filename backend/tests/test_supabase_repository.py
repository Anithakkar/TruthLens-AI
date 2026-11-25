from types import SimpleNamespace
from uuid import uuid4

import pytest
from postgrest.exceptions import APIError

from app.core.config import settings
from app.db import supabase as supabase_repository
from app.db.errors import DatabaseNotConfiguredError, DatabaseOperationError
from app.schemas.submission import NewsSubmissionCreate


class FakeQuery:
    def __init__(self, result):
        self.result = result
        self.inserted_record = None
        self.selected_fields = None

    def insert(self, record):
        self.inserted_record = record
        return self

    def select(self, fields):
        self.selected_fields = fields
        return self

    def execute(self):
        return SimpleNamespace(data=self.result)


class FakeClient:
    def __init__(self, query):
        self.query = query
        self.table_name = None

    def table(self, table_name):
        self.table_name = table_name
        return self.query


def test_save_submission_sends_validated_data_and_returns_database_record(monkeypatch) -> None:
    submission_id = uuid4()
    created_at = "2026-11-24T10:00:00+00:00"
    query = FakeQuery(
        [
            {
                "id": str(submission_id),
                "status": "received",
                "created_at": created_at,
            }
        ]
    )
    client = FakeClient(query)
    monkeypatch.setattr(supabase_repository, "get_supabase_client", lambda: client)
    submission = NewsSubmissionCreate(
        headline="Example report",
        article_text="This article contains enough text to pass the submission limits.",
    )

    result = supabase_repository.save_submission(submission)

    assert client.table_name == "news_submissions"
    assert query.inserted_record == {
        "headline": "Example report",
        "article_text": "This article contains enough text to pass the submission limits.",
    }
    assert query.selected_fields == "id,status,created_at"
    assert result["id"] == str(submission_id)


def test_save_submission_raises_clear_error_when_database_returns_no_record(monkeypatch) -> None:
    query = FakeQuery([])
    monkeypatch.setattr(
        supabase_repository,
        "get_supabase_client",
        lambda: FakeClient(query),
    )
    submission = NewsSubmissionCreate(
        headline="Example report",
        article_text="This article contains enough text to pass the submission limits.",
    )

    with pytest.raises(DatabaseOperationError, match="did not return"):
        supabase_repository.save_submission(submission)


def test_get_client_requires_supabase_url_and_server_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    supabase_repository.get_supabase_client.cache_clear()

    with pytest.raises(DatabaseNotConfiguredError):
        supabase_repository.get_supabase_client()


def test_save_submission_wraps_postgrest_errors(monkeypatch) -> None:
    class FailedQuery(FakeQuery):
        def execute(self):
            raise APIError({"message": "Database unavailable"})

    monkeypatch.setattr(
        supabase_repository,
        "get_supabase_client",
        lambda: FakeClient(FailedQuery([])),
    )
    submission = NewsSubmissionCreate(
        headline="Example report",
        article_text="This article contains enough text to pass the submission limits.",
    )

    with pytest.raises(DatabaseOperationError, match="could not save"):
        supabase_repository.save_submission(submission)
