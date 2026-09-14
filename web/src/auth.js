// JWT auth client — token in localStorage, Bearer header on every request.
const TOKEN_KEY = "setunetra_token";
const USER_KEY = "setunetra_user";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setSession(token, user) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    /* ignore */
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    /* ignore */
  }
}

export function authHeaders(extra = {}) {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

// Role → level for gating UI affordances (mirrors the server ladder).
export const ROLE_LEVELS = {
  viewer: 1,
  auditor: 1,
  station_officer: 2,
  dept_officer: 3,
  admin: 4,
};

export function hasLevel(user, role) {
  if (!user) return false;
  return (ROLE_LEVELS[user.role] || 0) >= (ROLE_LEVELS[role] || 99);
}

export function canSeeSecurity(user) {
  return !!user && ["admin", "auditor", "dept_officer"].includes(user.role);
}

export function canSeeAudit(user) {
  return !!user && ["admin", "auditor"].includes(user.role);
}

export const DEMO_ACCOUNTS = [
  { email: "admin@setunetra.gov.in", password: "Admin@123", label: "State Admin", role: "admin" },
  { email: "police@setunetra.gov.in", password: "Police@123", label: "Police Officer", role: "dept_officer" },
  { email: "rajkot@setunetra.gov.in", password: "Station@123", label: "Station Officer", role: "station_officer" },
  { email: "auditor@setunetra.gov.in", password: "Audit@123", label: "Security Auditor", role: "auditor" },
  { email: "viewer@setunetra.gov.in", password: "Viewer@123", label: "Control Room", role: "viewer" },
];
