"""Model 1 — gap analysis. Geometric coverage gaps (PostGIS) + department and
district distribution, for the "uncovered zones / ageing infrastructure" report.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db

router = APIRouter(prefix="/api/coverage", tags=["coverage"])


@router.get("/gaps")
def coverage_gaps(db: Session = Depends(get_db), user=Depends(get_current_user)):
    total = db.execute(text("SELECT count(*) AS n FROM cameras")).fetchone().n

    gaps = db.execute(text(
        "SELECT district, severity, reason, camera_count, "
        "       ST_AsGeoJSON(region) AS region_geojson, "
        "       ST_X(center) AS lon, ST_Y(center) AS lat "
        "FROM coverage_gaps "
        "ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END"
    )).mappings().all()

    dept_rows = db.execute(text(
        "SELECT d.name, d.kind, count(c.id) AS camera_count "
        "FROM departments d LEFT JOIN cameras c ON c.department_id = d.id "
        "GROUP BY d.id, d.name, d.kind ORDER BY camera_count DESC"
    )).fetchall()
    unclassified = db.execute(text("SELECT count(*) AS n FROM cameras WHERE department_id IS NULL")).fetchone().n

    districts = db.execute(text(
        "SELECT district, count(*) AS camera_count, "
        "       count(*) FILTER (WHERE status IN ('down','degraded')) AS unhealthy "
        "FROM cameras WHERE district IS NOT NULL GROUP BY district ORDER BY camera_count ASC"
    )).mappings().all()

    departments = [
        {"department": r.name, "kind": r.kind, "camera_count": r.camera_count,
         "pct_of_total": round(100 * r.camera_count / total, 1) if total else 0.0}
        for r in dept_rows
    ]
    if unclassified:
        departments.append({"department": "Unclassified", "kind": "other",
                            "camera_count": unclassified,
                            "pct_of_total": round(100 * unclassified / total, 1) if total else 0.0})

    return {
        "method": "Geometric gap zones (PostGIS) + department/district coverage distribution",
        "total_cameras": total,
        "gaps": [dict(g) for g in gaps],
        "departments": departments,
        "districts": [dict(d) for d in districts],
        "uncovered_departments": [d["department"] for d in departments if d["camera_count"] == 0],
    }
