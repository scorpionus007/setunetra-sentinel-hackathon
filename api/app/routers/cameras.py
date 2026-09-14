"""Model 1 — Camera registry (read + manage) and live snapshot/activation.

Department-wise RBAC scoping:
  * admin / auditor / viewer  → whole state (viewer is read-only control room)
  * dept_officer              → own department only
  * station_officer           → own district only
"""
import os
import time

import redis
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import client_ip, get_current_user, record_audit, require_role
from app.db import get_db

router = APIRouter(prefix="/api/cameras", tags=["cameras"])

_VALID_STORAGE_TIERS = {"hot", "warm", "cold"}
_redis = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))

_LIST_QUERY = """
    SELECT c.id, c.external_id, c.location_name, c.district, c.status,
           c.camera_type, c.manufacturer, c.model_name, c.ip_address,
           c.resolution, c.fps, c.codec, c.rtsp_url, c.hls_url,
           c.owner_contact, c.install_date, c.retention_days,
           c.storage_tier, c.priority_tier, c.source, c.last_seen,
           ST_Y(c.location) AS lat, ST_X(c.location) AS lon,
           d.name AS department, d.kind AS department_kind,
           s.name AS station, v.name AS vms_name
    FROM cameras c
    LEFT JOIN departments d ON d.id = c.department_id
    LEFT JOIN stations s ON s.id = c.station_id
    LEFT JOIN vms_systems v ON v.id = c.vms_id
"""


def _serialize(cam) -> dict:
    return {
        "id": str(cam.id),
        "external_id": cam.external_id,
        "location_name": cam.location_name,
        "district": cam.district,
        "status": cam.status,
        "camera_type": cam.camera_type,
        "manufacturer": cam.manufacturer,
        "model_name": cam.model_name,
        "ip_address": cam.ip_address,
        "resolution": cam.resolution,
        "fps": cam.fps,
        "codec": cam.codec,
        "rtsp_url": cam.rtsp_url,
        "hls_url": cam.hls_url,
        "owner_contact": cam.owner_contact,
        "install_date": cam.install_date.isoformat() if cam.install_date else None,
        "retention_days": cam.retention_days,
        "storage_tier": cam.storage_tier,
        "priority_tier": cam.priority_tier,
        "source": cam.source,
        "last_seen": cam.last_seen.isoformat() if cam.last_seen else None,
        "lat": cam.lat,
        "lon": cam.lon,
        "department": cam.department,
        "department_kind": cam.department_kind,
        "station": cam.station,
        "vms_name": cam.vms_name,
    }


def _scope_clause(user) -> tuple[str, dict]:
    """Return an extra WHERE fragment + params for the user's jurisdiction."""
    if user["role"] == "dept_officer" and user["department_id"]:
        return " WHERE c.department_id = :dept ", {"dept": user["department_id"]}
    if user["role"] == "station_officer" and user["district"]:
        return " WHERE c.district = :district ", {"district": user["district"]}
    return "", {}


@router.get("")
def list_cameras(db: Session = Depends(get_db), user=Depends(get_current_user)):
    where, params = _scope_clause(user)
    rows = db.execute(text(_LIST_QUERY + where + " ORDER BY c.external_id::int"), params).fetchall()
    return [_serialize(c) for c in rows]


@router.get("/health")
def camera_health(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.execute(text(
        """
        SELECT DISTINCT ON (ch.camera_id)
               c.external_id AS camera_id, ch.status, ch.last_frame_ts, ch.latency_ms, ch.ts, ch.note
        FROM camera_health ch
        JOIN cameras c ON c.id = ch.camera_id
        ORDER BY ch.camera_id, ch.ts DESC
        """
    )).fetchall()
    return [
        {
            "camera_id": r.camera_id,
            "status": r.status,
            "last_frame_ts": r.last_frame_ts.isoformat() if r.last_frame_ts else None,
            "latency_ms": r.latency_ms,
            "note": r.note,
            "ts": r.ts.isoformat() if r.ts else None,
        }
        for r in rows
    ]


@router.get("/{external_id}")
def get_camera(external_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = db.execute(text(_LIST_QUERY + " WHERE c.external_id = :ext"), {"ext": external_id}).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return _serialize(row)


class StorageTierOverrideIn(BaseModel):
    storage_tier: str | None = None
    retention_days: int | None = None


@router.patch("/{external_id}/storage-tier")
def override_storage_tier(external_id: str, body: StorageTierOverrideIn, request: Request,
                          db: Session = Depends(get_db), user=Depends(require_role("dept_officer"))):
    if body.storage_tier is not None and body.storage_tier not in _VALID_STORAGE_TIERS:
        raise HTTPException(status_code=400, detail=f"storage_tier must be one of {sorted(_VALID_STORAGE_TIERS)}")
    row = db.execute(text("SELECT id FROM cameras WHERE external_id = :ext"), {"ext": external_id}).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    sets, params = [], {"id": row.id}
    if body.storage_tier is not None:
        sets.append("storage_tier = :st")
        params["st"] = body.storage_tier
    if body.retention_days is not None:
        sets.append("retention_days = :rd")
        params["rd"] = body.retention_days
    if sets:
        sets.append("updated_at = now()")
        db.execute(text(f"UPDATE cameras SET {', '.join(sets)} WHERE id = :id"), params)
        db.commit()
    record_audit(db, user, "update", f"camera:{external_id}",
                 detail={"storage_tier": body.storage_tier, "retention_days": body.retention_days},
                 ip=client_ip(request))
    return {"external_id": external_id, "storage_tier": body.storage_tier, "retention_days": body.retention_days}


@router.delete("/{external_id}")
def delete_camera(external_id: str, request: Request, db: Session = Depends(get_db),
                  user=Depends(require_role("admin"))):
    row = db.execute(text("SELECT id FROM cameras WHERE external_id = :ext"), {"ext": external_id}).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    db.execute(text("DELETE FROM cameras WHERE id = :id"), {"id": row.id})
    db.commit()
    record_audit(db, user, "delete", f"camera:{external_id}", ip=client_ip(request))
    return {"deleted": external_id}


@router.get("/{external_id}/snapshot")
def camera_snapshot(external_id: str, user=Depends(get_current_user)):
    """Latest raw frame for the live view (ingest publishes latest_frame:{id})."""
    blob = _redis.get(f"latest_frame:{external_id}")
    if not blob:
        return Response(status_code=204)
    return Response(content=blob, media_type="image/jpeg")


@router.post("/{external_id}/activate")
def activate_camera(external_id: str, user=Depends(get_current_user)):
    """Request a camera into the ingest active pool (Model 2 unified viewing)."""
    _redis.zadd("requested_cameras", {external_id: time.time()})
    return {"external_id": external_id, "requested": True}
