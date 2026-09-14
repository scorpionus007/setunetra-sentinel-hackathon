"""Model 3 — VMS Federation & Middleware.

Registers departmental VMS, pulls their events through pluggable adapters over a
metadata bus, and runs a deterministic cross-system correlation engine that links
the same entity across multiple systems + the registry watchlist.
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text

from app.adapters import get_adapter
import app.adapters.mock_adapters  # noqa: F401  (registers the vendor adapters)
from app.auth import client_ip, get_current_user, record_audit, require_role
from app.db import get_db

router = APIRouter(prefix="/api/vms", tags=["federation"])


@router.get("")
def list_systems(db=Depends(get_db), user=Depends(get_current_user)):
    rows = db.execute(text(
        "SELECT v.id, v.name, v.vendor, v.adapter_type, v.status, v.enabled, "
        "       v.camera_count, v.last_sync, v.last_error, v.base_url, d.name AS department "
        "FROM vms_systems v LEFT JOIN departments d ON d.id = v.department_id "
        "ORDER BY v.name"
    )).mappings().all()
    return [dict(r) for r in rows]


@router.get("/events")
def list_events(limit: int = 50, db=Depends(get_db), user=Depends(get_current_user)):
    rows = db.execute(text(
        "SELECT fe.id, fe.event_type, fe.payload, fe.occurred_at, fe.correlation_id, "
        "       v.name AS vms_name, v.vendor, fe.camera_external_id, c.location_name "
        "FROM federated_events fe "
        "JOIN vms_systems v ON v.id = fe.vms_id "
        "LEFT JOIN cameras c ON c.id = fe.camera_id "
        "ORDER BY fe.occurred_at DESC LIMIT :lim"
    ), {"lim": min(limit, 200)}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/correlations")
def list_correlations(db=Depends(get_db), user=Depends(get_current_user)):
    rows = db.execute(text(
        "SELECT correlation_key, rule, event_count, vms_count, summary, first_seen, last_seen "
        "FROM event_correlations ORDER BY last_seen DESC"
    )).mappings().all()
    return [dict(r) for r in rows]


@router.get("/analytics")
def federated_analytics(db=Depends(get_db), user=Depends(get_current_user)):
    """Federated analytics report — counts per system, per event type, correlations."""
    per_system = db.execute(text(
        "SELECT v.name, v.vendor, v.status, count(fe.id) AS events "
        "FROM vms_systems v LEFT JOIN federated_events fe ON fe.vms_id = v.id "
        "GROUP BY v.id, v.name, v.vendor, v.status ORDER BY events DESC"
    )).mappings().all()
    per_type = db.execute(text(
        "SELECT event_type, count(*) AS n FROM federated_events GROUP BY event_type ORDER BY n DESC"
    )).mappings().all()
    totals = db.execute(text(
        "SELECT (SELECT count(*) FROM vms_systems) AS systems, "
        "       (SELECT count(*) FROM vms_systems WHERE status='online') AS online, "
        "       (SELECT count(*) FROM federated_events) AS events, "
        "       (SELECT count(*) FROM event_correlations) AS correlations"
    )).mappings().first()
    return {
        "totals": dict(totals),
        "per_system": [dict(r) for r in per_system],
        "per_event_type": [dict(r) for r in per_type],
    }


def _run_correlation(db) -> list[dict]:
    """Deterministic rule: a plate reported by >=2 distinct sources (VMS and/or
    the registry watchlist) within 30 min is one correlated movement. Links the
    contributing events and raises an alert when the plate is on the watchlist.
    """
    plates = db.execute(text(
        "SELECT payload->>'plate' AS plate, "
        "       count(DISTINCT vms_id) AS vms_count, count(*) AS ev_count "
        "FROM federated_events "
        "WHERE payload ? 'plate' AND occurred_at > now() - interval '30 minutes' "
        "GROUP BY payload->>'plate'"
    )).mappings().all()

    results = []
    for p in plates:
        plate = p["plate"]
        if not plate:
            continue
        wl = db.execute(text("SELECT id, priority FROM watchlist WHERE value = :v AND active LIMIT 1"),
                        {"v": plate}).mappings().first()
        sources = p["vms_count"] + (1 if wl else 0)
        if sources < 2:
            continue

        key = f"plate:{plate}"
        summary = (f"{plate} reported by {p['vms_count']} VMS"
                   + (" + registry watchlist" if wl else "")
                   + f" within 30 min ({p['ev_count']} events)")
        db.execute(text("DELETE FROM event_correlations WHERE correlation_key = :k"), {"k": key})
        corr = db.execute(text(
            "INSERT INTO event_correlations (correlation_key, rule, event_count, vms_count, summary) "
            "VALUES (:k, 'same_plate_multi_source_30min', :ec, :vc, :s) RETURNING id"
        ), {"k": key, "ec": p["ev_count"], "vc": p["vms_count"], "s": summary}).scalar()

        db.execute(text(
            "UPDATE federated_events SET correlation_id = :cid "
            "WHERE payload->>'plate' = :v AND occurred_at > now() - interval '30 minutes'"
        ), {"cid": corr, "v": plate})

        if wl:
            db.execute(text(
                "INSERT INTO alerts (kind, severity, message, watchlist_id, correlation_id, source_system) "
                "VALUES ('federation_correlation', :sev, :msg, :wid, :cid, 'Federation engine')"
            ), {
                "sev": "critical" if wl["priority"] == "critical" else "high",
                "msg": f"Watchlist vehicle {plate} correlated across {p['vms_count']} systems",
                "wid": wl["id"], "cid": corr,
            })
        results.append({"plate": plate, "sources": sources, "summary": summary, "watchlist": bool(wl)})
    db.commit()
    return results


@router.post("/{vms_id}/sync")
def sync_system(vms_id: str, request: Request, db=Depends(get_db),
                user=Depends(require_role("dept_officer"))):
    system = db.execute(text(
        "SELECT id, name, vendor, adapter_type, status, base_url, auth_ref FROM vms_systems WHERE id = :id"
    ), {"id": vms_id}).mappings().first()
    if not system:
        raise HTTPException(status_code=404, detail="VMS not found")

    watch_values = [r[0] for r in db.execute(text(
        "SELECT value FROM watchlist WHERE type='vehicle' AND active"
    )).all()]

    try:
        adapter = get_adapter(dict(system))
        health = adapter.health()
        events = adapter.poll_events(watch_values=watch_values)
    except Exception as exc:
        db.execute(text("UPDATE vms_systems SET last_error = :e, status='degraded' WHERE id = :id"),
                   {"e": str(exc)[:200], "id": vms_id})
        db.commit()
        record_audit(db, user, "vms_sync", f"vms:{system['name']}", detail={"error": str(exc)},
                     ip=client_ip(request), outcome="error")
        raise HTTPException(status_code=502, detail=f"Adapter error: {exc}")

    inserted = 0
    for ev in events:
        cam = db.execute(text("SELECT id FROM cameras WHERE external_id = :e"),
                         {"e": ev.get("camera_external_id")}).scalar()
        db.execute(text(
            "INSERT INTO federated_events (vms_id, external_event_id, camera_external_id, camera_id, event_type, payload) "
            "VALUES (:vid, :eid, :cext, :cid, :etype, CAST(:payload AS JSONB))"
        ), {
            "vid": vms_id, "eid": ev.get("external_event_id"),
            "cext": ev.get("camera_external_id"), "cid": cam,
            "etype": ev.get("event_type"),
            "payload": json.dumps(ev.get("payload") or {}),
        })
        inserted += 1

    db.execute(text(
        "UPDATE vms_systems SET last_sync = now(), last_error = NULL, "
        "status = :st, camera_count = GREATEST(camera_count, :cc) WHERE id = :id"
    ), {"st": health["status"] if health["status"] != "offline" else "degraded",
        "cc": len(adapter.list_cameras()), "id": vms_id})
    db.commit()

    correlations = _run_correlation(db)
    record_audit(db, user, "vms_sync", f"vms:{system['name']}",
                 detail={"events": inserted, "correlations": len(correlations)}, ip=client_ip(request))
    return {
        "vms": system["name"],
        "health": health,
        "events_ingested": inserted,
        "correlations": correlations,
    }
