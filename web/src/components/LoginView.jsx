import React, { useState } from "react";
import { login } from "../api";
import { setSession, DEMO_ACCOUNTS } from "../auth";
import { Emblem } from "../ui";

export default function LoginView({ onLogin, onBack }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e?.preventDefault();
    setError(""); setBusy(true);
    try {
      const { token, user } = await login(email.trim(), password);
      setSession(token, user);
      onLogin(user);
    } catch (err) { setError(err.message || "Login failed"); }
    finally { setBusy(false); }
  }
  function useDemo(a) { setEmail(a.email); setPassword(a.password); setError(""); }

  return (
    <div className="auth-wrap">
      <div className="auth-brandside">
        <div className="hero-grid-bg" />
        <div className="brandmark" style={{ position: "relative" }}>
          <Emblem size={46} />
          <div className="brand-text">
            <div className="bt-name" style={{ color: "#fff", fontSize: 20 }}>SetuNetra</div>
            <div className="bt-sub" style={{ color: "#a9b6d6" }}>CCTV Command Grid</div>
          </div>
        </div>
        <div style={{ position: "relative" }}>
          <h2>Proactive monitoring for the state's camera networks.</h2>
          <p>One console for registry, live viewing and cross-vendor federation — secured with role-based access and a full audit trail.</p>
          <div style={{ marginTop: 26, display: "flex", flexDirection: "column", gap: 13 }}>
            {["Department-scoped access control", "Immutable audit of every action", "No existing VMS replaced"].map((t) => (
              <div key={t} className="checkline"><span className="tick">✓</span>{t}</div>
            ))}
          </div>
        </div>
        <div style={{ position: "relative", color: "#8497c4", fontSize: 12 }}>Gujarat Police Innovation Challenge 2026 · Prototype</div>
      </div>

      <div className="auth-formside">
        <div className="auth-card">
          {onBack && <button className="btn btn-sm btn-ghost" onClick={onBack} style={{ marginBottom: 18, marginLeft: -8 }}>← Back to home</button>}
          <h1>Sign in to the console</h1>
          <div className="sub">Use a demo role below, or enter your official credentials.</div>
          {error && <div className="auth-error">{error}</div>}
          <form onSubmit={submit}>
            <div className="form-group">
              <label>Official email</label>
              <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="officer@setunetra.gov.in" autoFocus />
            </div>
            <div className="form-group">
              <label>Password</label>
              <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
            </div>
            <button className="btn btn-primary" type="submit" disabled={busy || !email || !password} style={{ width: "100%" }}>
              {busy ? "Authenticating…" : "Sign in"}
            </button>
          </form>
          <div className="demo-accounts">
            <div className="demo-label">Demo roles — click to fill</div>
            <div className="demo-chips">
              {DEMO_ACCOUNTS.map((a) => (
                <button key={a.email} className="demo-chip" onClick={() => useDemo(a)} type="button">{a.label}</button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
