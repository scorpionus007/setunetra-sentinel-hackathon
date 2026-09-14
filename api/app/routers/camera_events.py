"""Model 2 — operator/rule-based event tagging + camera-wise searchable index.

No AI: events are created by operators (or by a rule) and are fully searchable by
camera, type, and free text (e.g. a plate string or description).
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth import client_ip, get_current_user, record_audit, require_role
from app.db import get_db

router = APIRouter(prefix="/api/camera-events", tags=["events"])

_VALID_TYPES = {"observation", "vehicle_of_interest", "incident", "maintenance", "watchlist_hit", "other"}


class EventBody(BaseModel):
    camera_external_id: str
    event_type: str = "observation"
    label: str = Field(min_length=1, max_length=300)
    note: str | None = None


@router.get("")
def list_events(q: str = "", camera_external_id: str = "", event_type: str = "",
                limit: int = 50, db=Depends(get_db), user=Depends(get_current_user)):
    clauses = ["1=1"]
    params: dict = {"lim": min(limit, 200)}
    if q:
        clauses.append("(ce.label ILIKE :q OR ce.note ILIKE :q)")
        params["q"] = f"%{q}%"
    if camera_external_id:
        clauses.append("c.external_id = :cext")
        params["cext"] = camera_external_id
    if event_type:
        clauses.append("ce.event_type = :etype")
        params["etype"] = event_type
    where = " AND ".join(clauses)
    rows = db.execute(text(
        f"SELECT ce.id, ce.event_type, ce.label, ce.note, ce.occurred_at, "
        f"       c.external_id AS camera_external_id, c.location_name, c.district, "
        f"       u.email AS tagged_by, w.value AS watchlist_value "
        f"FROM camera_events ce "
        f"JOIN cameras c ON c.id = ce.camera_id "
        f"LEFT JOIN users u ON u.id = ce.tagged_by "
        f"LEFT JOIN watchlist w ON w.id = ce.watchlist_id "
        f"WHERE {where} ORDER BY ce.occurred_at DESC LIMIT :lim"
    ), params).mappings().all()
    return [dict(r) for r in rows]


@router.post("")
def tag_event(body: EventBody, request: Request, db=Depends(get_db),
              user=Depends(require_role("station_officer"))):
    if body.event_type not in _VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"event_type must be one of {sorted(_VALID_TYPES)}")
    cam = db.execute(text("SELECT id FROM cameras WHERE external_id = :e"),
                     {"e": body.camera_external_id}).scalar()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Auto-link to a watchlist entry if the label matches one (rule-based hit).
    wl = db.execute(text("SELECT id FROM watchlist WHERE value = :v AND active LIMIT 1"),
                    {"v": body.label.strip()}).scalar()
    event_type = "watchlist_hit" if wl else body.event_type

    eid = db.execute(text(
        "INSERT INTO camera_events (camera_id, event_type, label, watchlist_id, tagged_by, note) "
        "VALUES (:cid, :etype, :label, :wid, :uid, :note) RETURNING id"
    ), {"cid": cam, "etype": event_type, "label": body.label.strip(),
        "wid": wl, "uid": user["id"], "note": body.note}).scalar()

    if wl:
        db.execute(text(
            "INSERT INTO alerts (kind, severity, message, camera_id, watchlist_id, camera_event_id, source_system) "
            "VALUES ('watchlist_hit', 'high', :msg, :cid, :wid, :eid, 'Operator tag')"
        ), {"msg": f"Watchlist match tagged: {body.label.strip()}", "cid": cam, "wid": wl, "eid": eid})
    db.commit()
    record_audit(db, user, "tag_event", f"camera:{body.camera_external_id}",
                 detail={"label": body.label.strip(), "type": event_type}, ip=client_ip(request))
    return {"id": str(eid), "event_type": event_type, "watchlist_hit": bool(wl)}
