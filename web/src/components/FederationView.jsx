import React, { useEffect, useState } from "react";
import { getVmsSystems, getFederatedEvents, getCorrelations, getFederationAnalytics, syncVms } from "../api";
import { hasLevel } from "../auth";
import { StatusBadge, Flash, timeAgo, Stat } from "../ui";

export default function FederationView({ user, onRefresh }) {
  const [systems, setSystems] = useState([]);
  const [events, setEvents] = useState([]);
  const [correlations, setCorrelations] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [flash, setFlash] = useState(null);
  const [syncing, setSyncing] = useState(null);

  async function load() {
    const [s, e, c, a] = await Promise.all([getVmsSystems(), getFederatedEvents(40), getCorrelations(), getFederationAnalytics()]);
    setSystems(s); setEvents(e); setCorrelations(c); setAnalytics(a);
  }
  useEffect(() => { load().catch((err) => setFlash({ kind: "err", msg: err.message })); }, []);

  async function doSync(sys) {
    setSyncing(sys.id); setFlash(null);
    try {
      const res = await syncVms(sys.id);
      const corr = res.correlations.length ? ` · ${res.correlations.length} correlation(s) raised` : "";
      setFlash({ kind: "ok", msg: `${sys.name}: pulled ${res.events_ingested} events${corr}` });
      await load(); onRefresh && onRefresh();
    } catch (e) { setFlash({ kind: "err", msg: e.message }); }
    finally { setSyncing(null); }
  }

  const canSync = hasLevel(user, "dept_officer");

  return (
    <>
      {flash && <Flash kind={flash.kind} onClose={() => setFlash(null)}>{flash.msg}</Flash>}

      {analytics && (
        <div className="kpi-grid">
          <Stat label="Integrated VMS" value={analytics.totals.systems} sub={`${analytics.totals.online} online`} tone="navy" />
          <Stat label="Federated Events" value={analytics.totals.events} sub="via metadata bus" tone="saffron" />
          <Stat label="Correlations" value={analytics.totals.correlations} sub="cross-system links" tone="red" />
          <Stat label="Vendor Adapters" value={systems.length} sub="pluggable" tone="green" />
        </div>
      )}

      <div className="panel">
        <div className="panel-head">
          <h3>Departmental VMS Systems</h3>
          <span className="hint">Model 3 · adapter-based federation — no VMS is replaced</span>
        </div>
        <div className="table-wrap">
          <table className="tbl">
            <thead><tr><th>System</th><th>Vendor</th><th>Adapter</th><th>Department</th><th>Status</th><th>Cameras</th><th>Last Sync</th><th></th></tr></thead>
            <tbody>
              {systems.map((s) => (
                <tr key={s.id}>
                  <td className="cell-strong">{s.name}</td>
                  <td>{s.vendor}</td>
                  <td><span className="chip">{s.adapter_type}</span></td>
                  <td className="muted">{s.department || "—"}</td>
                  <td><StatusBadge status={s.status} /></td>
                  <td>{s.camera_count}</td>
                  <td className="muted">{timeAgo(s.last_sync)}</td>
                  <td>{canSync && <button className="btn btn-sm" onClick={() => doSync(s)} disabled={syncing === s.id}>{syncing === s.id ? "Syncing…" : "Sync"}</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <div className="panel-head"><h3>Cross-System Correlations</h3><span className="hint">deterministic engine</span></div>
          <div className="panel-body">
            {correlations.length === 0 && <div className="empty">No correlations yet — run a VMS sync</div>}
            {correlations.map((c, i) => (
              <div key={i} style={{ padding: "12px 0", borderBottom: "1px solid var(--border)" }}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <span className="mono" style={{ color: "var(--saffron-deep)", fontWeight: 700 }}>{c.correlation_key}</span>
                  <span className="chip">{c.vms_count} systems · {c.event_count} events</span>
                </div>
                <div className="muted" style={{ fontSize: 12.5, marginTop: 5 }}>{c.summary}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-head"><h3>Federated Event Bus</h3><span className="hint">latest {events.length}</span></div>
          <div className="panel-body" style={{ maxHeight: 380, overflowY: "auto" }}>
            {events.map((e) => (
              <div className="lrow" key={e.id}>
                <div className="lr-main">
                  <div className="lr-t"><span className="chip" style={{ marginRight: 7 }}>{e.event_type}</span>{e.vms_name}{e.correlation_id && <span className="badge critical" style={{ marginLeft: 7 }}>correlated</span>}</div>
                  <div className="lr-s">{e.location_name || `cam ${e.camera_external_id}`}</div>
                </div>
                <span className="muted" style={{ fontSize: 11.5 }}>{timeAgo(e.occurred_at)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
