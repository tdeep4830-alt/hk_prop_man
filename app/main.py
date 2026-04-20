"""HK-PropTech AI — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import from_url as redis_from_url
from sqlalchemy import text

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.i18n import t
from app.core.logger import logger
from app.core.middleware import LocaleMiddleware
from app.core.observability import setup_metrics, setup_tracing
from app.db.session import engine


# ---------------------------------------------------------------------------
# Lifespan: startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting HK-PropTech AI", extra={"env": settings.ENVIRONMENT})
    if settings.ENABLE_TRACING:
        setup_tracing(settings.PHOENIX_ENDPOINT)
    app.state.redis = redis_from_url(settings.REDIS_URL, decode_responses=True)
    yield
    await app.state.redis.aclose()
    await engine.dispose()
    logger.info("HK-PropTech AI shut down gracefully")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="HK-PropTech AI",
    version="0.2.0",
    lifespan=lifespan,
)

# Middleware (order matters — outermost first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LocaleMiddleware)

# Prometheus /metrics endpoint
setup_metrics(app)

# Routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    lang = getattr(request.state, "lang", settings.DEFAULT_LANG)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": t(exc.i18n_key, lang, **exc.fmt_args)},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    lang = getattr(request.state, "lang", settings.DEFAULT_LANG)
    logger.error(
        "Unhandled exception",
        extra={"path": str(request.url), "method": request.method, "error": str(exc)},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": t("error.internal", lang)},
    )


# ---------------------------------------------------------------------------
# Health check — verifies DB + Redis connectivity
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check(request: Request):
    lang = getattr(request.state, "lang", settings.DEFAULT_LANG)
    status: dict = {"status": "ok", "db": "ok", "redis": "ok"}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.warning("DB health check failed", extra={"error": str(e)})
        status["db"] = "unavailable"
        status["status"] = "degraded"

    try:
        await request.app.state.redis.ping()
    except Exception as e:
        logger.warning("Redis health check failed", extra={"error": str(e)})
        status["redis"] = "unavailable"
        status["status"] = "degraded"

    message_key = "health.ok" if status["status"] == "ok" else "health.degraded"
    status["message"] = t(message_key, lang)

    http_code = 200 if status["status"] == "ok" else 503
    return JSONResponse(status_code=http_code, content=status)
