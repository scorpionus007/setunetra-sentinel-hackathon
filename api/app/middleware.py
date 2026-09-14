"""Cross-cutting cybersecurity middleware: security headers + rate limiting.

Both are dependency-free (in-process). The rate limiter is a per-IP sliding
window; trips are recorded to security_events so they surface on the security
dashboard.
"""
import os
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.db import SessionLocal
from app.auth import log_security_event, client_ip

RATE_LIMIT = int(os.environ.get("API_RATE_LIMIT_PER_MIN", "600"))
WINDOW_SECONDS = 60
# High-frequency media polling (the live viewing wall) is exempt from the
# limiter — it is auth-gated, read-only, and legitimately polled continuously.
_EXEMPT_SUFFIXES = ("/snapshot",)

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding-window limiter. OPTIONS (CORS preflight) is exempt."""

    def __init__(self, app):
        super().__init__(app)
        self._hits = defaultdict(deque)

    async def dispatch(self, request, call_next):
        if request.method == "OPTIONS" or request.url.path.endswith(_EXEMPT_SUFFIXES):
            return await call_next(request)

        ip = client_ip(request)
        now = time.time()
        window = self._hits[ip]
        while window and window[0] < now - WINDOW_SECONDS:
            window.popleft()

        if len(window) >= RATE_LIMIT:
            db = SessionLocal()
            try:
                log_security_event(db, "rate_limited", "medium", None, ip,
                                   f"{RATE_LIMIT} req/min exceeded on {request.url.path}")
            finally:
                db.close()
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Slow down."},
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )

        window.append(now)
        return await call_next(request)
