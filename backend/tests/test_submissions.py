import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes import submissions as submission_routes
from app.core.config import settings
from app.db.errors import DatabaseNotConfiguredError, DatabaseOperationError
from app.main import app


client = TestClient(app)

VALID_PAYLOAD = {
    "headline": "Example public health report",
    "article_text": (
        "This is a sufficiently long sample article submitted for the initial "
        "TruthLens API request and persistence flow."
    ),
}


def test_create_submission_returns_saved_record(monkeypatch) -> None:
    submission_id = uuid4()
    created_at = datetime.now(timezone.utc).isoformat()

    def fake_save_submission(submission):
        assert submission.headline == VALID_PAYLOAD["headline"]
        return {
            "id": str(submission_id),
            "status": "received",
            "created_at": created_at,
        }

    monkeypatch.setattr(submission_routes, "save_submission", fake_save_submission)

    response = client.post("/api/submissions", json=VALID_PAYLOAD)

    assert response.status_code == 201
    assert response.json()["id"] == str(submission_id)
    assert response.json()["status"] == "received"


def test_create_submission_rejects_too_short_article() -> None:
    response = client.post(
        "/api/submissions",
        json={**VALID_PAYLOAD, "article_text": "Too short"},
    )

    assert response.status_code == 422


def test_create_submission_reports_missing_database_configuration(monkeypatch) -> None:
    def no_database(submission):
        raise DatabaseNotConfiguredError("Missing connection settings.")

    monkeypatch.setattr(submission_routes, "save_submission", no_database)

    response = client.post("/api/submissions", json=VALID_PAYLOAD)

    assert response.status_code == 503
    assert "Supabase is not configured" in response.json()["detail"]


def test_create_submission_reports_database_failure(monkeypatch) -> None:
    def database_failure(submission):
        raise DatabaseOperationError("Supabase request failed.")

    monkeypatch.setattr(submission_routes, "save_submission", database_failure)

    response = client.post("/api/submissions", json=VALID_PAYLOAD)

    assert response.status_code == 502
    assert "database could not save" in response.json()["detail"]


def test_create_submission_is_persisted_in_local_sqlite(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "truthlens-test.db"
    monkeypatch.setattr(settings, "database_provider", "sqlite")
    monkeypatch.setattr(settings, "sqlite_database_path", str(database_path))

    response = client.post("/api/submissions", json=VALID_PAYLOAD)

    assert response.status_code == 201
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "select headline, article_text, status from news_submissions where id = ?",
            (response.json()["id"],),
        ).fetchone()

    assert row == (
        VALID_PAYLOAD["headline"],
        VALID_PAYLOAD["article_text"],
        "received",
    )


def test_submission_list_returns_saved_records(tmp_path, monkeypatch) -> None:
    from app.db.sqlite import list_submissions, save_submission
    from app.schemas.submission import NewsSubmissionCreate

    monkeypatch.setattr(settings, "database_provider", "sqlite")
    monkeypatch.setattr(settings, "sqlite_database_path", str(tmp_path / "list-test.db"))
    submission = NewsSubmissionCreate(**VALID_PAYLOAD)
    saved = save_submission(submission)

    records = list_submissions(limit=5)

    assert len(records) == 1
    assert records[0]["id"] == saved["id"]
    assert records[0]["headline"] == VALID_PAYLOAD["headline"]
    assert records[0]["article_text"] == VALID_PAYLOAD["article_text"]


def test_saved_submission_list_api_shows_persisted_analysis(tmp_path, monkeypatch) -> None:
    from app.api.routes import submissions as submission_routes

    monkeypatch.setattr(settings, "database_provider", "sqlite")
    monkeypatch.setattr(settings, "sqlite_database_path", str(tmp_path / "api-list.db"))
    monkeypatch.setattr(
        submission_routes,
        "predict_statement",
        lambda text: {
            "benchmark_label": "half-true",
            "label_description": "rated half true in the LIAR benchmark",
            "model_score": 0.6,
            "top_signals": [],
            "counter_signals": [],
            "explanation": "A model association, not evidence.",
        },
    )
    monkeypatch.setattr(
        submission_routes,
        "search_fact_checks",
        lambda query: {"status": "not_configured", "message": "Not configured", "items": []},
    )

    saved = client.post("/api/submissions", json=VALID_PAYLOAD)
    assert saved.status_code == 201
    analyzed = client.post(
        "/api/analyze",
        json={**VALID_PAYLOAD, "submission_id": saved.json()["id"]},
    )
    assert analyzed.status_code == 200

    listed = client.get("/api/submissions")

    assert listed.status_code == 200
    assert listed.json()[0]["id"] == saved.json()["id"]
    assert listed.json()[0]["status"] == "analyzed"
    assert listed.json()[0]["analysis_result"]["benchmark_label"] == "half-true"


def test_delete_submission_removes_saved_record(tmp_path, monkeypatch) -> None:
    from app.db.sqlite import save_analysis_result

    monkeypatch.setattr(settings, "database_provider", "sqlite")
    monkeypatch.setattr(settings, "sqlite_database_path", str(tmp_path / "delete-test.db"))
    saved = client.post("/api/submissions", json=VALID_PAYLOAD)
    submission_id = saved.json()["id"]
    save_analysis_result(submission_id, {"benchmark_label": "half-true"})

    deleted = client.delete(f"/api/submissions/{submission_id}")

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get("/api/submissions").json() == []


def test_delete_submission_returns_not_found_for_unknown_id(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "database_provider", "sqlite")
    monkeypatch.setattr(settings, "sqlite_database_path", str(tmp_path / "delete-missing.db"))

    response = client.delete(f"/api/submissions/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Saved article was not found."


def test_delete_submission_reports_database_failure(monkeypatch) -> None:
    def database_failure(submission_id: str) -> bool:
        raise DatabaseOperationError("Storage unavailable.")

    monkeypatch.setattr(submission_routes, "delete_submission", database_failure)

    response = client.delete(f"/api/submissions/{uuid4()}")

    assert response.status_code == 502
    assert response.json()["detail"] == "The database could not delete the submission."


def test_supabase_delete_targets_the_requested_record(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.db import supabase

    operations: list[tuple[str, ...]] = []

    class DeleteQuery:
        def delete(self):
            operations.append(("delete",))
            return self

        def eq(self, field: str, value: str):
            operations.append(("eq", field, value))
            return self

        def select(self, fields: str):
            operations.append(("select", fields))
            return self

        def execute(self):
            return SimpleNamespace(data=[{"id": submission_id}])

    class Client:
        def table(self, name: str):
            assert name == "news_submissions"
            return DeleteQuery()

    submission_id = str(uuid4())
    monkeypatch.setattr(supabase, "get_supabase_client", lambda: Client())

    assert supabase.delete_submission(submission_id) is True
    assert operations == [
        ("delete",),
        ("eq", "id", submission_id),
        ("select", "id"),
    ]
