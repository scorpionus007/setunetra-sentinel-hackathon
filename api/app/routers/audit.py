"""Audit trail inspection — immutable log of mutating actions.

Visible to admin and auditor roles. Writes happen via app.auth.record_audit()
from the individual routers; this router is read + a manual log endpoint.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import client_ip, get_current_user, record_audit
from app.db import get_db

router = APIRouter(prefix="/api/audit", tags=["audit"])

_AUDIT_ROLES = {"admin", "auditor"}


class AuditLogEntryIn(BaseModel):
    action: str
    resource: str
    detail: Optional[dict] = None


@router.get("/logs")
def get_audit_logs(action: Optional[str] = None, outcome: Optional[str] = None,
                   limit: int = Query(default=50, le=200), offset: int = 0,
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user["role"] not in _AUDIT_ROLES:
        raise HTTPException(status_code=403, detail="Audit trail requires admin or auditor role")
    clauses = ["1=1"]
    params = {"limit": limit, "offset": offset}
    if action:
        clauses.append("action ILIKE :action")
        params["action"] = f"%{action}%"
    if outcome:
        clauses.append("outcome = :outcome")
        params["outcome"] = outcome
    where = " AND ".join(clauses)
    rows = db.execute(text(
        f"SELECT id, user_email, role, action, resource, detail, ip_address, outcome, ts "
        f"FROM audit_log WHERE {where} ORDER BY ts DESC LIMIT :limit OFFSET :offset"
    ), params).fetchall()
    total = db.execute(text(f"SELECT count(*) AS total FROM audit_log WHERE {where}"), params).fetchone().total
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": [
            {
                "id": str(r.id),
                "user_email": r.user_email,
                "role": r.role,
                "action": r.action,
                "resource": r.resource,
                "detail": r.detail,
                "ip_address": r.ip_address,
                "outcome": r.outcome,
                "timestamp": r.ts.isoformat() if r.ts else None,
            }
            for r in rows
        ],
    }


@router.post("/log")
def create_audit_log(entry: AuditLogEntryIn, request: Request,
                     db: Session = Depends(get_db), user=Depends(get_current_user)):
    record_audit(db, user, entry.action, entry.resource, detail=entry.detail, ip=client_ip(request))
    return {"status": "recorded"}
