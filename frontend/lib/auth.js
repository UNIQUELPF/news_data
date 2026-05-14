export const TOKEN_KEY = "news_auth_token";
export const USER_KEY = "news_auth_user";

export function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser() {
  if (typeof window === "undefined") return null;
  const userStr = localStorage.getItem(USER_KEY);
  if (!userStr) return null;
  try {
    return JSON.parse(userStr);
  } catch (e) {
    return null;
  }
}

export function setAuth(token, user) {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export async function fetchWithAuth(url, options = {}) {
  const token = getToken();
  const headers = { ...options.headers };
  
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  
  if (options.body && !(options.body instanceof FormData) && typeof options.body !== 'string') {
    options.body = JSON.stringify(options.body);
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, { ...options, headers });
  
  if (response.status === 401) {
    clearAuth();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      // Clear specific user info but keep the path
      localStorage.removeItem(USER_KEY);
      window.location.href = "/login?redirect=" + encodeURIComponent(window.location.pathname + window.location.search);
    }
  }
  
  return response;
}
