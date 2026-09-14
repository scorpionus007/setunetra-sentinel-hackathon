// SetuNetra API client — Registry / Viewing / Federation / Security.
import { authHeaders, clearSession } from "./auth";

export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function request(path, { method = "GET", body, raw = false } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      Accept: "application/json",
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...authHeaders(),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    clearSession();
    window.dispatchEvent(new Event("setunetra:logout"));
    throw new Error("Session expired — please sign in again");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || `HTTP ${res.status}`);
    throw new Error(detail);
  }
  return raw ? res : res.json();
}

// --- auth ---
export async function login(email, password) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Login failed (${res.status})`);
  return data; // {token, user}
}

// --- registry / model 1 ---
export const getStats = () => request("/api/stats");
export const getCameras = () => request("/api/cameras");
export const getCameraHealth = () => request("/api/cameras/health");
export const getCoverageGaps = () => request("/api/coverage/gaps");
export const deleteCamera = (extId) => request(`/api/cameras/${encodeURIComponent(extId)}`, { method: "DELETE" });
export const onboardManual = (cam) => request("/api/onboarding/manual", { method: "POST", body: cam });
export const validateBulk = (payload) => request("/api/onboarding/validate", { method: "POST", body: payload });
export const onboardBulk = (payload) => request("/api/onboarding/bulk", { method: "POST", body: payload });
export const getOnboardTemplate = () => request("/api/onboarding/template");

// --- viewing / model 2 ---
export const getCameraEvents = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return request(`/api/camera-events${q ? `?${q}` : ""}`);
};
export const tagEvent = (payload) => request("/api/camera-events", { method: "POST", body: payload });
export const getWatchlist = () => request("/api/watchlist");
export const addWatchlist = (entry) => request("/api/watchlist", { method: "POST", body: entry });
export function snapshotUrl(extId) {
  return `${API_BASE}/api/cameras/${encodeURIComponent(extId)}/snapshot`;
}

// Snapshots are auth-gated, and <img> can't send the bearer header — so fetch
// the JPEG with the token and hand back an object URL (or null when no frame).
export async function fetchSnapshot(extId) {
  try {
    const res = await fetch(snapshotUrl(extId), { headers: authHeaders() });
    if (res.status !== 200) return null;
    const blob = await res.blob();
    if (!blob || !blob.size) return null;
    return URL.createObjectURL(blob);
  } catch {
    return null;
  }
}
export const activateCamera = (extId) =>
  request(`/api/cameras/${encodeURIComponent(extId)}/activate`, { method: "POST" }).catch(() => null);

// --- alerts ---
export const getAlerts = (status) => request(`/api/alerts${status ? `?status=${status}` : ""}`);
export const updateAlert = (id, status) => request(`/api/alerts/${id}`, { method: "PATCH", body: { status } });

// --- federation / model 3 ---
export const getVmsSystems = () => request("/api/vms");
export const getFederatedEvents = (limit = 50) => request(`/api/vms/events?limit=${limit}`);
export const getCorrelations = () => request("/api/vms/correlations");
export const getFederationAnalytics = () => request("/api/vms/analytics");
export const syncVms = (id) => request(`/api/vms/${id}/sync`, { method: "POST" });

// --- security / cyber ---
export const getSecurityPosture = () => request("/api/security/posture");
export const getSecurityEvents = (limit = 50) => request(`/api/security/events?limit=${limit}`);
export const getAuditLogs = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return request(`/api/audit/logs${q ? `?${q}` : ""}`);
};
