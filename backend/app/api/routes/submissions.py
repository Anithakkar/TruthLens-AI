import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.services.fact_checks import search_fact_checks
from app.services.model import (
    ModelNotReadyError,
    is_model_ready,
    predict_model_comparison,
    predict_statement,
)
from app.db.errors import (
    DatabaseNotConfiguredError,
    DatabaseOperationError,
)
from app.db.repository import (
    delete_submission,
    list_submissions,
    save_analysis_result,
    save_submission,
)
from app.schemas.analysis import NewsAnalysisRequest, NewsAnalysisResponse
from app.schemas.health import AnalysisAvailabilityResponse
from app.schemas.submission import (
    NewsSubmissionCreate,
    NewsSubmissionRecord,
    NewsSubmissionResponse,
)


logger = logging.getLogger(__name__)
router = APIRouter(tags=["submissions"])


@router.get(
    "/submissions",
    response_model=list[NewsSubmissionRecord],
)
def get_submissions(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[NewsSubmissionRecord]:
    try:
        records = list_submissions(limit)
    except DatabaseNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured.",
        ) from error
    except DatabaseOperationError as error:
        logger.exception("Failed to read submissions from the database.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The database could not load submissions.",
        ) from error

    return [NewsSubmissionRecord.model_validate(record) for record in records]


@router.delete(
    "/submissions/{submission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def remove_submission(submission_id: UUID) -> Response:
    try:
        deleted = delete_submission(str(submission_id))
    except DatabaseNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured.",
        ) from error
    except DatabaseOperationError as error:
        logger.exception("Failed to delete a submission from the database.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The database could not delete the submission.",
        ) from error

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved article was not found.",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/analysis/status",
    response_model=AnalysisAvailabilityResponse,
    tags=["analysis"],
)
def analysis_status() -> AnalysisAvailabilityResponse:
    ready = is_model_ready()
    return AnalysisAvailabilityResponse(
        available=ready,
        message=(
            "Baseline text classifier is ready; fact-check search is optional."
            if ready
            else "Train the baseline model before requesting an analysis."
        ),
    )


@router.post(
    "/analyze",
    response_model=NewsAnalysisResponse,
    tags=["analysis"],
)
def analyze_news(request: NewsAnalysisRequest) -> NewsAnalysisResponse:
    model_input = f"{request.headline}. {request.article_text}"
    try:
        prediction = predict_statement(model_input)
        model_comparison = predict_model_comparison(model_input, prediction)
    except ModelNotReadyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    fact_checks = search_fact_checks(request.headline)
    analysis = NewsAnalysisResponse(
        submission_id=request.submission_id,
        **prediction,
        model_comparison=model_comparison,
        fact_checks=fact_checks,
        notice=(
            "This is a benchmark-model prediction, not a finding of truth or "
            "falsity. External reviews are shown separately and should be read "
            "at their source."
        ),
    )
    if request.submission_id is not None:
        try:
            save_analysis_result(
                str(request.submission_id),
                analysis.model_dump(mode="json", exclude={"submission_id"}),
            )
        except (DatabaseNotConfiguredError, DatabaseOperationError) as error:
            logger.exception("Could not save analysis result for submission.")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Analysis completed, but its result could not be saved.",
            ) from error
    return analysis


@router.post(
    "/submissions",
    response_model=NewsSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_submission(submission: NewsSubmissionCreate) -> NewsSubmissionResponse:
    try:
        saved_submission = save_submission(submission)
    except DatabaseNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.",
        ) from error

    except DatabaseOperationError as error:
        logger.exception("Failed to save a news submission to Supabase.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The database could not save the submission. Please try again.",
        ) from error

    return NewsSubmissionResponse.model_validate(saved_submission)
