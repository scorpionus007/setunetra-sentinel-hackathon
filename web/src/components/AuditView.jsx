import React, { useEffect, useState } from "react";
import { getAuditLogs } from "../api";
import { Flash, timeAgo } from "../ui";

export default function AuditView() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [action, setAction] = useState("");
  const [outcome, setOutcome] = useState("");
  const [err, setErr] = useState(null);

  function load() {
    const params = { limit: 100 };
    if (action) params.action = action;
    if (outcome) params.outcome = outcome;
    getAuditLogs(params).then((d) => { setLogs(d.logs); setTotal(d.total); }).catch((e) => setErr(e.message));
  }
  useEffect(load, [action, outcome]);

  function exportCsv() {
    const cols = ["timestamp", "user_email", "role", "action", "resource", "outcome", "ip_address"];
    const rows = logs.map((l) => cols.map((k) => `"${l[k] ?? ""}"`).join(","));
    const blob = new Blob([cols.join(",") + "\n" + rows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "setunetra_audit.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  if (err) return <Flash kind="err">{err}</Flash>;

  return (
    <>
      <div className="toolbar">
        <select className="input" value={action} onChange={(e) => setAction(e.target.value)}><option value="">All actions</option>{["login", "create", "update", "delete", "bulk_onboard", "vms_sync", "tag_event"].map((a) => <option key={a}>{a}</option>)}</select>
        <select className="input" value={outcome} onChange={(e) => setOutcome(e.target.value)}><option value="">Any outcome</option>{["success", "denied", "error"].map((o) => <option key={o}>{o}</option>)}</select>
        <div className="spacer" />
        <button className="btn btn-sm" onClick={exportCsv}>Export CSV</button>
      </div>

      <div className="panel">
        <div className="panel-head"><h3>Immutable Audit Trail</h3><span className="hint">{total} entries</span></div>
        <div className="table-wrap">
          <table className="tbl">
            <thead><tr><th>Time</th><th>User</th><th>Role</th><th>Action</th><th>Resource</th><th>Outcome</th><th>IP</th></tr></thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id}>
                  <td className="muted">{timeAgo(l.timestamp)}</td>
                  <td className="cell-strong">{l.user_email || "—"}</td>
                  <td><span className="chip">{l.role || "—"}</span></td>
                  <td className="cell-strong">{l.action}</td>
                  <td className="mono muted">{l.resource}</td>
                  <td><span className={`badge ${l.outcome === "success" ? "online" : l.outcome === "denied" ? "high" : "down"}`}>{l.outcome}</span></td>
                  <td className="mono">{l.ip_address || "—"}</td>
                </tr>
              ))}
              {logs.length === 0 && <tr><td colSpan={7}><div className="empty">No audit entries</div></td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
