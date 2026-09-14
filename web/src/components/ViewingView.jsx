import React, { useEffect, useMemo, useRef, useState } from "react";
import { getCameraEvents, tagEvent, fetchSnapshot, activateCamera, getAlerts, updateAlert } from "../api";
import { hasLevel } from "../auth";
import { DeptTag, SeverityBadge, Flash, timeAgo } from "../ui";

// One live tile: polls the auth-gated snapshot; shows a frame when ingest delivers one.
function LiveTile({ cam, canTag, onTag }) {
  const [live, setLive] = useState(false);
  const [src, setSrc] = useState(null);

  useEffect(() => {
    let active = true;
    let current = null;
    const tick = async () => {
      const url = await fetchSnapshot(cam.external_id);
      if (!active) { if (url) URL.revokeObjectURL(url); return; }
      if (url) {
        if (current) URL.revokeObjectURL(current);
        current = url;
        setSrc(url); setLive(true);
      } else { setLive(false); }
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => { active = false; clearInterval(id); if (current) URL.revokeObjectURL(current); };
  }, [cam.external_id]);

  return (
    <div className="cam-tile">
      <div className="cam-frame">
        {src && live ? <img src={src} alt={cam.location_name} /> : (
          <div className="noimg"><span>{cam.status === "live" ? "Awaiting frame" : "No signal"}</span></div>
        )}
        <div className="cam-scanline" />
        <div className={`cam-livechip ${live ? "" : "off"}`}><span className="rec" />{live ? "LIVE" : "OFFLINE"}</div>
      </div>
      <div className="cam-meta">
        <div className="nm">{cam.location_name}</div>
        <div className="sub">#{cam.external_id} · {cam.district || "—"} <DeptTag name={cam.department} /></div>
        {canTag && <button className="btn btn-sm" style={{ marginTop: 10, width: "100%" }} onClick={() => onTag(cam)}>Tag event</button>}
      </div>
    </div>
  );
}

export default function ViewingView({ cameras, user, onRefresh }) {
  const [events, setEvents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [q, setQ] = useState("");
  const [flash, setFlash] = useState(null);
  const [tagCam, setTagCam] = useState(null);
  const [limit, setLimit] = useState(12);

  async function load() {
    const [e, a] = await Promise.all([getCameraEvents({ limit: 100 }), getAlerts()]);
    setEvents(e); setAlerts(a);
  }
  useEffect(() => {
    load().catch((err) => setFlash({ kind: "err", msg: err.message }));
    // ask ingest to prioritise the visible cameras into its active pool
    cameras.slice(0, limit).forEach((c) => activateCamera(c.external_id));
  }, []); // eslint-disable-line

  const shownEvents = useMemo(
    () => events.filter((e) => !q || `${e.label} ${e.camera_external_id} ${e.location_name}`.toLowerCase().includes(q.toLowerCase())),
    [events, q]
  );

  const canTag = hasLevel(user, "station_officer");
  const gridCams = cameras.slice(0, limit);

  async function ack(id, status) {
    try { await updateAlert(id, status); await load(); onRefresh && onRefresh(); }
    catch (e) { setFlash({ kind: "err", msg: e.message }); }
  }

  return (
    <>
      {flash && <Flash kind={flash.kind} onClose={() => setFlash(null)}>{flash.msg}</Flash>}

      <div className="panel">
        <div className="panel-head">
          <h3>Unified Viewing Wall</h3>
          <span className="hint">Model 2 · live frames via CPU-light ingest (no ML) — offline tiles show honest status</span>
        </div>
        <div className="panel-body">
          <div className="cam-grid">
            {gridCams.map((c) => <LiveTile key={c.id} cam={c} canTag={canTag} onTag={setTagCam} />)}
          </div>
          {cameras.length > limit && (
            <div style={{ textAlign: "center", marginTop: 18 }}>
              <button className="btn" onClick={() => { const n = limit + 12; setLimit(n); cameras.slice(limit, n).forEach((c) => activateCamera(c.external_id)); }}>
                Show more feeds ({cameras.length - limit} remaining)
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <div className="panel-head"><h3>Event Index</h3><span className="hint">searchable · camera-wise</span></div>
          <div className="panel-body">
            <div className="search-box" style={{ marginBottom: 14 }}>
              <input className="input" placeholder="Search events (plate, description, camera)…" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: "100%" }} />
            </div>
            <div style={{ maxHeight: 360, overflowY: "auto" }}>
              {shownEvents.map((e) => (
                <div className="lrow" key={e.id}>
                  <div className="lr-main">
                    <div className="lr-t cell-strong">{e.label}</div>
                    <div className="lr-s">{e.location_name || `cam ${e.camera_external_id}`} · {e.tagged_by || "system"}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <span className={`badge ${e.event_type === "watchlist_hit" ? "critical" : "low"}`}>{e.event_type.replace(/_/g, " ")}</span>
                    <div className="lr-s" style={{ marginTop: 4 }}>{timeAgo(e.occurred_at)}</div>
                  </div>
                </div>
              ))}
              {shownEvents.length === 0 && <div className="empty">No events</div>}
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head"><h3>Active Alerts</h3><span className="hint">rule-based</span></div>
          <div className="panel-body" style={{ maxHeight: 420, overflowY: "auto" }}>
            {alerts.map((a) => (
              <div className="lrow" key={a.id}>
                <div className="lr-main">
                  <div className="lr-t">{a.message}</div>
                  <div className="lr-s">{a.source_system} · {timeAgo(a.ts)}</div>
                </div>
                <div className="row" style={{ gap: 8 }}>
                  <SeverityBadge severity={a.severity} />
                  {hasLevel(user, "station_officer") && a.status === "new" && (
                    <button className="btn btn-sm btn-ghost" onClick={() => ack(a.id, "acknowledged")}>Ack</button>
                  )}
                  {a.status !== "new" && <span className={`badge ${a.status}`}>{a.status}</span>}
                </div>
              </div>
            ))}
            {alerts.length === 0 && <div className="empty">No alerts</div>}
          </div>
        </div>
      </div>

      {tagCam && <TagModal camera={tagCam} onClose={() => setTagCam(null)} onDone={(msg) => { setTagCam(null); setFlash({ kind: "ok", msg }); load(); onRefresh && onRefresh(); }} />}
    </>
  );
}

function TagModal({ camera, onClose, onDone }) {
  const [label, setLabel] = useState("");
  const [type, setType] = useState("observation");
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setErr(""); setBusy(true);
    try {
      const res = await tagEvent({ camera_external_id: camera.external_id, event_type: type, label, note });
      onDone(`Event tagged on ${camera.location_name}${res.watchlist_hit ? " — WATCHLIST HIT" : ""}`);
    } catch (e) { setErr(typeof e.message === "string" ? e.message : "Tag failed"); }
    finally { setBusy(false); }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head"><h3>Tag event · {camera.location_name}</h3><button className="close-x" onClick={onClose}>×</button></div>
        <div className="modal-body">
          {err && <Flash kind="err">{err}</Flash>}
          <div className="form-group"><label>Event type</label>
            <select className="input" value={type} onChange={(e) => setType(e.target.value)}>
              {["observation", "vehicle_of_interest", "incident", "maintenance", "other"].map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div className="form-group"><label>Label (plate / description)</label>
            <input className="input" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. GJ01AB1234 or 'suspicious vehicle'" />
          </div>
          <div className="form-group"><label>Note</label><input className="input" value={note} onChange={(e) => setNote(e.target.value)} /></div>
          <div className="muted" style={{ fontSize: 12, marginBottom: 14 }}>A label matching a watchlist entry auto-raises a watchlist-hit alert.</div>
          <button className="btn btn-primary" onClick={submit} disabled={busy || !label} style={{ width: "100%" }}>{busy ? "Tagging…" : "Tag event"}</button>
        </div>
      </div>
    </div>
  );
}
