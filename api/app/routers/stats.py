"""Dashboard KPIs — a single roll-up for the landing view across all models."""
from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.auth import get_current_user
from app.db import get_db

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def stats(db=Depends(get_db), user=Depends(get_current_user)):
    totals = db.execute(text(
        "SELECT "
        " (SELECT count(*) FROM cameras) AS cameras, "
        " (SELECT count(*) FROM cameras WHERE status='live') AS live, "
        " (SELECT count(*) FROM cameras WHERE status='down') AS down, "
        " (SELECT count(*) FROM cameras WHERE status='degraded') AS degraded, "
        " (SELECT count(*) FROM cameras WHERE location IS NOT NULL) AS geocoded, "
        " (SELECT count(DISTINCT district) FROM cameras) AS districts, "
        " (SELECT count(*) FROM departments) AS departments, "
        " (SELECT count(*) FROM vms_systems) AS vms_total, "
        " (SELECT count(*) FROM vms_systems WHERE status='online') AS vms_online, "
        " (SELECT count(*) FROM alerts WHERE status='new') AS open_alerts, "
        " (SELECT count(*) FROM watchlist WHERE active) AS watchlist, "
        " (SELECT count(*) FROM coverage_gaps) AS coverage_gaps, "
        " (SELECT count(*) FROM camera_events) AS tagged_events, "
        " (SELECT count(*) FROM federated_events) AS federated_events, "
        " (SELECT count(*) FROM event_correlations) AS correlations"
    )).mappings().first()

    by_department = db.execute(text(
        "SELECT d.name AS department, d.kind, count(c.id) AS cameras, "
        "       count(c.id) FILTER (WHERE c.status='live') AS live "
        "FROM departments d LEFT JOIN cameras c ON c.department_id = d.id "
        "GROUP BY d.id, d.name, d.kind ORDER BY cameras DESC"
    )).mappings().all()

    by_district = db.execute(text(
        "SELECT district, count(*) AS cameras FROM cameras "
        "WHERE district IS NOT NULL GROUP BY district ORDER BY cameras DESC"
    )).mappings().all()

    by_type = db.execute(text(
        "SELECT camera_type, count(*) AS n FROM cameras GROUP BY camera_type ORDER BY n DESC"
    )).mappings().all()

    return {
        "totals": dict(totals),
        "by_department": [dict(r) for r in by_department],
        "by_district": [dict(r) for r in by_district],
        "by_type": [dict(r) for r in by_type],
    }
