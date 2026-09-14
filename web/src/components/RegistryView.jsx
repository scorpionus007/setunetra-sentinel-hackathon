import React, { useMemo, useState } from "react";
import { onboardManual, onboardBulk, deleteCamera } from "../api";
import { hasLevel } from "../auth";
import { StatusBadge, DeptTag, Flash } from "../ui";

const DEPARTMENTS = ["Police", "Municipal Corporation", "GSRTC", "Panchayat", "Health"];
const TYPES = ["fixed", "ptz", "dome", "bullet", "anpr", "thermal", "other"];

export default function RegistryView({ cameras, user, onRefresh, onSelectCamera }) {
  const [q, setQ] = useState("");
  const [dept, setDept] = useState("");
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [showOnboard, setShowOnboard] = useState(false);
  const [flash, setFlash] = useState(null);

  const filtered = useMemo(() => cameras.filter((c) => {
    if (q && !(`${c.location_name} ${c.external_id} ${c.district}`.toLowerCase().includes(q.toLowerCase()))) return false;
    if (dept && c.department !== dept) return false;
    if (status && c.status !== status) return false;
    if (type && c.camera_type !== type) return false;
    return true;
  }), [cameras, q, dept, status, type]);

  const canManage = hasLevel(user, "dept_officer");
  const canDelete = hasLevel(user, "admin");

  async function onDelete(e, extId) {
    e.stopPropagation();
    if (!window.confirm(`Delete camera ${extId} from the registry?`)) return;
    try { await deleteCamera(extId); setFlash({ kind: "ok", msg: `Camera ${extId} deleted` }); onRefresh(); }
    catch (err) { setFlash({ kind: "err", msg: err.message }); }
  }

  function exportCsv() {
    const cols = ["external_id", "location_name", "district", "department", "camera_type", "status", "lat", "lon", "manufacturer", "resolution"];
    const rows = filtered.map((c) => cols.map((k) => `"${c[k] ?? ""}"`).join(","));
    const blob = new Blob([cols.join(",") + "\n" + rows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "setunetra_cameras.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  const scopeNote = user.role === "dept_officer" ? " · your department" : user.role === "station_officer" ? " · your district" : "";

  return (
    <>
      {flash && <Flash kind={flash.kind} onClose={() => setFlash(null)}>{flash.msg}</Flash>}
      <div className="toolbar">
        <input className="input" placeholder="Search name, ID or district…" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 250 }} />
        <select className="input" value={dept} onChange={(e) => setDept(e.target.value)}><option value="">All departments</option>{DEPARTMENTS.map((d) => <option key={d}>{d}</option>)}</select>
        <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">Any status</option>{["live", "down", "degraded", "unknown"].map((s) => <option key={s}>{s}</option>)}</select>
        <select className="input" value={type} onChange={(e) => setType(e.target.value)}><option value="">Any type</option>{TYPES.map((s) => <option key={s}>{s}</option>)}</select>
        <div className="spacer" />
        <button className="btn btn-sm" onClick={exportCsv}>Export CSV</button>
        {canManage && <button className="btn btn-sm btn-primary" onClick={() => setShowOnboard(true)}>Onboard camera</button>}
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>Camera Registry</h3>
          <span className="hint">{filtered.length} of {cameras.length} cameras{scopeNote}</span>
        </div>
        <div className="table-wrap">
          <table className="tbl">
            <thead><tr><th>ID</th><th>Location</th><th>District</th><th>Department</th><th>Type</th><th>Status</th><th>Priority</th><th>Coordinates</th>{canDelete && <th></th>}</tr></thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.id} onClick={() => onSelectCamera && onSelectCamera(c)} style={{ cursor: "pointer" }}>
                  <td className="mono cell-strong">{c.external_id}</td>
                  <td className="cell-strong">{c.location_name}</td>
                  <td>{c.district || "—"}</td>
                  <td><DeptTag name={c.department} /></td>
                  <td><span className="chip" style={{ textTransform: "uppercase" }}>{c.camera_type}</span></td>
                  <td><StatusBadge status={c.status} /></td>
                  <td className="muted" style={{ textTransform: "capitalize" }}>{c.priority_tier || "—"}</td>
                  <td className="mono muted" style={{ fontSize: 11.5 }}>{c.lat ? `${c.lat.toFixed(3)}, ${c.lon.toFixed(3)}` : "—"}</td>
                  {canDelete && <td><button className="btn btn-sm btn-ghost btn-danger" onClick={(e) => onDelete(e, c.external_id)}>Delete</button></td>}
                </tr>
              ))}
              {filtered.length === 0 && <tr><td colSpan={canDelete ? 9 : 8}><div className="empty">No cameras match the filters</div></td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {showOnboard && <OnboardModal onClose={() => setShowOnboard(false)} onDone={(msg) => { setShowOnboard(false); setFlash({ kind: "ok", msg }); onRefresh(); }} />}
    </>
  );
}

function OnboardModal({ onClose, onDone }) {
  const [tab, setTab] = useState("manual");
  const [form, setForm] = useState({ external_id: "", location_name: "", district: "", department: "Police", camera_type: "fixed", lat: "", lon: "", manufacturer: "", resolution: "1080p" });
  const [csv, setCsv] = useState("external_id,location_name,district,lat,lon,department,camera_type,manufacturer,model_name,ip_address,resolution,fps,rtsp_url\n101,Test Gate Camera,Ahmedabad,23.03,72.58,Police,ptz,Hikvision,DS-2CD,10.0.0.101,1080p,25,rtsp://10.0.0.101/stream");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submitManual() {
    setErr(""); setBusy(true);
    try {
      await onboardManual({ ...form, lat: form.lat ? parseFloat(form.lat) : null, lon: form.lon ? parseFloat(form.lon) : null });
      onDone(`Camera ${form.external_id} onboarded`);
    } catch (e) { setErr(typeof e.message === "string" ? e.message : "Onboarding failed"); }
    finally { setBusy(false); }
  }
  async function submitBulk() {
    setErr(""); setBusy(true);
    try { const res = await onboardBulk({ csv }); onDone(`Bulk import: ${res.inserted_count} added, ${res.failed.length} failed`); }
    catch (e) { setErr(typeof e.message === "string" ? e.message : "Bulk import failed"); }
    finally { setBusy(false); }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head"><h3>Onboard camera</h3><button className="close-x" onClick={onClose}>×</button></div>
        <div className="modal-body">
          <div className="pilltabs" style={{ marginBottom: 20 }}>
            <button className={`pilltab ${tab === "manual" ? "active" : ""}`} onClick={() => setTab("manual")}>Manual entry</button>
            <button className={`pilltab ${tab === "bulk" ? "active" : ""}`} onClick={() => setTab("bulk")}>Bulk CSV import</button>
          </div>
          {err && <Flash kind="err">{err}</Flash>}
          {tab === "manual" ? (
            <>
              <div className="form-grid">
                <div className="form-group"><label>External ID *</label><input className="input" value={form.external_id} onChange={set("external_id")} /></div>
                <div className="form-group"><label>Location name *</label><input className="input" value={form.location_name} onChange={set("location_name")} /></div>
                <div className="form-group"><label>District</label><input className="input" value={form.district} onChange={set("district")} /></div>
                <div className="form-group"><label>Department</label><select className="input" value={form.department} onChange={set("department")}>{DEPARTMENTS.map((d) => <option key={d}>{d}</option>)}</select></div>
                <div className="form-group"><label>Camera type</label><select className="input" value={form.camera_type} onChange={set("camera_type")}>{TYPES.map((t) => <option key={t}>{t}</option>)}</select></div>
                <div className="form-group"><label>Manufacturer</label><input className="input" value={form.manufacturer} onChange={set("manufacturer")} /></div>
                <div className="form-group"><label>Latitude</label><input className="input" value={form.lat} onChange={set("lat")} placeholder="23.03" /></div>
                <div className="form-group"><label>Longitude</label><input className="input" value={form.lon} onChange={set("lon")} placeholder="72.58" /></div>
              </div>
              <button className="btn btn-primary" onClick={submitManual} disabled={busy || !form.external_id || !form.location_name} style={{ width: "100%", marginTop: 6 }}>{busy ? "Onboarding…" : "Onboard camera"}</button>
            </>
          ) : (
            <>
              <div className="form-group"><label>CSV data (first row = header)</label><textarea className="input" value={csv} onChange={(e) => setCsv(e.target.value)} /></div>
              <button className="btn btn-primary" onClick={submitBulk} disabled={busy} style={{ width: "100%" }}>{busy ? "Importing…" : "Import cameras"}</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
