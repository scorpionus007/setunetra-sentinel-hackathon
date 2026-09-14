"""SetuNetra API — Integrated CCTV Registry, Unified Viewing & VMS Federation.

Models: (1) Registry & GIS, (2) Unified Viewing & metadata, (3) VMS Federation,
plus a cybersecurity layer (JWT auth, RBAC, rate limiting, audit, security headers).
No AI/ML: all analytics are deterministic and rule-based.
"""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.routers import (
    alerts,
    audit,
    auth,
    camera_events,
    cameras,
    coverage,
    federation,
    lookup,
    onboarding,
    security,
    stats,
    watchlist,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("api.main")

app = FastAPI(title="SetuNetra API", version="2.0.0",
              description="CCTV Registry + Unified Viewing + VMS Federation (no AI/ML)")

# Middleware (added last = outermost): CORS wraps everything so even a 429 or a
# rejected request still carries the right CORS headers for the browser.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
_allowed_origins = os.environ.get(
    "API_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(onboarding.router)
app.include_router(camera_events.router)
app.include_router(watchlist.router)
app.include_router(alerts.router)
app.include_router(coverage.router)
app.include_router(lookup.router)
app.include_router(federation.router)
app.include_router(security.router)
app.include_router(stats.router)
app.include_router(audit.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "setunetra-api", "version": "2.0.0"}
