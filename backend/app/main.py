from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
from collections import defaultdict, deque
from time import monotonic

from app.db.repository import get_database_status

from app.api.routes.submissions import router as submissions_router
from app.core.config import settings
from app.schemas.health import HealthResponse
from app.services.model import is_model_ready, is_transformer_model_ready


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "TruthLens AI API for news submissions and benchmark-model analysis, "
        "with optional external fact-check reviews."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(submissions_router, prefix="/api")

_request_windows: dict[str, deque[float]] = defaultdict(deque)
_WRITE_WINDOW_SECONDS = 60.0
_WRITE_REQUEST_LIMIT = 30


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        key = f"{request.client.host if request.client else 'unknown'}:{request.url.path}"
        now = monotonic()
        window = _request_windows[key]
        while window and now - window[0] > _WRITE_WINDOW_SECONDS:
            window.popleft()
        if len(window) >= _WRITE_REQUEST_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please wait before trying again."},
            )
        window.append(now)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    return response


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "ok",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        api_version=app.version,
    )


@app.get("/api/configuration", tags=["configuration"])
def configuration_status() -> dict[str, object]:
    return {
        "database": get_database_status(),
        "model_provider": settings.model_provider,
        "model_ready": is_model_ready(),
        "transformer_selected": settings.model_provider == "transformer",
        "transformer_configured": is_transformer_model_ready(),
        "fact_check_configured": bool(settings.google_fact_check_api_key),
    }


