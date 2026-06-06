const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "changeme-dev-key";
const BASE = "/api";

async function apiFetch(path: string, options: RequestInit = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
      ...options.headers,
    },
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json();
}

export const api = {
  getMetrics: () => apiFetch("/metrics"),
  listTargets: () => apiFetch("/targets"),
  getTarget: (id: string) => apiFetch(`/targets/${id}`),
  getSignals: (targetId: string, params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params) : "";
    return apiFetch(`/targets/${targetId}/signals${qs}`);
  },
  getReports: (targetId: string) => apiFetch(`/targets/${targetId}/reports`),
  listRuns: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params) : "";
    return apiFetch(`/runs${qs}`);
  },
  triggerRun: (targetId: string) =>
    apiFetch(`/runs/trigger/${targetId}`, { method: "POST" }),
  query: (q: string) =>
    apiFetch("/query", { method: "POST", body: JSON.stringify({ q }) }),
  createTarget: (data: object) =>
    apiFetch("/targets", { method: "POST", body: JSON.stringify(data) }),
  updateTarget: (id: string, data: object) =>
    apiFetch(`/targets/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteTarget: (id: string) =>
    apiFetch(`/targets/${id}`, { method: "DELETE" }),
  compareTargets: (id: string, otherId: string) =>
    apiFetch(`/targets/${id}/compare/${otherId}`, { method: "POST" }),
};
