import React, { useEffect, useState } from "react";
import { fetchSnapshot } from "../api";
import { StatusBadge, DeptTag } from "../ui";

export default function CameraDetailModal({ camera, onClose }) {
  const c = camera;
  const [live, setLive] = useState(false);
  const [src, setSrc] = useState(null);

  useEffect(() => {
    let active = true;
    let current = null;
    const tick = async () => {
      const url = await fetchSnapshot(c.external_id);
      if (!active) { if (url) URL.revokeObjectURL(url); return; }
      if (url) { if (current) URL.revokeObjectURL(current); current = url; setSrc(url); setLive(true); }
      else setLive(false);
    };
    tick();
    const id = setInterval(tick, 2500);
    return () => { active = false; clearInterval(id); if (current) URL.revokeObjectURL(current); };
  }, [c.external_id]);

  const rows = [
    ["Device ID", `#${c.external_id}`], ["District", c.district || "—"], ["Camera type", (c.camera_type || "").toUpperCase()],
    ["Priority", (c.priority_tier || "—")], ["Storage tier", c.storage_tier], ["Retention", c.retention_days ? `${c.retention_days} days` : "—"],
    ["Coordinates", c.lat ? `${c.lat.toFixed(4)}, ${c.lon.toFixed(4)}` : "—"], ["Federated from", c.vms_name || "Direct registry"],
  ];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head"><h3>{c.location_name}</h3><button className="close-x" onClick={onClose}>×</button></div>
        <div className="modal-body">
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 14 }}>
            <StatusBadge status={c.status} /><DeptTag name={c.department} />
          </div>
          <div className="cam-frame" style={{ borderRadius: 12, marginBottom: 18 }}>
            {src && live ? <img src={src} alt="" /> : <div className="noimg"><span>{c.status === "live" ? "Awaiting frame from ingest" : "No signal"}</span></div>}
            <div className="cam-scanline" />
            <div className={`cam-livechip ${live ? "" : "off"}`}><span className="rec" />{live ? "LIVE" : "OFFLINE"}</div>
          </div>
          <table className="tbl">
            <tbody>
              {rows.map(([k, v]) => (
                <tr key={k}><td className="muted" style={{ width: 150 }}>{k}</td><td className="cell-strong">{v}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
