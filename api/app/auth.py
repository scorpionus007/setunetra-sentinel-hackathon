"""Authentication & authorisation — real stateless JWT (HS256), replacing the
old X-User-Role header placeholder.

Cybersecurity model:
  * Passwords are bcrypt-hashed in Postgres (pgcrypto crypt()/gen_salt('bf')).
  * Login issues a signed HS256 token (stdlib HMAC — no third-party JWT lib).
  * Every request re-loads the user from the DB, so a disabled account or a
    changed role takes effect immediately (the token only carries identity).
  * Department-wise RBAC by role level; jurisdiction scoping is applied in the
    data routers using the user's department/station.
  * Failed logins, lockouts, RBAC denials and bad tokens are written to
    security_events; mutating actions are written to audit_log.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import text

from app.db import get_db

SECRET = os.environ.get("API_SECRET_KEY", "setunetra-dev-secret-change-me")
TOKEN_TTL_SECONDS = int(os.environ.get("API_TOKEN_TTL", str(8 * 3600)))
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# Department-wise RBAC ladder. Higher level ⊇ lower level capabilities.
ROLE_LEVELS = {
    "viewer": 1,          # read-only operational surfaces
    "auditor": 1,         # read-only, but sees the security/audit surfaces
    "station_officer": 2, # scoped to a station
    "dept_officer": 3,    # scoped to a department
    "admin": 4,           # statewide super user
}
ROLE_LABELS = {
    "viewer": "Control Room Viewer",
    "auditor": "Security Auditor",
    "station_officer": "Station Officer",
    "dept_officer": "Department Officer",
    "admin": "State Administrator",
}


# --- token helpers ---------------------------------------------------------

def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_decode(seg: str) -> bytes:
    return base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))


def make_token(user: dict) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
    }
    segment = _b64u_encode(json.dumps(header).encode()) + "." + _b64u_encode(json.dumps(payload).encode())
    sig = hmac.new(SECRET.encode(), segment.encode(), hashlib.sha256).digest()
    return segment + "." + _b64u_encode(sig)


def decode_token(token: str) -> Optional[dict]:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        segment = header_b64 + "." + payload_b64
        expected = _b64u_encode(hmac.new(SECRET.encode(), segment.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, sig_b64):
            return None
        payload = json.loads(_b64u_decode(payload_b64))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# --- security & audit telemetry -------------------------------------------

def log_security_event(db, kind: str, severity: str, email, ip: str, detail: str) -> None:
    try:
        db.execute(
            text(
                "INSERT INTO security_events (kind, severity, email, ip_address, detail) "
                "VALUES (:k, :s, :e, :ip, :d)"
            ),
            {"k": kind, "s": severity, "e": email, "ip": ip, "d": detail},
        )
        db.commit()
    except Exception:
        db.rollback()


def record_audit(db, user: Optional[dict], action: str, resource: str,
                 detail=None, ip: str = "unknown", outcome: str = "success") -> None:
    try:
        db.execute(
            text(
                "INSERT INTO audit_log (user_id, user_email, role, action, resource, detail, ip_address, outcome) "
                "VALUES (:uid, :email, :role, :action, :resource, CAST(:detail AS JSONB), :ip, :outcome)"
            ),
            {
                "uid": user["id"] if user else None,
                "email": user["email"] if user else None,
                "role": user["role"] if user else None,
                "action": action,
                "resource": resource,
                "detail": json.dumps(detail) if detail is not None else None,
                "ip": ip,
                "outcome": outcome,
            },
        )
        db.commit()
    except Exception:
        db.rollback()


# --- current user dependency ----------------------------------------------

def _load_user(db, user_id: str) -> Optional[dict]:
    row = db.execute(
        text(
            "SELECT u.id, u.email, u.full_name, u.role, u.department_id, u.station_id, u.is_active, "
            "       d.name AS department_name, s.district AS station_district "
            "FROM users u "
            "LEFT JOIN departments d ON d.id = u.department_id "
            "LEFT JOIN stations s ON s.id = u.station_id "
            "WHERE u.id = :id"
        ),
        {"id": user_id},
    ).mappings().first()
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "email": row["email"],
        "full_name": row["full_name"],
        "role": row["role"],
        "level": ROLE_LEVELS.get(row["role"], 1),
        "department_id": str(row["department_id"]) if row["department_id"] else None,
        "department_name": row["department_name"],
        "station_id": str(row["station_id"]) if row["station_id"] else None,
        "district": row["station_district"],
        "is_active": row["is_active"],
    }


def get_current_user(
    request: Request,
    authorization: str = Header(default=None),
    db=Depends(get_db),
) -> dict:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    payload = decode_token(token) if token else None
    if not payload:
        # Only record a security event when a token was actually presented and
        # failed validation (expired/tampered) — an absent token is just an
        # unauthenticated request and would otherwise flood the log.
        if token:
            log_security_event(db, "token_invalid", "low", None, client_ip(request),
                               "Expired or tampered bearer token")
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = _load_user(db, payload["sub"])
    if not user or not user["is_active"]:
        raise HTTPException(status_code=401, detail="Account inactive or not found")
    return user


def require_role(min_role: str):
    """Dependency factory — caller needs at least `min_role`'s level."""
    min_level = ROLE_LEVELS.get(min_role, 99)

    def _check(request: Request, user=Depends(get_current_user), db=Depends(get_db)):
        if user["level"] < min_level:
            log_security_event(
                db, "access_denied", "medium", user["email"], client_ip(request),
                f"RBAC: {user['role']} attempted action requiring {min_role}",
            )
            raise HTTPException(
                status_code=403,
                detail=f"Access denied — requires {ROLE_LABELS.get(min_role, min_role)} or higher",
            )
        return user

    return _check
