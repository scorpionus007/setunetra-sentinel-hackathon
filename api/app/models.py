"""SQLAlchemy models mirroring contracts/schema.sql.

Only the tables needed for Day 1 (#11 registry & onboarding) are modeled
here. Add the rest as the features that need them come up — don't model
ahead of the day's task.
"""
import uuid

from sqlalchemy import Boolean, Column, Text, TIMESTAMP, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base
from geoalchemy2 import Geometry

Base = declarative_base()


class Department(Base):
    __tablename__ = "departments"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    name = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Station(Base):
    __tablename__ = "stations"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False)
    name = Column(Text, nullable=False)
    jurisdiction = Column(Geometry("POLYGON", srid=4326))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    external_id = Column(Text, unique=True, nullable=False)  # id from sandbox /api/ingest
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"))
    station_id = Column(UUID(as_uuid=True), ForeignKey("stations.id"))
    location_name = Column(Text)  # raw place name from the catalogue
    location = Column(Geometry("POINT", srid=4326))  # nullable until geocoded — see CONTEXT.md §3
    status = Column(Text, nullable=False, server_default="unknown")
    codec = Column(Text)
    resolution = Column(Text)
    rtsp_url = Column(Text)
    whep_url = Column(Text)
    hls_url = Column(Text)
    storage_tier = Column(Text, nullable=False, server_default="warm")
    priority_tier = Column(Text, nullable=False, server_default="medium")
    last_seen = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class ExternalLookup(Base):
    """#15 VAHAN/SARTHI/etc adapter audit trail — table existed in
    contracts/schema.sql since Day 0 but was never modeled or written to;
    every lookup (mocked or real) persists a row here."""

    __tablename__ = "external_lookups"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    source = Column(Text, nullable=False)  # CHECK vahan/sarthi/egujcop/afis/nafis — enforced in Postgres
    query_value = Column(Text, nullable=False)
    response_json = Column(JSONB)
    is_mocked = Column(Boolean, nullable=False, server_default="true")
    ts = Column(TIMESTAMP(timezone=True), server_default=func.now())
