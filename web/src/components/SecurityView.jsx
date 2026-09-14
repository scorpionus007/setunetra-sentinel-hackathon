import React, { useEffect, useState } from "react";
import { getSecurityPosture, getSecurityEvents } from "../api";
import { Flash, timeAgo, SeverityBadge } from "../ui";

function gaugeColor(score) {
  if (score >= 90) return "#138808";
  if (score >= 75) return "#b78103";
  if (score >= 60) return "#d9741a";
  return "#c62828";
}

export default function SecurityView() {
  const [posture, setPosture] = useState(null);
  const [events, setEvents] = useState([]);
  const [err, setErr] = useState(null);

  useEffect(() => {
    Promise.all([getSecurityPosture(), getSecurityEvents(60)])
      .then(([p, e]) => { setPosture(p); setEvents(e); })
      .catch((e) => setErr(e.message));
  }, []);

  if (err) return <Flash kind="err">{err}</Flash>;
  if (!posture) return <div className="loading">Loading security posture…</div>;

  const color = gaugeColor(posture.score);
  const m = posture.metrics;
  const metricRows = [
    ["Failed logins (24h)", m.failed_logins], ["Rate-limit trips", m.rate_limited],
    ["Locked accounts", m.locked_accounts], ["VMS offline", m.vms_offline],
    ["Unhealthy cameras", m.cameras_unhealthy], ["Active users", m.active_users],
  ];

  return (
    <>
      <div className="grid-2">
        <div className="panel">
          <div className="panel-head"><h3>Security Posture</h3><span className="hint">rule-based scoring</span></div>
          <div className="panel-body">
            <div className="posture">
              <div className="gauge" style={{ background: `conic-gradient(${color} ${posture.score * 3.6}deg, #efece3 0)` }}>
                <div className="gauge-inner">
                  <div className="gauge-score" style={{ color }}>{posture.score}</div>
                  <div className="gauge-grade">Grade {posture.grade}</div>
                </div>
              </div>
              <div style={{ flex: 1 }}>
                {metricRows.map(([l, v]) => (
                  <div className="bar-row" key={l} style={{ marginBottom: 9 }}>
                    <div className="bar-label" style={{ width: "auto", flex: 1 }}>{l}</div>
                    <div className="bar-val">{v}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head"><h3>Security Controls</h3><span className="hint">enforced</span></div>
          <div className="panel-body">
            <div className="controls-list">
              {posture.controls.map((c) => (
                <div className="control-item" key={c.control}><span className="ck">✓</span>{c.control}</div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head"><h3>Security Event Log</h3><span className="hint">auth failures · rate limits · access denials · anomalies</span></div>
        <div className="table-wrap">
          <table className="tbl">
            <thead><tr><th>Time</th><th>Kind</th><th>Severity</th><th>Account</th><th>Source IP</th><th>Detail</th></tr></thead>
            <tbody>
              {events.map((e, i) => (
                <tr key={i}>
                  <td className="muted">{timeAgo(e.ts)}</td>
                  <td><span className="chip">{e.kind}</span></td>
                  <td><SeverityBadge severity={e.severity} /></td>
                  <td className="muted">{e.email || "—"}</td>
                  <td className="mono">{e.ip_address || "—"}</td>
                  <td className="muted">{e.detail}</td>
                </tr>
              ))}
              {events.length === 0 && <tr><td colSpan={6}><div className="empty">No security events</div></td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
