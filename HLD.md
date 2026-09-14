<div align="center">

<img src="web/public/emblem.png" width="96" alt="SetuNetra emblem" />

# SetuNetra — High-Level Design & Architecture

**Integrated Video Management & Analytics Platform**
Gujarat Police Innovation Challenge 2026 · Step-5 deliverable (HLD)

</div>

---

## 1. Purpose & scope

This document describes the high-level design of **SetuNetra** — a platform that
onboards, maps, views and federates the state's fragmented, multi-department CCTV
into a single command console **without replacing any existing VMS**. It implements
a hybrid of the challenge's **Model 1 (Registry & GIS)**, **Model 2 (Unified
Viewing)** and **Model 3 (VMS Federation)**, plus a cross-cutting cybersecurity
layer. All analytics are **deterministic and rule-based** — there is no ML in the
critical path, so the system is GPU-free, privacy-preserving and auditable.

## 2. Workflow & integration diagram

![SetuNetra workflow and integration](docs/workflow_integration.svg)

The same flow as a code-rendered graph:

```mermaid
flowchart TB
  subgraph S["Sources"]
    C["RTSP / ONVIF cameras<br/>(credentialed, TCP)"]
    V["Departmental VMS<br/>Hikvision · Milestone · CP-Plus · Genetec · ONVIF"]
  end
  subgraph IF["Ingest & Federation"]
    IG["Ingest service<br/>RTSP → JPEG · no ML · bounded pool"]
    AD["VMS adapter framework<br/>→ metadata bus"]
  end
  subgraph CORE["Core platform"]
    RE[("Redis<br/>frames + bus")]
    API["FastAPI core<br/>registry · federation+correlation · alerts · auth"]
    PG[("PostgreSQL + PostGIS<br/>system of record")]
  end
  WEB["React + Leaflet console<br/>Dashboard · Registry/GIS · Viewing · Federation · Security · Audit"]
  U["Command centre<br/>operators · officers · video walls"]

  C --> IG --> RE
  V --> AD --> API
  RE <--> API <--> PG
  API -- "JWT / REST" --> WEB --> U
  SEC["Security across all tiers: JWT · RBAC · lockout · rate-limit · headers · audit"]:::sec
  classDef sec fill:#FFF2E3,stroke:#F0D3AC,color:#D9741A;
```

## 3. Architecture overview

Four independent, horizontally scalable tiers communicating only through Redis and
PostgreSQL — services never import across the folder boundary.

| Tier | Component | Responsibility |
|---|---|---|
| **Ingest** | `ingest/live_ingest.py` | Decode each camera's RTSP to a periodic JPEG (no ML); write truthful health/status. Bounded, cap-safe concurrency. |
| **Core** | `api/` (FastAPI) | Registry, onboarding, unified-viewing endpoints, VMS federation + correlation engine, rule-based alerting, JWT auth / RBAC / audit. |
| **Bus / cache** | Redis | Live frame keys (short TTL) + metadata/event bus. |
| **Store** | PostgreSQL + PostGIS | System of record: cameras (geometry), health, gaps, watchlist, events, VMS, federated events, correlations, alerts, audit, security events. |
| **Presentation** | `web/` (React + Vite + Leaflet) | Command console — dashboard, GIS registry, viewing wall, federation, security, audit. |

## 4. Component design

### 4.1 Registry & GIS (Model 1)
- Onboarding by **bulk CSV / manual / API**, all through one validated, audited upsert.
- Cameras stored as **PostGIS points**; interactive Leaflet map with department/status layers.
- **Health monitoring** (`camera_health`) and **coverage-gap analysis** (`coverage_gaps`, geometric + department/district distribution).

### 4.2 Unified Viewing (Model 2)
- **Ingest** pulls live RTSP → JPEG into Redis; the console polls auth-gated snapshots.
- Viewing wall with **click-to-maximise** live view; **operator event tagging**; **searchable, camera-wise event index**; rule-based **alerts**.

### 4.3 VMS Federation (Model 3)
- **Adapter framework** (`api/app/adapters/`): one `@register("<type>")` class per vendor exposing `health / list_cameras / poll_events`.
- Adapters feed a **metadata bus** (`federated_events`); a **deterministic correlation engine** links the same entity reported by ≥2 sources within a time window (`event_correlations`), raising alerts on watchlist matches.

### 4.4 Cybersecurity (cross-cutting)
- Stateless **JWT (HS256)**; **bcrypt** passwords via `pgcrypto`; **department-scoped RBAC** enforced server-side.
- **Brute-force lockout**, per-IP **rate limiting**, **security headers** (CSP/HSTS/XFO), **immutable audit trail**, live **security posture** dashboard.

## 5. Data model (key entities)

```mermaid
erDiagram
  DEPARTMENTS ||--o{ STATIONS : has
  DEPARTMENTS ||--o{ CAMERAS : owns
  STATIONS ||--o{ CAMERAS : hosts
  CAMERAS ||--o{ CAMERA_HEALTH : reports
  CAMERAS ||--o{ CAMERA_EVENTS : tagged
  CAMERAS ||--o{ ALERTS : raises
  VMS_SYSTEMS ||--o{ FEDERATED_EVENTS : emits
  FEDERATED_EVENTS }o--|| EVENT_CORRELATIONS : linked
  WATCHLIST ||--o{ ALERTS : matches
  USERS ||--o{ AUDIT_LOG : acts
```

Supporting tables: `security_events`, `external_lookups` (mock VAHAN/Sarthi shells),
`coverage_gaps` (PostGIS regions).

## 6. Request & authentication flow

```mermaid
sequenceDiagram
  participant U as Operator (browser)
  participant W as React console
  participant A as FastAPI
  participant D as PostgreSQL
  U->>W: sign in (email, password)
  W->>A: POST /api/auth/login
  A->>D: verify bcrypt hash (pgcrypto)
  A-->>W: JWT (HS256, 8h)
  W->>A: GET /api/cameras  (Bearer JWT)
  A->>A: verify token · resolve role · RBAC scope
  A->>D: query (department/district-scoped)
  A-->>W: cameras (scoped) · audit logged
```

## 7. Federation & correlation flow

```mermaid
sequenceDiagram
  participant O as Officer
  participant A as FastAPI
  participant AD as Vendor adapter
  participant D as PostgreSQL
  O->>A: POST /api/vms/{id}/sync
  A->>AD: poll_events(watch_values)
  AD-->>A: events (native vocab + reported tags)
  A->>D: insert federated_events
  A->>A: correlation rule (same tag, ≥2 sources, 30 min)
  A->>D: upsert event_correlations + raise alert (if watchlisted)
  A-->>O: events ingested + correlations raised
```

## 8. Technology stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, react-leaflet, OpenStreetMap tiles (keyless) |
| Backend | Python 3.11, FastAPI, SQLAlchemy, GeoAlchemy2 |
| Ingest | OpenCV (FFmpeg backend) — decode only, **no ML** |
| Data | PostgreSQL 16 + PostGIS, Redis 7 |
| Auth | Stateless JWT (HS256), bcrypt via pgcrypto |
| Packaging | Docker, Docker Compose |

## 9. Deployment view

```mermaid
flowchart LR
  LB["Load balancer / TLS"] --> W1["web (static)"]
  LB --> A1["api replica"]
  LB --> A2["api replica"]
  A1 --> PG[("PostgreSQL + PostGIS<br/>PITR + replicas")]
  A2 --> PG
  A1 --> RK[("Redis Cluster")]
  ING["ingest nodes<br/>sharded by camera range"] --> RK
  ING -. reads registry .-> PG
```

- **Stateless API replicas** behind a load balancer (TLS termination).
- **Ingest nodes** are regional and horizontally sharded by camera-id range.
- **PostgreSQL** with streaming replication + PITR; **Redis Cluster** for the bus.
- Target deployment is **on-premise** (government data residency); no public cloud dependency.

## 10. Non-functional requirements

| Attribute | Design response |
|---|---|
| **Scalability** | Stateless tiers; snapshot-first bandwidth; GPU-free linear CPU scaling → ~80,000 cameras. See `SCALABILITY.md`. |
| **Availability** | Stateless API replicas; DB PITR + standby; ephemeral Redis frames self-heal. |
| **Security** | Zero-trust: JWT, dept RBAC, lockout, rate limiting, headers, immutable audit. |
| **Performance** | Ingest is I/O-bound at snapshot cadence; API is standard web-tier capacity. |
| **Interoperability** | Vendor-agnostic adapter framework; no rip-and-replace of existing VMS. |
| **Auditability / privacy** | Every mutation audited; no fabricated data; deterministic (explainable) logic. |

## 11. Scope & design decisions (honest)

- **Deterministic by design — no AI/ML.** Matching is operator/rule-based + cross-VMS
  correlation, not inference. This is a deliberate trade for a GPU-free, privacy-preserving,
  auditable foundation. **Model 4 (AI analytics)** attaches later as a *pluggable* worker
  consuming the same frame bus, writing into the same `alerts` / `event_correlations`
  tables — no UI or schema change needed.
- **Live feeds** are real (credential-authenticated RTSP), bounded by the grid's per-account
  concurrent-stream cap; the platform holds a stable set live and is architected to shard
  ingest for statewide scale.

---

<div align="center">
Prototype for the Gujarat Police Innovation Challenge 2026 · For evaluation use.
</div>
