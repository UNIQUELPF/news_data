export function apiBase() {
  const envBase = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (envBase) return envBase.replace(/\/$/, "");
  if (typeof window === "undefined") return "http://127.0.0.1:8000";
  return window.location.origin;
}

export function buildRequestUrl(path, query, base = apiBase()) {
  const url = new URL(path, `${base}/`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== "" && value !== "all") {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url;
}

export async function request(path, { query, method = "GET", body, adminToken, adminActor } = {}) {
  const url = buildRequestUrl(path, query);

  const response = await fetch(url.toString(), {
    method,
    headers: {
      Accept: "application/json",
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(path.startsWith("/api/v1/pipeline") && adminToken ? { "X-Admin-Token": adminToken } : {}),
      ...(path.startsWith("/api/v1/pipeline") && adminActor ? { "X-Admin-Actor": adminActor } : {})
    },
    body: body ? JSON.stringify(body) : undefined
  });

  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json();
      detail = payload?.detail || payload?.error || "";
    } catch {}
    throw new Error(detail ? `${response.status} ${detail}` : `${response.status} Request failed`);
  }

  return response.json();
}
