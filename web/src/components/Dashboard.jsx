import React from "react";
import MapView from "./MapView";
import { Stat, BarChart, Donut, DeptTag, SeverityBadge, DEPT_COLORS, timeAgo } from "../ui";

export default function Dashboard({ stats, cameras, alerts, gaps, onSelectCamera, onGoto }) {
  if (!stats) return <div className="loading">Loading command overview…</div>;
  const t = stats.totals;
  const uptime = t.cameras ? Math.round((t.live / t.cameras) * 100) : 0;

  const deptData = stats.by_department.map((d) => ({ label: d.department, value: d.cameras, kind: d.department }));
  const typeData = stats.by_type.map((d) => ({ label: d.camera_type, value: d.n }));
  const donutSegs = [
    { label: "Online", value: t.live, color: "#138808" },
    { label: "Degraded", value: t.degraded, color: "#c77700" },
    { label: "Offline", value: t.down, color: "#c62828" },
  ];

  return (
    <>
      <div className="kpi-grid">
        <Stat label="Registered Cameras" value={t.cameras} sub={`${t.geocoded} geocoded · ${t.districts} districts`} tone="navy" />
        <Stat label="Online Now" value={t.live} sub={<><span className="trend-up">{uptime}% uptime</span> · {t.down} offline</>} tone="green" />
        <Stat label="Departments" value={t.departments} sub="onboarded to grid" tone="saffron" />
        <Stat label="Federated VMS" value={`${t.vms_online}/${t.vms_total}`} sub="systems online" tone="navy" />
        <Stat label="Open Alerts" value={t.open_alerts} sub="need attention" tone={t.open_alerts ? "red" : "green"} />
        <Stat label="Coverage Gaps" value={t.coverage_gaps} sub="uncovered zones" tone="saffron" />
      </div>

      <div className="grid-wide">
        <div className="panel" style={{ marginBottom: 0 }}>
          <div className="panel-head">
            <h3>Statewide Surveillance Grid</h3>
            <span className="hint">Model 1 · {cameras.length} cameras across Gujarat</span>
          </div>
          <div style={{ padding: 14 }}><MapView cameras={cameras} onSelectCamera={onSelectCamera} /></div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div className="panel" style={{ marginBottom: 0 }}>
            <div className="panel-head"><h3>Network Health</h3></div>
            <div className="panel-body"><Donut segments={donutSegs} centerValue={`${uptime}%`} centerLabel="uptime" /></div>
          </div>
          <div className="panel" style={{ marginBottom: 0 }}>
            <div className="panel-head"><h3>Camera Types</h3></div>
            <div className="panel-body"><BarChart data={typeData} colorFor={() => "#0a1f4d"} /></div>
          </div>
        </div>
      </div>

      <div style={{ height: 20 }} />

      <div className="grid-2">
        <div className="panel">
          <div className="panel-head"><h3>Cameras by Department</h3></div>
          <div className="panel-body"><BarChart data={deptData} colorFor={(d) => DEPT_COLORS[d.kind] || "#6b7280"} /></div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h3>Coverage Gaps</h3>
            <button className="btn btn-sm btn-ghost" onClick={() => onGoto && onGoto("registry")}>View registry</button>
          </div>
          <div className="panel-body">
            {(!gaps || gaps.gaps.length === 0) && <div className="empty">No gaps computed</div>}
            {gaps && gaps.gaps.map((g, i) => (
              <div className="lrow" key={i}>
                <div className="lr-main">
                  <div className="lr-t cell-strong">{g.district}</div>
                  <div className="lr-s">{g.reason}</div>
                </div>
                <SeverityBadge severity={g.severity} />
              </div>
            ))}
            {gaps && gaps.uncovered_departments.length > 0 && (
              <div style={{ marginTop: 14, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span className="muted" style={{ fontSize: 12.5 }}>Zero coverage:</span>
                {gaps.uncovered_departments.map((d) => <DeptTag key={d} name={d} />)}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head"><h3>Recent Alerts</h3><span className="hint">rule-based · newest first</span></div>
        <div className="panel-body">
          {(!alerts || alerts.length === 0) && <div className="empty">No alerts</div>}
          {(alerts || []).slice(0, 6).map((a) => (
            <div className="lrow" key={a.id}>
              <div className="lr-main">
                <div className="lr-t">{a.message}</div>
                <div className="lr-s">{a.source_system} · {timeAgo(a.ts)}</div>
              </div>
              <SeverityBadge severity={a.severity} />
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
