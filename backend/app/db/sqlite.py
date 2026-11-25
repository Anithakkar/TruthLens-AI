import sqlite3
import json
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.db.errors import DatabaseOperationError
from app.schemas.submission import NewsSubmissionCreate


def _database_path() -> Path:
    path = Path(settings.sqlite_database_path)
    if not path.is_absolute():
        project_root = Path(__file__).resolve().parents[3]
        path = project_root / path
    return path


def _ensure_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        create table if not exists news_submissions (
            id text primary key not null,
            headline text not null check (length(headline) between 5 and 300),
            article_text text not null check (length(article_text) between 40 and 20000),
            source_name text check (source_name is null or length(source_name) <= 200),
            source_url text,
            status text not null default 'received'
                check (status in ('received', 'analyzing', 'analyzed', 'failed')),
            created_at text not null,
            analysis_result text
        )
        """
    )
    columns = {
        row["name"] for row in connection.execute("pragma table_info(news_submissions)")
    }
    if "analysis_result" not in columns:
        connection.execute("alter table news_submissions add column analysis_result text")


def save_submission(submission: NewsSubmissionCreate) -> dict[str, Any]:
    database_path = _database_path()
    submission_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(database_path, timeout=10)) as connection, connection:
            connection.row_factory = sqlite3.Row
            _ensure_table(connection)
            connection.execute(
                """
                insert into news_submissions
                    (id, headline, article_text, source_name, source_url, status, created_at)
                values (?, ?, ?, ?, ?, 'received', ?)
                """,
                (
                    submission_id,
                    submission.headline,
                    submission.article_text,
                    submission.source_name,
                    str(submission.source_url) if submission.source_url else None,
                    created_at,
                ),
            )
    except sqlite3.Error as error:
        raise DatabaseOperationError("Local database could not save the submission.") from error

    return {
        "id": submission_id,
        "status": "received",
        "created_at": created_at,
    }


def list_submissions(limit: int = 20) -> list[dict[str, Any]]:
    database_path = _database_path()
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(database_path, timeout=10)) as connection, connection:
            connection.row_factory = sqlite3.Row
            _ensure_table(connection)
            rows = connection.execute(
                """
                select id, headline, article_text, source_name, source_url, status, created_at,
                    analysis_result
                from news_submissions
                order by created_at desc
                limit ?
                """,
                (limit,),
            ).fetchall()
    except sqlite3.Error as error:
        raise DatabaseOperationError("Local database could not read submissions.") from error

    records = []
    for row in rows:
        record = dict(row)
        if record["analysis_result"]:
            record["analysis_result"] = json.loads(record["analysis_result"])
        records.append(record)
    return records


def delete_submission(submission_id: str) -> bool:
    database_path = _database_path()
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(database_path, timeout=10)) as connection, connection:
            connection.row_factory = sqlite3.Row
            _ensure_table(connection)
            cursor = connection.execute(
                "delete from news_submissions where id = ?",
                (submission_id,),
            )
            return cursor.rowcount > 0
    except sqlite3.Error as error:
        raise DatabaseOperationError("Local database could not delete the submission.") from error


def save_analysis_result(submission_id: str, analysis_result: dict[str, Any]) -> None:
    database_path = _database_path()
    try:
        with closing(sqlite3.connect(database_path, timeout=10)) as connection, connection:
            connection.row_factory = sqlite3.Row
            _ensure_table(connection)
            cursor = connection.execute(
                """
                update news_submissions
                set analysis_result = ?, status = 'analyzed'
                where id = ?
                """,
                (json.dumps(analysis_result), submission_id),
            )
            if cursor.rowcount == 0:
                raise DatabaseOperationError("Submission was not found for analysis storage.")
    except sqlite3.Error as error:
        raise DatabaseOperationError("Local database could not save the analysis.") from error
