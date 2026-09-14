-- SetuNetra — Integrated CCTV Registry, Unified Viewing & VMS Federation Platform
-- Gujarat Police Innovation Challenge 2026
--
-- This schema covers three integration models WITHOUT any AI/ML analytics:
--   Model 1  Registry & GIS Foundation  (mandatory)   — cameras, departments,
--            stations, health, coverage gaps
--   Model 2  Unified Viewing & Metadata                — camera_events (operator /
--            rule-based tagging), watchlist, alerts
--   Model 3  VMS Federation & Middleware               — vms_systems, federated_events,
--            event_correlations
--   Cyber    Security architecture cutting across all  — users/RBAC, audit_log,
--            security_events, external_lookups
--
-- All "analytics" here are deterministic and rule-based (camera offline, manual
-- operator tags, cross-VMS correlation) — there is no vehicle/plate/face inference.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- crypt()/gen_salt() for password hashing

-- ============================================================================
-- Organisational scope  +  Cybersecurity: identity & RBAC
-- ============================================================================

CREATE TABLE departments (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT UNIQUE NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'other'
                  CHECK (kind IN ('police','municipal','transport','panchayat','health','institution','other')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE stations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    department_id   UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    district        TEXT,
    jurisdiction    GEOMETRY(POLYGON, 4326),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Department-wise role-based access control (hackathon: "Department-wise RBAC").
--   admin           — statewide super user
--   dept_officer    — scoped to one department
--   station_officer — scoped to one station
--   auditor         — read-only across security/audit surfaces
--   viewer          — read-only operational surfaces
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           TEXT UNIQUE NOT NULL,
    full_name       TEXT,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'viewer'
                      CHECK (role IN ('admin','dept_officer','station_officer','auditor','viewer')),
    department_id   UUID REFERENCES departments(id),
    station_id      UUID REFERENCES stations(id),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    last_login      TIMESTAMPTZ,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- Model 1 — Camera Registry & GIS Foundation
-- ============================================================================

CREATE TABLE cameras (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id     TEXT UNIQUE NOT NULL,          -- stable id used across onboarding sources
    department_id   UUID REFERENCES departments(id),
    station_id      UUID REFERENCES stations(id),
    location_name   TEXT,                          -- human place name, e.g. "Chimanbhai Bridge"
    district        TEXT,
    location        GEOMETRY(POINT, 4326),         -- lon/lat; nullable until geocoded
    -- Infrastructure / metadata (Model 1: "location, department, camera type,
    -- ownership, connectivity status, storage details, other infrastructure")
    camera_type     TEXT NOT NULL DEFAULT 'fixed'
                      CHECK (camera_type IN ('fixed','ptz','dome','bullet','anpr','thermal','other')),
    manufacturer    TEXT,
    model_name      TEXT,
    ip_address      TEXT,
    resolution      TEXT,
    fps             INTEGER,
    codec           TEXT,
    rtsp_url        TEXT,
    whep_url        TEXT,
    hls_url         TEXT,
    owner_contact   TEXT,
    install_date    DATE,
    retention_days  INTEGER NOT NULL DEFAULT 30,
    storage_tier    TEXT NOT NULL DEFAULT 'warm' CHECK (storage_tier IN ('hot','warm','cold')),
    priority_tier   TEXT NOT NULL DEFAULT 'medium' CHECK (priority_tier IN ('critical','medium','low')),
    -- Connectivity / health rollup
    status          TEXT NOT NULL DEFAULT 'unknown' CHECK (status IN ('live','down','degraded','unknown')),
    last_seen       TIMESTAMPTZ,
    -- Model 3 linkage: which federated VMS (if any) this camera was discovered through
    source          TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','bulk','api','federated')),
    vms_id          UUID,                          -- FK added after vms_systems is defined
    onboarded_by    UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_cameras_location ON cameras USING GIST (location);
CREATE INDEX idx_cameras_department ON cameras (department_id);
CREATE INDEX idx_cameras_status ON cameras (status);

-- Health / maintenance-status monitoring (Model 1)
CREATE TABLE camera_health (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id       UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
    status          TEXT NOT NULL,                 -- live / down / degraded
    last_frame_ts   TIMESTAMPTZ,
    latency_ms      INTEGER,
    note            TEXT
);
CREATE INDEX idx_camera_health_camera_ts ON camera_health (camera_id, ts DESC);

-- Gap-analysis output (Model 1: "gap-analysis reports for uncovered zones")
CREATE TABLE coverage_gaps (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    district        TEXT,
    station_id      UUID REFERENCES stations(id),
    region          GEOMETRY(POLYGON, 4326),
    center          GEOMETRY(POINT, 4326),
    severity        TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('high','medium','low')),
    reason          TEXT,                          -- e.g. "no camera within 3km", "ageing infra >7y"
    camera_count    INTEGER NOT NULL DEFAULT 0,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- Model 2 — Unified Viewing & (rule-based) Metadata
-- ============================================================================

-- Watchlist of entities of interest (stolen/blacklisted vehicles, wanted/missing
-- persons). No AI reads these — matches are entered by operators or by rule.
CREATE TABLE watchlist (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type        TEXT NOT NULL CHECK (type IN ('vehicle','person','object','other')),
    value       TEXT NOT NULL,                     -- plate string / name / identifier
    reason      TEXT,
    priority    TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('critical','medium','low')),
    active      BOOLEAN NOT NULL DEFAULT true,
    added_by    UUID REFERENCES users(id),
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_watchlist_value ON watchlist (value);

-- Operator / rule-based event tagging + camera-wise searchable index (Model 2:
-- "event tagging and camera-wise indexing, searchable vehicle-movement records").
CREATE TABLE camera_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id       UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL DEFAULT 'observation'
                      CHECK (event_type IN ('observation','vehicle_of_interest','incident','maintenance','watchlist_hit','other')),
    label           TEXT NOT NULL,                 -- free text / plate / description
    watchlist_id    UUID REFERENCES watchlist(id),
    tagged_by       UUID REFERENCES users(id),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    note            TEXT,
    metadata        JSONB
);
CREATE INDEX idx_camera_events_camera_ts ON camera_events (camera_id, occurred_at DESC);
CREATE INDEX idx_camera_events_label ON camera_events (label);
CREATE INDEX idx_camera_events_type ON camera_events (event_type);

-- ============================================================================
-- Model 3 — VMS Federation & Middleware
-- ============================================================================

-- Registered external VMS / departmental systems, each reached through a
-- pluggable adapter (Model 3: "adapter/plugin architecture for multiple VMS
-- vendors", "extensible connector framework").
CREATE TABLE vms_systems (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL,
    vendor          TEXT NOT NULL,                 -- Hikvision / Milestone / CP-Plus / Genetec / ONVIF ...
    adapter_type    TEXT NOT NULL
                      CHECK (adapter_type IN ('onvif','hikvision','milestone','cpplus','genetec','rtsp','generic_rest')),
    department_id   UUID REFERENCES departments(id),
    base_url        TEXT,
    auth_ref        TEXT,                          -- name of the secret/credential, NEVER the secret itself
    enabled         BOOLEAN NOT NULL DEFAULT true,
    status          TEXT NOT NULL DEFAULT 'unknown' CHECK (status IN ('online','offline','degraded','unknown')),
    camera_count    INTEGER NOT NULL DEFAULT 0,
    last_sync       TIMESTAMPTZ,
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE cameras
    ADD CONSTRAINT fk_cameras_vms FOREIGN KEY (vms_id) REFERENCES vms_systems(id) ON DELETE SET NULL;

-- Events pulled from federated systems through the metadata-exchange bus.
CREATE TABLE federated_events (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vms_id              UUID NOT NULL REFERENCES vms_systems(id) ON DELETE CASCADE,
    external_event_id   TEXT,                      -- id in the source system
    camera_external_id  TEXT,                      -- source camera ref
    camera_id           UUID REFERENCES cameras(id),
    event_type          TEXT NOT NULL,             -- motion / tamper / offline / door / analytic-tag ...
    payload             JSONB,
    correlation_id      UUID,                      -- set when correlated across systems
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_federated_events_vms_ts ON federated_events (vms_id, occurred_at DESC);
CREATE INDEX idx_federated_events_corr ON federated_events (correlation_id);

-- Cross-system event correlation output (Model 3: "cross-system event-correlation
-- engine"). Groups federated_events that a deterministic rule links together.
CREATE TABLE event_correlations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    correlation_key TEXT NOT NULL,                 -- rule key, e.g. plate/tag + time window
    rule            TEXT NOT NULL,                 -- which correlation rule fired
    event_count     INTEGER NOT NULL DEFAULT 0,
    vms_count       INTEGER NOT NULL DEFAULT 0,
    summary         TEXT,
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- Unified alerts (rule-based, no AI)
-- ============================================================================
-- Alerts come from deterministic sources: a camera going offline, an operator
-- watchlist tag, or a cross-VMS correlation — never from an inference model.
CREATE TABLE alerts (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kind                TEXT NOT NULL
                          CHECK (kind IN ('camera_offline','camera_tamper','watchlist_hit','federation_correlation','security','other')),
    severity            TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('critical','high','medium','low')),
    message             TEXT NOT NULL,
    camera_id           UUID REFERENCES cameras(id),
    watchlist_id        UUID REFERENCES watchlist(id),
    camera_event_id     UUID REFERENCES camera_events(id),
    correlation_id      UUID REFERENCES event_correlations(id),
    source_system       TEXT,                      -- which VMS / subsystem raised it
    status              TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','acknowledged','dismissed')),
    acknowledged_by     UUID REFERENCES users(id),
    ts                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_alerts_status_ts ON alerts (status, ts DESC);

-- ============================================================================
-- Cybersecurity — audit trail, security events, external lookups
-- ============================================================================

-- Immutable audit trail of every mutating action (who / what / when / from where).
CREATE TABLE audit_log (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES users(id),
    user_email  TEXT,                              -- denormalised so the record survives user deletion
    role        TEXT,
    action      TEXT NOT NULL,                     -- create/update/delete/login/export/...
    resource    TEXT NOT NULL,                     -- e.g. camera:<id>, vms:<id>
    detail      JSONB,
    ip_address  TEXT,
    outcome     TEXT NOT NULL DEFAULT 'success' CHECK (outcome IN ('success','denied','error')),
    ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_log_ts ON audit_log (ts DESC);
CREATE INDEX idx_audit_log_user ON audit_log (user_id);

-- Security telemetry: failed logins, rate-limit trips, RBAC denials, anomalies.
CREATE TABLE security_events (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kind        TEXT NOT NULL
                  CHECK (kind IN ('login_failed','login_locked','rate_limited','access_denied','token_invalid','config_change','anomaly')),
    severity    TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('critical','high','medium','low')),
    email       TEXT,
    ip_address  TEXT,
    detail      TEXT,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_security_events_ts ON security_events (ts DESC);
CREATE INDEX idx_security_events_kind ON security_events (kind);

-- Mock external government-database adapters (VAHAN/Sarthi/eGujCop/AFIS/NAFIS).
-- Kept as a federation/enrichment surface; all responses are mocked & flagged.
CREATE TABLE external_lookups (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source          TEXT NOT NULL CHECK (source IN ('vahan','sarthi','egujcop','afis','nafis')),
    query_value     TEXT NOT NULL,
    response_json   JSONB,
    is_mocked       BOOLEAN NOT NULL DEFAULT true,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now()
);
