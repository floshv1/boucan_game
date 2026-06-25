// Thin typed fetch wrapper (mirrors discord-bot/dashboard/web/lib/api.ts).
// Requests use relative paths; Next rewrites proxy /api/* to the backend.

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export interface CreatedSession {
  code: string;
  host_secret: string;
}

export function createSession(): Promise<CreatedSession> {
  return apiFetch<CreatedSession>("/api/sessions", { method: "POST" });
}

export function sessionExists(code: string): Promise<{ exists: boolean; code: string }> {
  return apiFetch(`/api/sessions/${encodeURIComponent(code)}`);
}
