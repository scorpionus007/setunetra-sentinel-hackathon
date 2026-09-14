"""Cybersecurity dashboard — security telemetry + posture summary.

Restricted to roles that own security oversight (auditor, dept_officer, admin);
a plain viewer cannot see it.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.auth import get_current_user
from app.db import get_db

router = APIRouter(prefix="/api/security", tags=["security"])

_SECURITY_ROLES = {"auditor", "dept_officer", "admin"}


def _guard(user):
    if user["role"] not in _SECURITY_ROLES:
        raise HTTPException(status_code=403, detail="Security surfaces require auditor or officer role")
    return user


@router.get("/events")
def security_events(limit: int = 50, db=Depends(get_db), user=Depends(get_current_user)):
    _guard(user)
    rows = db.execute(text(
        "SELECT kind, severity, email, ip_address, detail, ts "
        "FROM security_events ORDER BY ts DESC LIMIT :lim"
    ), {"lim": min(limit, 200)}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/posture")
def posture(db=Depends(get_db), user=Depends(get_current_user)):
    _guard(user)
    by_kind = db.execute(text(
        "SELECT kind, count(*) AS n FROM security_events "
        "WHERE ts > now() - interval '24 hours' GROUP BY kind ORDER BY n DESC"
    )).mappings().all()
    by_severity = db.execute(text(
        "SELECT severity, count(*) AS n FROM security_events "
        "WHERE ts > now() - interval '24 hours' GROUP BY severity"
    )).mappings().all()

    metrics = db.execute(text(
        "SELECT "
        " (SELECT count(*) FROM security_events WHERE kind='login_failed' AND ts > now() - interval '24 hours') AS failed_logins, "
        " (SELECT count(*) FROM security_events WHERE kind='rate_limited' AND ts > now() - interval '24 hours') AS rate_limited, "
        " (SELECT count(*) FROM users WHERE locked_until > now()) AS locked_accounts, "
        " (SELECT count(*) FROM vms_systems WHERE status='offline') AS vms_offline, "
        " (SELECT count(*) FROM cameras WHERE status IN ('down','degraded')) AS cameras_unhealthy, "
        " (SELECT count(*) FROM users WHERE is_active) AS active_users"
    )).mappings().first()

    # Deterministic posture score: start at 100, subtract weighted issues.
    m = dict(metrics)
    score = 100
    score -= min(20, m["failed_logins"] * 2)
    score -= min(15, m["rate_limited"] * 3)
    score -= m["locked_accounts"] * 5
    score -= m["vms_offline"] * 6
    score -= min(20, m["cameras_unhealthy"] * 2)
    score = max(0, score)
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D"

    controls = [
        {"control": "JWT authentication (HS256, 8h TTL)", "status": "enabled"},
        {"control": "Bcrypt password hashing (pgcrypto)", "status": "enabled"},
        {"control": "Department-wise RBAC (5 roles)", "status": "enabled"},
        {"control": "Brute-force lockout (5 attempts / 15 min)", "status": "enabled"},
        {"control": "Per-IP rate limiting", "status": "enabled"},
        {"control": "Security headers (CSP, HSTS, XFO)", "status": "enabled"},
        {"control": "Immutable audit trail", "status": "enabled"},
        {"control": "Secrets via environment (no hardcoding)", "status": "enabled"},
    ]
    return {
        "score": score,
        "grade": grade,
        "metrics": m,
        "by_kind": [dict(r) for r in by_kind],
        "by_severity": [dict(r) for r in by_severity],
        "controls": controls,
    }
