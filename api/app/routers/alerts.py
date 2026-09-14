"""Unified alert feed (rule-based) — camera offline/tamper, watchlist hits,
federation correlations, security. Read by any authenticated user; acknowledge
/dismiss requires an officer role.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import client_ip, get_current_user, record_audit, require_role
from app.db import get_db

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

_BASE_QUERY = """
    SELECT a.id, a.kind, a.severity, a.message, a.status, a.source_system, a.ts,
           c.external_id AS camera_external_id, c.location_name,
           w.value AS watchlist_value, w.type AS watchlist_type
    FROM alerts a
    LEFT JOIN cameras c ON c.id = a.camera_id
    LEFT JOIN watchlist w ON w.id = a.watchlist_id
"""


def _serialize(r) -> dict:
    return {
        "id": str(r.id),
        "kind": r.kind,
        "severity": r.severity,
        "message": r.message,
        "status": r.status,
        "source_system": r.source_system,
        "camera_external_id": r.camera_external_id,
        "location_name": r.location_name,
        "watchlist_value": r.watchlist_value,
        "watchlist_type": r.watchlist_type,
        "ts": r.ts.isoformat() if r.ts else None,
    }


@router.get("")
def list_alerts(status: str | None = Query(default=None), limit: int = 100,
                db: Session = Depends(get_db), user=Depends(get_current_user)):
    where = " WHERE a.status = :status " if status else ""
    params = {"status": status} if status else {}
    params["lim"] = min(limit, 200)
    rows = db.execute(text(_BASE_QUERY + where + " ORDER BY a.ts DESC LIMIT :lim"), params).fetchall()
    return [_serialize(r) for r in rows]


class AlertStatusIn(BaseModel):
    status: str


@router.patch("/{alert_id}")
def update_alert(alert_id: str, body: AlertStatusIn, request: Request,
                 db: Session = Depends(get_db), user=Depends(require_role("station_officer"))):
    if body.status not in {"new", "acknowledged", "dismissed"}:
        raise HTTPException(status_code=422, detail="status must be new/acknowledged/dismissed")
    row = db.execute(text("SELECT id FROM alerts WHERE id = :id"), {"id": alert_id}).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.execute(text("UPDATE alerts SET status = :s, acknowledged_by = :u WHERE id = :id"),
               {"s": body.status, "u": user["id"], "id": alert_id})
    db.commit()
    record_audit(db, user, "update", f"alert:{alert_id}", detail={"status": body.status}, ip=client_ip(request))
    return {"id": alert_id, "status": body.status}
