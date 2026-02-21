"""Custom middleware for HK-PropTech AI."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.i18n import SUPPORTED_LANGS


class LocaleMiddleware(BaseHTTPMiddleware):
    """Detect the client's preferred language and store it in ``request.state.lang``.

    Resolution order:
    1. ``Accept-Language`` header (first tag)
    2. Falls back to ``settings.DEFAULT_LANG`` (zh_hk)
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw = request.headers.get("Accept-Language", settings.DEFAULT_LANG)
        # Take first tag: "zh-HK,en;q=0.9" → "zh-HK"
        lang = raw.split(",")[0].strip().replace("-", "_").lower()

        if lang not in SUPPORTED_LANGS:
            lang = settings.DEFAULT_LANG

        request.state.lang = lang
        response = await call_next(request)
        response.headers["Content-Language"] = lang
        return response
