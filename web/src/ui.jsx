import React, { useEffect, useRef, useState } from "react";

export const DEPT_COLORS = {
  Police: "#1d4ed8",
  "Municipal Corporation": "#7c3aed",
  GSRTC: "#d97706",
  Panchayat: "#059669",
  Health: "#0891b2",
};

export function DeptTag({ name }) {
  if (!name) return <span className="chip">Unclassified</span>;
  const c = DEPT_COLORS[name] || "#64748b";
  return (
    <span className="tag-dept" style={{ background: `${c}14`, color: c }}>
      <span className="sq" style={{ background: c }} />
      {name}
    </span>
  );
}

export function StatusBadge({ status }) {
  const s = (status || "unknown").toLowerCase();
  const label = { live: "Online", down: "Offline", degraded: "Degraded", online: "Online", offline: "Offline" }[s] || s;
  return (
    <span className={`badge ${s}`}>
      <span className="dot" style={{ background: "currentColor" }} />
      {label}
    </span>
  );
}

export function SeverityBadge({ severity }) {
  const s = (severity || "low").toLowerCase();
  return <span className={`badge ${s}`}>{s}</span>;
}

// The state emblem brand mark (tricolour logo, transparent bg)
export function Emblem({ size = 36 }) {
  return <img src="/emblem.png" alt="SetuNetra emblem" className="emblem" style={{ height: size, width: "auto" }} />;
}

// Stat card — tricolour top accent, no icon
export function Stat({ label, value, sub, tone = "saffron" }) {
  const t = ["navy", "green", "red", "saffron"].includes(tone) ? tone : "saffron";
  return (
    <div className={`stat t-${t}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value"><Counter value={value} /></div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

// Animated integer counter (parses leading number, keeps suffix like "/5")
export function Counter({ value }) {
  const str = String(value);
  const m = str.match(/^(\d+)(.*)$/);
  const target = m ? parseInt(m[1], 10) : null;
  const suffix = m ? m[2] : "";
  const [n, setN] = useState(target === null ? null : 0);
  useEffect(() => {
    if (target === null) return;
    let raf, start;
    const dur = 700;
    const step = (ts) => {
      if (!start) start = ts;
      const p = Math.min(1, (ts - start) / dur);
      setN(Math.round((1 - Math.pow(1 - p, 3)) * target));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target]);
  if (target === null) return <>{str}</>;
  return <>{n}{suffix}</>;
}

export function BarChart({ data, colorFor }) {
  const top = Math.max(1, ...data.map((d) => d.value));
  return (
    <div>
      {data.map((d) => (
        <div className="bar-row" key={d.label}>
          <div className="bar-label">{d.label}</div>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(100 * d.value) / top}%`, background: colorFor ? colorFor(d) : "#1d4ed8" }} />
          </div>
          <div className="bar-val">{d.value}</div>
        </div>
      ))}
    </div>
  );
}

// SVG donut chart
export function Donut({ segments, size = 150, thickness = 22, centerLabel, centerValue }) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="donut-wrap">
      <svg className="donut" width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#eef2f7" strokeWidth={thickness} />
        {segments.map((seg, i) => {
          const len = (seg.value / total) * c;
          const el = (
            <circle key={i} cx={size / 2} cy={size / 2} r={r} fill="none" stroke={seg.color}
              strokeWidth={thickness} strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-offset}
              strokeLinecap="butt" transform={`rotate(-90 ${size / 2} ${size / 2})`}
              style={{ transition: "stroke-dasharray 0.8s ease" }} />
          );
          offset += len;
          return el;
        })}
        <text x="50%" y="46%" textAnchor="middle" fontFamily="Sora" fontWeight="800" fontSize="26" fill="#0f1c3f">{centerValue}</text>
        <text x="50%" y="60%" textAnchor="middle" fontSize="11" fill="#64748b">{centerLabel}</text>
      </svg>
      <div className="donut-legend">
        {segments.map((s, i) => (
          <div className="donut-leg" key={i}>
            <span className="sq" style={{ background: s.color }} />
            {s.label}
            <span className="lv">{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Flash({ kind, children, onClose }) {
  if (!children) return null;
  return <div className={`flash ${kind}`} onClick={onClose} role="status">{children}</div>;
}

export function timeAgo(iso) {
  if (!iso) return "—";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

// Scroll-reveal: attach ref, adds .in when in view
export function useReveal() {
  const ref = useRef(null);
  useEffect(() => {
    const els = ref.current?.querySelectorAll(".reveal");
    if (!els?.length) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { threshold: 0.12 });
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
  return ref;
}
