import React from "react";
import { useReveal, Counter, Emblem } from "../ui";

export default function Landing({ onEnter }) {
  const ref = useReveal();

  return (
    <div className="landing" ref={ref}>
      <div className="tricolour" />
      <nav className="landing-nav">
        <div className="landing-nav-inner">
          <div className="brandmark">
            <Emblem size={40} />
            <div className="brand-text">
              <div className="bt-name">SetuNetra</div>
              <div className="bt-sub">CCTV Command Grid</div>
            </div>
          </div>
          <div className="nav-links">
            <a href="#capabilities">Capabilities</a>
            <a href="#models">Integration</a>
            <a href="#scale">Scale</a>
            <button className="btn btn-sm" onClick={onEnter}>Sign in</button>
            <button className="btn btn-sm btn-primary" onClick={onEnter}>Open Console</button>
          </div>
        </div>
      </nav>

      <header className="hero">
        <div className="hero-grid-bg" />
        <div className="hero-inner">
          <div className="reveal in">
            <div className="hero-badge">
              <span className="pin">Gujarat Police</span>
              Innovation Challenge 2026 · Integrated VMS
            </div>
            <h1>Statewide CCTV, <span className="s">monitored</span> as <span className="g">one grid.</span></h1>
            <p className="hero-sub">
              A unified registry, live viewing wall and cross-vendor federation layer for the
              state's fragmented camera networks — proactive health monitoring, GIS visibility
              and coordinated alerts, without replacing a single existing system.
            </p>
            <div className="hero-cta">
              <button className="btn btn-primary" onClick={onEnter}>Open the Console</button>
              <a className="btn" href="#models">See how it works</a>
            </div>
            <div className="hero-stats">
              <div className="hero-stat"><div className="n"><Counter value="30" /></div><div className="l">Feeds onboarded</div></div>
              <div className="hero-stat"><div className="n"><Counter value="10" /></div><div className="l">Districts covered</div></div>
              <div className="hero-stat"><div className="n"><Counter value="5" /></div><div className="l">Departments</div></div>
            </div>
          </div>

          <div className="hero-mock reveal in">
            <div className="mock-window">
              <div className="mock-top tricolour" />
              <div className="mock-topbar">
                <span className="mock-dot" style={{ background: "#e57373" }} />
                <span className="mock-dot" style={{ background: "#ffb74d" }} />
                <span className="mock-dot" style={{ background: "#81c784" }} />
                <span style={{ marginLeft: 8 }}>Network Health · Live</span>
              </div>
              <div className="mock-body">
                <div className="mock-row">
                  <div className="mock-kpi g"><div className="k">Online</div><div className="v" style={{ color: "#138808" }}>26</div></div>
                  <div className="mock-kpi"><div className="k">Offline</div><div className="v" style={{ color: "#c62828" }}>4</div></div>
                  <div className="mock-kpi n"><div className="k">Alerts</div><div className="v" style={{ color: "#0a1f4d" }}>7</div></div>
                </div>
                <div className="mock-panel">
                  <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 10 }}>Device registry</div>
                  {["#ff9933", "#0a1f4d", "#138808", "#ff9933"].map((c, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 9, margin: "9px 0" }}>
                      <span style={{ width: 8, height: 8, borderRadius: 3, background: c }} />
                      <div className="mock-line" style={{ flex: 1, width: `${72 - i * 8}%` }} />
                      <span style={{ width: 34, height: 7, borderRadius: 4, background: "#e6f4e4" }} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="float-card float-a s"><div className="fc-t">Uptime</div><div className="fc-n">86.7%</div></div>
            <div className="float-card float-b"><div className="fc-t">Federated VMS</div><div className="fc-n">5 vendors</div></div>
          </div>
        </div>
      </header>

      <div className="trust reveal">
        <span className="t-label">Built for</span>
        <span className="t-item">Police</span>
        <span className="t-item">Municipal Corporations</span>
        <span className="t-item">Transport · GSRTC</span>
        <span className="t-item">Panchayat</span>
        <span className="t-item">Health</span>
      </div>

      <section className="section" id="capabilities">
        <div className="section-head reveal">
          <span className="kicker">Capabilities</span>
          <h2>Everything a control room needs, in one console</h2>
          <p>Purpose-built for heterogeneous, multi-department CCTV — no forced rip-and-replace.</p>
        </div>
        <div className="features">
          {[
            { m: "Model 1", t: "Central Registry & GIS", d: "Every camera catalogued with location, department, ownership, connectivity and storage — pinned on an interactive district map." },
            { m: "Model 2", t: "Unified Viewing Wall", d: "Live status and frames from every feed in one grid, with operator event tagging and a searchable, camera-wise index." },
            { m: "Model 3", t: "VMS Federation", d: "Adapter framework speaks each vendor's protocol, exchanges metadata over a bus, and correlates events across systems." },
            { m: "Health", t: "Proactive Monitoring", d: "Continuous connectivity and latency checks surface offline or tampered cameras before an incident, not after." },
            { m: "Model 1", t: "Coverage Gap Analysis", d: "Geometric analysis flags uncovered zones and ageing infrastructure across the state so investment lands where it matters." },
            { m: "Security", t: "Zero-Trust Access", d: "JWT sessions, department-scoped access control, brute-force lockout, rate limiting and an immutable audit trail on every action." },
          ].map((f, i) => (
            <div className="feature reveal" key={i} style={{ transitionDelay: `${(i % 3) * 80}ms` }}>
              <span className="model-chip">{f.m}</span>
              <h3>{f.t}</h3>
              <p>{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="band" id="scale">
        <div className="hero-grid-bg" />
        <div className="section">
          <div className="section-head reveal" style={{ marginBottom: 40 }}>
            <span className="kicker" style={{ color: "#ffb774" }}>Designed for scale</span>
            <h2>From 30 feeds today to the statewide vision</h2>
          </div>
          <div className="band-stats">
            <div className="band-stat reveal"><div className="n"><Counter value="30" /></div><div className="l">Live feeds onboarded</div></div>
            <div className="band-stat reveal" style={{ transitionDelay: "80ms" }}><div className="n"><Counter value="5" /></div><div className="l">VMS vendors federated</div></div>
            <div className="band-stat reveal" style={{ transitionDelay: "160ms" }}><div className="n"><Counter value="10" /></div><div className="l">Districts on the grid</div></div>
            <div className="band-stat reveal" style={{ transitionDelay: "240ms" }}><div className="n">80k+</div><div className="l">Architected capacity</div></div>
          </div>
        </div>
      </section>

      <section className="section" id="models">
        <div className="section-head reveal">
          <span className="kicker">Integration model</span>
          <h2>Onboard, unify, federate</h2>
          <p>Three composable models — the registry is the foundation; viewing and federation build on top.</p>
        </div>
        <div className="steps">
          {[
            { t: "Onboard the registry", d: "Bulk-import, API or manual entry brings every department's cameras into one standardised inventory with GIS pins." },
            { t: "Unify the viewing", d: "The console streams live status and frames from all feeds into one wall — no separate vendor viewers." },
            { t: "Federate & correlate", d: "Pluggable adapters pull metadata from each VMS; the engine links the same entity across systems automatically." },
          ].map((s, i) => (
            <div className="step reveal" key={i} style={{ transitionDelay: `${i * 90}ms` }}>
              <div className="num">{i + 1}</div>
              <h4>{s.t}</h4>
              <p>{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="section" style={{ paddingTop: 0 }}>
        <div className="cta-band reveal">
          <div className="hero-grid-bg" />
          <div style={{ position: "relative" }}>
            <h2>Open the command console</h2>
            <p>Sign in with a demo role and explore the full registry, viewing wall, federation layer and security posture.</p>
            <button className="btn btn-saffron" onClick={onEnter} style={{ padding: "13px 26px" }}>Launch Console</button>
          </div>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="tricolour" style={{ opacity: 0.85 }} />
        <div className="footer-inner">
          <div>
            <div className="brandmark" style={{ marginBottom: 4 }}>
              <Emblem size={34} />
              <div className="brand-text"><div className="bt-name" style={{ fontSize: 16 }}>SetuNetra</div></div>
            </div>
            <p className="fnote">
              A prototype submission for the Gujarat Police Innovation Challenge 2026. Integrated
              Video Management &amp; Analytics — registry, unified viewing and VMS federation.
            </p>
          </div>
          <div className="muted" style={{ fontSize: 12.5, textAlign: "right" }}>
            <div>Integration Models 1 · 2 · 3</div>
            <div style={{ marginTop: 6 }}>© 2026 · For evaluation use</div>
          </div>
        </div>
      </footer>
    </div>
  );
}
