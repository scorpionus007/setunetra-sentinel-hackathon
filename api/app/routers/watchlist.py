"""Watchlist CRUD — entities of interest (matched by operator/rule, not AI)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import client_ip, get_current_user, record_audit, require_role
from app.db import get_db

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

_VALID_TYPES = {"vehicle", "person", "object", "other"}
_VALID_PRIORITIES = {"critical", "medium", "low"}


class WatchlistIn(BaseModel):
    type: str
    value: str
    reason: str | None = None
    priority: str = "medium"


def _serialize(row) -> dict:
    return {
        "id": str(row.id),
        "type": row.type,
        "value": row.value,
        "reason": row.reason,
        "priority": row.priority,
        "active": row.active,
        "added_at": row.added_at.isoformat() if row.added_at else None,
    }


@router.get("")
def list_watchlist(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.execute(text(
        "SELECT id, type, value, reason, priority, active, added_at FROM watchlist ORDER BY added_at DESC"
    )).fetchall()
    return [_serialize(r) for r in rows]


@router.post("", status_code=201)
def add_watchlist_entry(entry: WatchlistIn, request: Request, db: Session = Depends(get_db),
                        user=Depends(require_role("dept_officer"))):
    if entry.type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {sorted(_VALID_TYPES)}")
    if entry.priority not in _VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"priority must be one of {sorted(_VALID_PRIORITIES)}")
    row = db.execute(text(
        "INSERT INTO watchlist (type, value, reason, priority, added_by) "
        "VALUES (:type, :value, :reason, :priority, :uid) "
        "RETURNING id, type, value, reason, priority, active, added_at"
    ), {"type": entry.type, "value": entry.value, "reason": entry.reason,
        "priority": entry.priority, "uid": user["id"]}).fetchone()
    db.commit()
    record_audit(db, user, "create", f"watchlist:{entry.value}", detail={"type": entry.type}, ip=client_ip(request))
    return _serialize(row)
