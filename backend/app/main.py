import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import ORJSONResponse
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.core.rate_limit import SlidingWindowRateLimiter
from app.db.session import Database
from app.jobs.notifications import NotificationWorker

settings = get_settings()
configure_logging(settings.log_level, settings.environment == "production")
logger = structlog.get_logger()
public_order_limiter = SlidingWindowRateLimiter(requests=10, window_seconds=60)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    database = Database(settings)
    http = httpx.AsyncClient(timeout=httpx.Timeout(15, connect=5))
    worker = NotificationWorker(database, settings, http)
    worker_task = asyncio.create_task(worker.run(), name="notification-outbox")
    app.state.settings = settings
    app.state.database = database
    app.state.http = http
    try:
        yield
    finally:
        worker.stop()
        try:
            await asyncio.wait_for(worker_task, timeout=10)
        except TimeoutError:
            worker_task.cancel()
        await http.aclose()
        await database.close()


app = FastAPI(
    title="Wrap Theory API",
    version="1.0.0",
    description="Storefront and operations API for a single-branch restaurant.",
    default_response_class=ORJSONResponse,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    openapi_url="/openapi.json" if settings.environment != "production" else None,
    lifespan=lifespan,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(GZipMiddleware, minimum_size=1_000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)


@app.middleware("http")
async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))[:100]
    request.state.request_id = request_id
    client_ip = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    client_ip = client_ip or (request.client.host if request.client else "unknown")
    if request.method == "POST" and request.url.path == "/v1/public/orders":
        await public_order_limiter.check(client_ip)
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    logger.info(
        "request_completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round((time.perf_counter() - start) * 1000, 2),
    )
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, error: AppError) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
                "requestId": request.state.request_id,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, error: RequestValidationError) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request data is invalid",
                "details": error.errors(),
                "requestId": request.state.request_id,
            }
        },
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, error: Exception) -> ORJSONResponse:
    logger.exception("unhandled_error", request_id=request.state.request_id, path=request.url.path)
    return ORJSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "requestId": request.state.request_id,
            }
        },
    )


@app.get("/health", tags=["Health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["Health"])
async def ready(request: Request) -> dict[str, str]:
    database: Database = request.app.state.database
    async with database.sessions() as session:
        await session.execute(text("select 1"))
    return {"status": "ready"}


app.include_router(api_router)
