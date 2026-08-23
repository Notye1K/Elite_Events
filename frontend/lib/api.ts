export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getToken() {
  return typeof window === "undefined" ? null : localStorage.getItem("token");
}
export function getUser() {
  try {
    return JSON.parse(localStorage.getItem("user") || "null");
  } catch {
    return null;
  }
}
export function saveSession(data: any) {
  localStorage.setItem("token", data.access_token);
  localStorage.setItem("user", JSON.stringify(data.user));

  window.dispatchEvent(new Event("auth-changed"));
}
export function clearSession() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");

  window.dispatchEvent(new Event("auth-changed"));
}

export async function api(path: string, init: RequestInit = {}) {
  const token = getToken();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API}${path}`, { ...init, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Erro inesperado");
  return data;
}
