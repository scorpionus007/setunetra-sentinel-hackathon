"""Model 1 — camera onboarding: manual entry, bulk import (CSV/JSON), API.

Every onboarding path runs the same validation and the same audited upsert, so a
camera added by CSV is indistinguishable from one added by API. Input is strictly
validated (Pydantic + range checks); we never probe the supplied URLs (SSRF-safe).
"""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import client_ip, get_current_user, record_audit, require_role
from app.db import get_db

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

_VALID_TYPES = {"fixed", "ptz", "dome", "bullet", "anpr", "thermal", "other"}
CSV_COLUMNS = ["external_id", "location_name", "district", "lat", "lon",
               "department", "camera_type", "manufacturer", "model_name",
               "ip_address", "resolution", "fps", "rtsp_url"]


class CameraIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    external_id: str = Field(min_length=1, max_length=64)
    location_name: str = Field(min_length=1, max_length=200)
    district: str | None = None
    lat: float | None = None
    lon: float | None = None
    department: str | None = None
    camera_type: str = "fixed"
    manufacturer: str | None = None
    model_name: str | None = None
    ip_address: str | None = None
    resolution: str | None = None
    fps: int | None = None
    rtsp_url: str | None = None

    @field_validator("camera_type")
    @classmethod
    def _type_ok(cls, v):
        v = (v or "fixed").lower()
        return v if v in _VALID_TYPES else "other"

    @field_validator("lat")
    @classmethod
    def _lat_ok(cls, v):
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("lat out of range")
        return v

    @field_validator("lon")
    @classmethod
    def _lon_ok(cls, v):
        if v is not None and not (-180 <= v <= 180):
            raise ValueError("lon out of range")
        return v


class BulkIn(BaseModel):
    csv: str | None = None
    cameras: list[CameraIn] | None = None


def _validate_row(db, cam: CameraIn) -> list[str]:
    errors = []
    exists = db.execute(text("SELECT 1 FROM cameras WHERE external_id = :e"), {"e": cam.external_id}).fetchone()
    if exists:
        errors.append(f"external_id '{cam.external_id}' already exists")
    if cam.department:
        dept = db.execute(text("SELECT 1 FROM departments WHERE name = :n"), {"n": cam.department}).fetchone()
        if not dept:
            errors.append(f"unknown department '{cam.department}'")
    if (cam.lat is None) != (cam.lon is None):
        errors.append("lat and lon must be provided together")
    return errors


def _insert(db, cam: CameraIn, source: str, user) -> None:
    dept_id = None
    if cam.department:
        dept_id = db.execute(text("SELECT id FROM departments WHERE name = :n"), {"n": cam.department}).scalar()
    loc = "ST_SetSRID(ST_MakePoint(:lon,:lat),4326)" if cam.lat is not None else "NULL"
    db.execute(text(
        f"INSERT INTO cameras (external_id, location_name, district, location, department_id, "
        f"camera_type, manufacturer, model_name, ip_address, resolution, fps, rtsp_url, status, source, onboarded_by) "
        f"VALUES (:ext, :name, :district, {loc}, :dept, :ctype, :manu, :model, :ip, :res, :fps, :rtsp, "
        f"'unknown', :source, :uid)"
    ), {
        "ext": cam.external_id, "name": cam.location_name, "district": cam.district,
        "lon": cam.lon, "lat": cam.lat, "dept": dept_id, "ctype": cam.camera_type,
        "manu": cam.manufacturer, "model": cam.model_name, "ip": cam.ip_address,
        "res": cam.resolution, "fps": cam.fps, "rtsp": cam.rtsp_url, "source": source, "uid": user["id"],
    })


@router.get("/template")
def csv_template(user=Depends(get_current_user)):
    example = "31,Sample Junction Camera,Ahmedabad,23.03,72.58,Police,ptz,Hikvision,DS-2CD,10.0.0.31,1080p,25,rtsp://10.0.0.31/stream"
    return {"columns": CSV_COLUMNS, "header": ",".join(CSV_COLUMNS), "example_row": example}


@router.post("/validate")
def validate(body: BulkIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    cams, parse_errors = _parse(body)
    results = []
    seen = set()
    for i, cam in enumerate(cams):
        errs = _validate_row(db, cam)
        if cam.external_id in seen:
            errs.append("duplicate external_id within batch")
        seen.add(cam.external_id)
        results.append({"row": i + 1, "external_id": cam.external_id, "valid": not errs, "errors": errs})
    return {"parse_errors": parse_errors, "rows": results,
            "valid_count": sum(1 for r in results if r["valid"]), "total": len(results)}


@router.post("/manual", status_code=201)
def onboard_manual(cam: CameraIn, request: Request, db: Session = Depends(get_db),
                   user=Depends(require_role("dept_officer"))):
    errs = _validate_row(db, cam)
    if errs:
        raise HTTPException(status_code=422, detail={"errors": errs})
    _insert(db, cam, "manual", user)
    db.commit()
    record_audit(db, user, "create", f"camera:{cam.external_id}", detail={"method": "manual"}, ip=client_ip(request))
    return {"onboarded": cam.external_id}


@router.post("/bulk")
def onboard_bulk(body: BulkIn, request: Request, db: Session = Depends(get_db),
                 user=Depends(require_role("dept_officer"))):
    cams, parse_errors = _parse(body)
    inserted, failed, seen = [], [], set()
    for i, cam in enumerate(cams):
        errs = _validate_row(db, cam)
        if cam.external_id in seen:
            errs.append("duplicate external_id within batch")
        seen.add(cam.external_id)
        if errs:
            failed.append({"row": i + 1, "external_id": cam.external_id, "errors": errs})
            continue
        _insert(db, cam, "bulk", user)
        inserted.append(cam.external_id)
    db.commit()
    record_audit(db, user, "bulk_onboard", "cameras",
                 detail={"inserted": len(inserted), "failed": len(failed)}, ip=client_ip(request))
    return {"inserted": inserted, "inserted_count": len(inserted),
            "failed": failed, "parse_errors": parse_errors}


def _parse(body: BulkIn) -> tuple[list[CameraIn], list[str]]:
    if body.cameras:
        return list(body.cameras), []
    if not body.csv:
        return [], ["no csv or cameras provided"]
    cams, errors = [], []
    reader = csv.DictReader(io.StringIO(body.csv.strip()))
    for i, raw in enumerate(reader):
        try:
            cleaned = {k: (v.strip() if isinstance(v, str) and v.strip() != "" else None) for k, v in raw.items()}
            cams.append(CameraIn(
                external_id=cleaned.get("external_id"),
                location_name=cleaned.get("location_name"),
                district=cleaned.get("district"),
                lat=float(cleaned["lat"]) if cleaned.get("lat") else None,
                lon=float(cleaned["lon"]) if cleaned.get("lon") else None,
                department=cleaned.get("department"),
                camera_type=cleaned.get("camera_type") or "fixed",
                manufacturer=cleaned.get("manufacturer"),
                model_name=cleaned.get("model_name"),
                ip_address=cleaned.get("ip_address"),
                resolution=cleaned.get("resolution"),
                fps=int(cleaned["fps"]) if cleaned.get("fps") else None,
                rtsp_url=cleaned.get("rtsp_url"),
            ))
        except Exception as exc:
            errors.append(f"row {i + 1}: {exc}")
    return cams, errors
