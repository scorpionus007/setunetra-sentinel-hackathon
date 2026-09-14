import React, { useCallback, useEffect, useState } from "react";
import Landing from "./components/Landing";
import LoginView from "./components/LoginView";
import Dashboard from "./components/Dashboard";
import RegistryView from "./components/RegistryView";
import ViewingView from "./components/ViewingView";
import FederationView from "./components/FederationView";
import SecurityView from "./components/SecurityView";
import AuditView from "./components/AuditView";
import CameraDetailModal from "./components/CameraDetailModal";
import { Emblem } from "./ui";
import { getUser, clearSession, getToken, canSeeSecurity, canSeeAudit } from "./auth";
import { getStats, getCameras, getCoverageGaps, getAlerts } from "./api";

const NAV = [
  { id: "dashboard", label: "Overview", model: "Command Center", section: "Monitoring" },
  { id: "registry", label: "Registry & GIS", model: "Model 1", section: "Monitoring" },
  { id: "viewing", label: "Viewing Wall", model: "Model 2", section: "Monitoring" },
  { id: "federation", label: "VMS Federation", model: "Model 3", section: "Monitoring" },
  { id: "security", label: "Security", model: "Governance", section: "Governance", gate: canSeeSecurity },
  { id: "audit", label: "Audit Trail", model: "Governance", section: "Governance", gate: canSeeAudit },
];

export default function App() {
  const [user, setUser] = useState(getUser());
  const [screen, setScreen] = useState("landing");
  const [view, setView] = useState("dashboard");
  const [stats, setStats] = useState(null);
  const [cameras, setCameras] = useState([]);
  const [gaps, setGaps] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [selectedCamera, setSelectedCamera] = useState(null);

  const loadShared = useCallback(async () => {
    if (!getToken()) return;
    try {
      const [s, c, g, a] = await Promise.all([getStats(), getCameras(), getCoverageGaps(), getAlerts()]);
      setStats(s); setCameras(c); setGaps(g); setAlerts(a);
    } catch (e) { console.warn(e.message); }
  }, []);

  useEffect(() => {
    const onLogout = () => { setUser(null); clearSession(); setScreen("login"); };
    window.addEventListener("setunetra:logout", onLogout);
    return () => window.removeEventListener("setunetra:logout", onLogout);
  }, []);

  useEffect(() => { if (user) loadShared(); }, [user, loadShared]);

  if (!user) {
    if (screen === "login") return <LoginView onLogin={setUser} onBack={() => setScreen("landing")} />;
    return <Landing onEnter={() => setScreen("login")} />;
  }

  const visibleNav = NAV.filter((n) => !n.gate || n.gate(user));
  const sections = [...new Set(visibleNav.map((n) => n.section))];
  const openAlerts = alerts.filter((a) => a.status === "new").length;
  const active = NAV.find((n) => n.id === view) || NAV[0];

  function logout() { clearSession(); setUser(null); setScreen("landing"); }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-top-rule" />
        <div className="sidebar-brand">
          <div className="brandmark">
            <Emblem size={38} />
            <div className="brand-text">
              <div className="bt-name">SetuNetra</div>
              <div className="bt-sub">CCTV Command Grid</div>
            </div>
          </div>
          <div className="gov-line">Gujarat Police · Home Department</div>
        </div>
        <nav className="nav">
          {sections.map((sec) => (
            <div key={sec}>
              <div className="nav-section">{sec}</div>
              {visibleNav.filter((n) => n.section === sec).map((n) => (
                <button key={n.id} className={`nav-item ${view === n.id ? "active" : ""}`} onClick={() => setView(n.id)}>
                  <span>{n.label}</span>
                  {n.id === "dashboard" && openAlerts > 0 && <span className="nav-badge">{openAlerts}</span>}
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-user">
          <div className="user-row">
            <div className="user-avatar">{(user.email || "?")[0].toUpperCase()}</div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="user-email">{user.email}</div>
              <div className="user-role">{user.role_label || user.role}</div>
            </div>
            <button className="btn btn-sm btn-ghost" onClick={logout}>Sign out</button>
          </div>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div className="topbar-title">
            <h1>{active.label}</h1>
            <div className="crumb">SetuNetra · {active.model}</div>
          </div>
          <div className="topbar-actions">
            <span className="model-pill">{active.model}</span>
            <button className="btn btn-sm" onClick={loadShared}>Refresh</button>
          </div>
        </div>

        <div className="content">
          {view === "dashboard" && <Dashboard stats={stats} cameras={cameras} alerts={alerts} gaps={gaps} onSelectCamera={setSelectedCamera} onGoto={setView} />}
          {view === "registry" && <RegistryView cameras={cameras} user={user} onRefresh={loadShared} onSelectCamera={setSelectedCamera} />}
          {view === "viewing" && <ViewingView cameras={cameras} user={user} onRefresh={loadShared} />}
          {view === "federation" && <FederationView user={user} onRefresh={loadShared} />}
          {view === "security" && <SecurityView />}
          {view === "audit" && <AuditView />}
        </div>
      </main>

      {selectedCamera && <CameraDetailModal camera={selectedCamera} onClose={() => setSelectedCamera(null)} />}
    </div>
  );
}
