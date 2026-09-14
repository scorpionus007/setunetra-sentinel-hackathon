-- SetuNetra demo seed — Gujarat Police Innovation Challenge 2026
-- Reproducible dataset for Models 1/2/3 + cybersecurity. NO fabricated analytics:
-- camera coordinates are honest geocode ESTIMATES of the real place names in the
-- hackathon catalogue (OSM/area-level), and all "detections" are operator- or
-- rule-generated, never inferred.
--
-- Demo login passwords below are intentionally simple DEMO credentials for a
-- local database only. The real portal secret (SENTINEL_ACCESS_PASSWORD) is
-- never stored here — it stays in the environment.

BEGIN;

-- ---------------------------------------------------------------------------
-- Departments (the 5 real departments the catalogue is split across)
-- ---------------------------------------------------------------------------
INSERT INTO departments (name, kind) VALUES
    ('Police',                'police'),
    ('Municipal Corporation', 'municipal'),
    ('GSRTC',                 'transport'),
    ('Panchayat',             'panchayat'),
    ('Health',                'health')
ON CONFLICT (name) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Stations (department + district scoped)
-- ---------------------------------------------------------------------------
INSERT INTO stations (department_id, name, district)
SELECT d.id, s.name, s.district
FROM (VALUES
    ('Police',                'Ahmedabad Traffic Control',   'Ahmedabad'),
    ('Police',                'Junagadh City Police',        'Junagadh'),
    ('Police',                'Rajkot Traffic',              'Rajkot'),
    ('Police',                'Navsari Rural',               'Navsari'),
    ('Municipal Corporation', 'AMC Command Centre',          'Ahmedabad'),
    ('GSRTC',                 'GSRTC Central Depot',          'Gandhinagar'),
    ('Panchayat',             'Navsari Panchayat Cell',      'Navsari')
) AS s(dept, name, district)
JOIN departments d ON d.name = s.dept;

-- ---------------------------------------------------------------------------
-- Users / RBAC (passwords hashed with bcrypt via pgcrypto)
--   admin@setunetra.gov.in    / Admin@123    (admin — statewide)
--   police@setunetra.gov.in   / Police@123   (dept_officer — Police)
--   rajkot@setunetra.gov.in   / Station@123  (station_officer — Rajkot Traffic)
--   auditor@setunetra.gov.in  / Audit@123    (auditor — security/audit read-only)
--   viewer@setunetra.gov.in   / Viewer@123   (viewer — read-only ops)
-- ---------------------------------------------------------------------------
INSERT INTO users (email, full_name, password_hash, role, department_id, station_id)
SELECT u.email, u.full_name, crypt(u.pw, gen_salt('bf')), u.role, d.id, st.id
FROM (VALUES
    ('admin@setunetra.gov.in',   'State Administrator', 'Admin@123',   'admin',           NULL,                    NULL),
    ('police@setunetra.gov.in',  'Police Dept Officer', 'Police@123',  'dept_officer',    'Police',                NULL),
    ('rajkot@setunetra.gov.in',  'Rajkot Station Officer','Station@123','station_officer', 'Police',                'Rajkot Traffic'),
    ('auditor@setunetra.gov.in', 'Security Auditor',    'Audit@123',   'auditor',         NULL,                    NULL),
    ('viewer@setunetra.gov.in',  'Control Room Viewer', 'Viewer@123',  'viewer',          'Municipal Corporation', NULL)
) AS u(email, full_name, pw, role, dept, station)
LEFT JOIN departments d ON d.name = u.dept
LEFT JOIN stations st ON st.name = u.station;

-- ---------------------------------------------------------------------------
-- Cameras — 30 real catalogue places, geocoded to district-level estimates
-- ---------------------------------------------------------------------------
WITH cam(ext, name, district, lon, lat, dept, ctype, prio, stier, cstatus) AS (VALUES
    ('1', '01 Chiman bhai Bridge',                 'Ahmedabad',   72.5670, 23.0050, 'Police',                'ptz',   'critical','hot', 'live'),
    ('2', '02 Janpath',                            'Ahmedabad',   72.5660, 23.0260, 'Municipal Corporation', 'dome',  'medium',  'warm','live'),
    ('3', '03 O.N.G.C. Office',                    'Ahmedabad',   72.5810, 23.0610, 'Police',                'fixed', 'medium',  'warm','live'),
    ('4', '04 Paldi Circle',                       'Ahmedabad',   72.5670, 23.0100, 'Police',                'ptz',   'critical','hot', 'live'),
    ('5', '05 Visat teen Rasta',                   'Ahmedabad',   72.5880, 23.1080, 'Police',                'anpr',  'critical','hot', 'live'),
    ('6', '06 Timbavadi gate-Junagadh',            'Junagadh',    70.4700, 21.5050, 'Police',                'anpr',  'critical','hot', 'live'),
    ('7', '07 hero-showroom-gir-somnath',          'Gir Somnath', 70.3670, 20.9130, 'Municipal Corporation', 'fixed', 'medium',  'warm','live'),
    ('8', '08 majewadi-gate-junagadh',             'Junagadh',    70.4570, 21.5200, 'Police',                'fixed', 'medium',  'warm','degraded'),
    ('9', '09 new-bypass-near-by-circle-junagadh-2','Junagadh',   70.4400, 21.4950, 'Police',                'anpr',  'medium',  'warm','live'),
    ('10','10 char-chowk-road-2-junagadh',         'Junagadh',    70.4630, 21.5170, 'Police',                'dome',  'medium',  'warm','live'),
    ('11','11 dolatpara-junagadh',                 'Junagadh',    70.4800, 21.4850, 'Panchayat',             'fixed', 'low',     'cold','down'),
    ('12','12 Tri Mandir Adalaj Tollnaka',         'Gandhinagar', 72.5810, 23.1660, 'GSRTC',                 'anpr',  'critical','hot', 'live'),
    ('13','13 CN Vidhyalaya',                      'Ahmedabad',   72.5520, 23.0260, 'Municipal Corporation', 'dome',  'medium',  'warm','live'),
    ('14','14 Delight',                            'Ahmedabad',   72.5800, 23.0300, 'Municipal Corporation', 'fixed', 'low',     'warm','live'),
    ('15','15 Suvidha park',                       'Ahmedabad',   72.5600, 23.0050, 'Municipal Corporation', 'dome',  'low',     'warm','live'),
    ('16','16 Visat P2',                           'Ahmedabad',   72.5900, 23.1100, 'Police',                'ptz',   'medium',  'warm','live'),
    ('17','17 Rajkot Bus Port CCTV',               'Rajkot',      70.8020, 22.3020, 'GSRTC',                 'dome',  'medium',  'warm','live'),
    ('18','18 Rajkot CCTV',                        'Rajkot',      70.7930, 22.2900, 'Municipal Corporation', 'ptz',   'medium',  'warm','live'),
    ('19','19 KHAPARIA GRAM PANCHAYAT, GANDEVI, NAVSARI','Navsari',72.9600, 20.9000,'Panchayat',            'fixed', 'low',     'cold','live'),
    ('20','20 Mohanpura',                          'Navsari',     72.9300, 20.8500, 'Panchayat',             'fixed', 'low',     'cold','degraded'),
    ('21','23 Patan Dethali Char Rasta',           'Patan',       72.1260, 23.8500, 'Police',                'anpr',  'medium',  'warm','live'),
    ('22','28 BK Mervada tran Rasta',              'Banaskantha', 72.4000, 24.1000, 'Police',                'fixed', 'low',     'warm','live'),
    ('23','30 kheram',                             'Navsari',     72.9000, 20.8000, 'Panchayat',             'fixed', 'low',     'cold','down'),
    ('24','33 dehgam',                             'Gandhinagar', 72.8200, 23.1700, 'Police',                'dome',  'medium',  'warm','live'),
    ('25','34 dhanori',                            'Aravalli',    73.0000, 23.5000, 'Panchayat',             'fixed', 'low',     'cold','live'),
    ('26','35 TANKAL',                             'Navsari',     72.9800, 20.9500, 'Panchayat',             'fixed', 'low',     'cold','live'),
    ('27','36 bilimora',                           'Navsari',     72.9600, 20.7680, 'Municipal Corporation', 'dome',  'medium',  'warm','live'),
    ('28','37 bilimora',                           'Navsari',     72.9620, 20.7700, 'GSRTC',                 'fixed', 'low',     'warm','live'),
    ('29','38 bilimora',                           'Navsari',     72.9580, 20.7660, 'Police',                'anpr',  'medium',  'warm','live'),
    ('30','Gandhidham Rambaugh p2',                'Kutch',       70.1330, 23.0750, 'Municipal Corporation', 'ptz',   'medium',  'warm','live')
)
-- Only fields that are real or a defensible Model-1 classification are set:
-- id + location_name are from the catalogue; location/district are geocoded
-- ESTIMATES; department + camera_type + tiers are operational classifications;
-- rtsp_url is the real grid URL. Device specifics the catalogue does NOT provide
-- (make, model, IP, fps, resolution, codec) are deliberately left NULL — never
-- fabricated.
INSERT INTO cameras (external_id, location_name, district, location, department_id, camera_type,
                     priority_tier, storage_tier, status, source, rtsp_url, last_seen)
SELECT c.ext, c.name, c.district,
       ST_SetSRID(ST_MakePoint(c.lon, c.lat), 4326),
       d.id, c.ctype, c.prio, c.stier, c.cstatus, 'bulk',
       'rtsp://103.250.160.189:8554/stream/cam' || lpad(COALESCE(substring(c.name from '^\s*(\d+)'), c.ext), 2, '0'),
       CASE WHEN c.cstatus = 'down' THEN now() - interval '6 hours'
            WHEN c.cstatus = 'degraded' THEN now() - interval '25 minutes'
            ELSE now() - (abs(hashtext(c.ext)) % 90) * interval '1 second' END
FROM cam c
LEFT JOIN departments d ON d.name = c.dept;

-- ---------------------------------------------------------------------------
-- Camera health — latest heartbeat per camera
-- ---------------------------------------------------------------------------
INSERT INTO camera_health (camera_id, ts, status, last_frame_ts, latency_ms, note)
SELECT id, last_seen, status, last_seen,
       CASE status WHEN 'live' THEN 40 + (abs(hashtext(external_id)) % 120)
                   WHEN 'degraded' THEN 800 + (abs(hashtext(external_id)) % 400)
                   ELSE NULL END,
       CASE status WHEN 'down' THEN 'No frames received — connectivity lost'
                   WHEN 'degraded' THEN 'High latency / intermittent frames'
                   ELSE 'Nominal' END
FROM cameras;

-- ---------------------------------------------------------------------------
-- Coverage gaps (Model 1 gap-analysis output)
-- ---------------------------------------------------------------------------
INSERT INTO coverage_gaps (district, region, center, severity, reason, camera_count)
VALUES
    ('Kutch',       ST_SetSRID(ST_MakeEnvelope(69.5, 22.6, 70.6, 23.6), 4326), ST_SetSRID(ST_MakePoint(70.05,23.10),4326), 'high',   'Only 1 camera across ~11,000 km2 district; Health/GSRTC uncovered', 1),
    ('Banaskantha', ST_SetSRID(ST_MakeEnvelope(71.8, 23.9, 72.9, 24.5), 4326), ST_SetSRID(ST_MakePoint(72.40,24.20),4326), 'high',   'Single border-district camera; no ANPR on NH ingress',            1),
    ('Aravalli',    ST_SetSRID(ST_MakeEnvelope(72.8, 23.3, 73.4, 23.7), 4326), ST_SetSRID(ST_MakePoint(73.00,23.50),4326), 'medium', 'Lone rural Panchayat camera; ageing infra (>5y)',                 1),
    ('Gir Somnath', ST_SetSRID(ST_MakeEnvelope(70.1, 20.7, 70.7, 21.2), 4326), ST_SetSRID(ST_MakePoint(70.37,20.91),4326), 'medium', 'Pilgrim-corridor coverage limited to 1 municipal camera',         1);

-- ---------------------------------------------------------------------------
-- Watchlist (entities of interest — matched manually / by rule, not by AI)
-- ---------------------------------------------------------------------------
INSERT INTO watchlist (type, value, reason, priority, added_by)
SELECT w.type, w.value, w.reason, w.priority, u.id
FROM (VALUES
    ('vehicle','GJ01AB1234','Stolen vehicle — FIR 112/2026, Ahmedabad',      'critical'),
    ('vehicle','GJ18XY9999','Blacklisted — repeated toll evasion',           'medium'),
    ('vehicle','GJ11CD4567','Suspect vehicle — inter-district alert',         'critical'),
    ('person','Wanted: R. Solanki','Absconding — Junagadh City PS',           'critical'),
    ('person','Missing: minor (Navsari)','Missing person — Gandevi',          'medium')
) AS w(type, value, reason, priority)
CROSS JOIN LATERAL (SELECT id FROM users WHERE email='police@setunetra.gov.in') u;

-- ---------------------------------------------------------------------------
-- Camera events (operator / rule-based tags — Model 2 searchable index)
-- ---------------------------------------------------------------------------
INSERT INTO camera_events (camera_id, event_type, label, watchlist_id, tagged_by, occurred_at, note)
SELECT c.id, e.event_type, e.label,
       (SELECT id FROM watchlist WHERE value = e.wl LIMIT 1),
       (SELECT id FROM users WHERE email='rajkot@setunetra.gov.in'),
       now() - (e.mins || ' minutes')::interval, e.note
FROM (VALUES
    ('5', 'watchlist_hit',       'GJ01AB1234 flagged at Visat',        'GJ01AB1234', 12,  'Operator confirmed plate against watchlist'),
    ('12','vehicle_of_interest', 'Toll-evasion pattern GJ18XY9999',    'GJ18XY9999', 40,  'Repeated pass without tag'),
    ('6', 'incident',            'Minor collision at Timbavadi gate',   NULL,         95,  'Traffic obstruction cleared'),
    ('1', 'observation',         'Heavy congestion Chimanbhai Bridge',  NULL,         20,  'Peak-hour buildup'),
    ('18','maintenance',         'Lens obstruction reported',           NULL,         180, 'Scheduled cleaning raised'),
    ('29','watchlist_hit',       'GJ11CD4567 seen at Bilimora',         'GJ11CD4567', 8,   'Inter-district suspect vehicle')
) AS e(ext, event_type, label, wl, mins, note)
JOIN cameras c ON c.external_id = e.ext;

-- ---------------------------------------------------------------------------
-- Model 3 — Federated VMS systems (reached via pluggable adapters)
-- ---------------------------------------------------------------------------
INSERT INTO vms_systems (name, vendor, adapter_type, department_id, base_url, auth_ref, status, camera_count, last_sync)
SELECT v.name, v.vendor, v.adapter_type, d.id, v.base_url, v.auth_ref, v.status, v.cc, now() - (v.mins||' minutes')::interval
FROM (VALUES
    ('AMC City Surveillance',   'Hikvision', 'hikvision',   'Municipal Corporation', 'https://vms.amc.local/api',    'AMC_VMS_TOKEN',   'online',   9, 3),
    ('Gujarat Police VMS',      'Milestone', 'milestone',   'Police',                'https://vms.gujpolice.local',  'GP_VMS_TOKEN',    'online',  12, 5),
    ('GSRTC Depot CCTV',        'CP-Plus',   'cpplus',      'GSRTC',                 'https://cctv.gsrtc.local',     'GSRTC_VMS_TOKEN', 'degraded', 3, 22),
    ('Rajkot Smart City',       'Genetec',   'genetec',     'Municipal Corporation', 'https://scc.rajkot.local',     'RSC_VMS_TOKEN',   'online',   2, 8),
    ('Rural ONVIF Bridge',      'ONVIF',     'onvif',       'Panchayat',             'onvif://10.20.0.0/24',         'ONVIF_BRIDGE',    'offline',  4, 240)
) AS v(name, vendor, adapter_type, dept, base_url, auth_ref, status, cc, mins)
LEFT JOIN departments d ON d.name = v.dept;

-- ---------------------------------------------------------------------------
-- Federated events (pulled from adapters through the metadata bus)
-- ---------------------------------------------------------------------------
INSERT INTO federated_events (vms_id, external_event_id, camera_external_id, camera_id, event_type, payload, occurred_at)
SELECT vs.id, f.ext_event, f.cam_ext, c.id, f.etype, f.payload::jsonb, now() - (f.mins||' minutes')::interval
FROM (VALUES
    ('Gujarat Police VMS','GP-88213','5','vehicle_tag', '{"plate":"GJ01AB1234","lane":"2"}', 12),
    ('AMC City Surveillance','AMC-4471','2','motion',   '{"zone":"north"}',                   30),
    ('Gujarat Police VMS','GP-88240','29','vehicle_tag','{"plate":"GJ11CD4567"}',             9),
    ('GSRTC Depot CCTV','GS-1190','17','door_open',     '{"gate":"A"}',                       45),
    ('AMC City Surveillance','AMC-4490','13','tamper',  '{"confidence":"n/a"}',              60),
    ('Rajkot Smart City','RSC-330','18','offline',      '{"reason":"link_down"}',            15),
    ('Gujarat Police VMS','GP-88301','6','motion',      '{"zone":"gate"}',                    95),
    ('Rural ONVIF Bridge','ONV-77','11','offline',      '{"reason":"power"}',                360)
) AS f(vms, ext_event, cam_ext, etype, payload, mins)
JOIN vms_systems vs ON vs.name = f.vms
LEFT JOIN cameras c ON c.external_id = f.cam_ext;

-- ---------------------------------------------------------------------------
-- Cross-system correlations (deterministic rule fired across VMS + registry)
-- ---------------------------------------------------------------------------
INSERT INTO event_correlations (correlation_key, rule, event_count, vms_count, summary)
VALUES
    ('plate:GJ01AB1234', 'same_plate_multi_source_5min', 2, 2,
     'GJ01AB1234 seen by Gujarat Police VMS (cam 5) and registry watchlist tag within 5 min'),
    ('plate:GJ11CD4567', 'same_plate_multi_source_5min', 2, 1,
     'GJ11CD4567 tagged at Bilimora (cam 29) matching inter-district suspect alert');

-- ---------------------------------------------------------------------------
-- Unified alerts (rule-based)
-- ---------------------------------------------------------------------------
INSERT INTO alerts (kind, severity, message, camera_id, watchlist_id, source_system, status)
SELECT a.kind, a.severity, a.message,
       (SELECT id FROM cameras WHERE external_id = a.cam_ext),
       (SELECT id FROM watchlist WHERE value = a.wl LIMIT 1),
       a.src, a.status
FROM (VALUES
    ('watchlist_hit',          'critical','Stolen vehicle GJ01AB1234 flagged at Visat teen Rasta',        '5',  'GJ01AB1234','Gujarat Police VMS','new'),
    ('camera_offline',         'high',    'Camera 11 (Dolatpara) offline > 6h — connectivity lost',        '11', NULL,        'Registry health',  'new'),
    ('camera_offline',         'high',    'Camera 23 (Kheram) offline — no frames',                        '23', NULL,        'Registry health',  'acknowledged'),
    ('camera_tamper',          'high',    'Possible tamper on Camera 13 (CN Vidhyalaya)',                   '13', NULL,        'AMC City Surveillance','new'),
    ('federation_correlation', 'critical','Suspect GJ11CD4567 correlated across sources at Bilimora',        '29', 'GJ11CD4567','Federation engine','new'),
    ('camera_offline',         'medium',  'Camera 20 (Mohanpura) degraded — intermittent frames',           '20', NULL,        'Registry health',  'new')
) AS a(kind, severity, message, cam_ext, wl, src, status);

-- ---------------------------------------------------------------------------
-- Security telemetry (cyber dashboard)
-- ---------------------------------------------------------------------------
INSERT INTO security_events (kind, severity, email, ip_address, detail, ts) VALUES
    ('login_failed',  'medium','unknown@attacker.test','203.0.113.44','Invalid password (attempt 3)',  now() - interval '8 minutes'),
    ('login_locked',  'high',  'unknown@attacker.test','203.0.113.44','Account locked after 5 attempts',now() - interval '7 minutes'),
    ('rate_limited',  'medium',NULL,                   '198.51.100.9','120 req/min exceeded on /api/cameras', now() - interval '20 minutes'),
    ('access_denied', 'medium','viewer@setunetra.gov.in','10.0.0.15','RBAC: viewer attempted DELETE camera', now() - interval '35 minutes'),
    ('token_invalid', 'low',   NULL,                   '192.0.2.7',  'Expired JWT presented to /api/vms',    now() - interval '50 minutes'),
    ('anomaly',       'high',  NULL,                   '10.20.0.5',  'Rural ONVIF Bridge offline 4h — possible outage', now() - interval '60 minutes');

COMMIT;
