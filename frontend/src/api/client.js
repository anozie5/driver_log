// ─────────────────────────────────────────────────────────────
// API base URL — swap for production or use import.meta.env.VITE_API_URL
// ─────────────────────────────────────────────────────────────
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ── Token helpers ─────────────────────────────────────────────
export function getToken() {
  return localStorage.getItem("access");
}
export function getRefresh() {
  return localStorage.getItem("refresh");
}
export function saveTokens(access, refresh) {
  localStorage.setItem("access", access);
  if (refresh) localStorage.setItem("refresh", refresh);
}
export function clearTokens() {
  localStorage.removeItem("access");
  localStorage.removeItem("refresh");
}

// ── Core fetch wrapper ────────────────────────────────────────
async function api(method, path, body, opts = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    ...opts,
  });

  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw { status: res.status, data };
  return data;
}

// ── Auth ──────────────────────────────────────────────────────
export const signup = (d) => api("POST", "/auth/signup/", d);
export const login = (d) => api("POST", "/auth/login/", d);
export const getProfile = () => api("GET", "/auth/profile/");
export const updateProfile = (d) => api("PATCH", "/auth/profile/", d);
export const resetPassword = (d) => api("POST", "/auth/password-reset/", d);
export const changeEmail = (d) => api("POST", "/auth/change-email/", d);

// ── Daily Logs ────────────────────────────────────────────────
export const getLogs = (q) =>
  api("GET", `/log/logs/?${new URLSearchParams(q)}`);
export const getLog = (id) => api("GET", `/log/logs/${id}/`);
export const createLog = (d) => api("POST", "/log/logs/", d);
export const patchLog = (id, d) => api("PATCH", `/log/logs/${id}/`, d);
export const deleteLog = (id) => api("DELETE", `/log/logs/${id}/`);

// ── Activity Logs ─────────────────────────────────────────────
export const getActs = (logId) => api("GET", `/log/logs/${logId}/acts/`);
export const createAct = (logId, d) =>
  api("POST", `/log/logs/${logId}/acts/`, d);
export const patchAct = (pk, d) => api("PATCH", `/log/acts/${pk}/`, d);
export const deleteAct = (pk) => api("DELETE", `/log/acts/${pk}/`);

// ── Co-driver workflow ────────────────────────────────────────
export const getPendingCoDrivers = () =>
  api("GET", "/log/logs/pending-co-drivers/");
export const submitCoDriver = (logId, primaryId) =>
  api("POST", `/log/logs/${logId}/submit-co-driver/`, {
    primary_log_id: primaryId,
  });
export const approveCoDriver = (primaryId, coId, approve) =>
  api("PATCH", `/log/logs/${primaryId}/approve-co-driver/`, {
    co_driver_log_id: coId,
    approve,
  });

// ── All Authenticated User ───────────────────────────────────────────────────
export const getDrivers = () => api("GET", "/log/managers/drivers/"); // keep for ManagerPage
export const getDriverLogs = (id, q) =>
  api("GET", `/log/managers/drivers/${id}/logs/?${new URLSearchParams(q)}`); // keep for ManagerPage
export const searchDrivers = (q) =>
  api("GET", `/log/drivers/search/?q=${encodeURIComponent(q)}`);
export const getDriverPublicLogs = (id, q) =>
  api("GET", `/log/drivers/${id}/logs/?${new URLSearchParams(q)}`);

// ── Trips ─────────────────────────────────────────────────────
export const getTrips = () => api("GET", "/trip/trips/");
export const getTrip = (id) => api("GET", `/trip/trips/${id}/`);
export const planTrip = (d) => api("POST", "/trip/trips/", d);
export const deleteTrip = (id) => api("DELETE", `/trip/trips/${id}/`);
export const replanTrip = (id) => api("POST", `/trip/trips/${id}/replan/`);
