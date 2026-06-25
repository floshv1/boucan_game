// Shared backend HTTP URL helper.
//
// `/api/*` and `/media/*` are proxied **same-origin** by Next (see next.config.ts
// rewrites), exactly like lib/api.ts already does — returning a relative URL means
// the browser never needs CORS and the calls work transparently over HTTPS.
//
// Everything else (the Spotify OAuth login redirect at `/auth/*`) is reached
// directly on the backend port: Spotify's redirect_uri is pinned to that origin,
// so the round-trip must not go through the proxy.
export function backendHttpUrl(path: string): string {
  if (path.startsWith("/api/") || path === "/api" || path.startsWith("/media/")) {
    return path; // same-origin, proxied by Next
  }
  if (typeof window === "undefined") {
    // SSR guard — backend URL is not available server-side.
    return path;
  }
  const proto = window.location.protocol; // "http:" or "https:"
  const port = process.env.NEXT_PUBLIC_BACKEND_PORT ?? "8200";
  return `${proto}//${window.location.hostname}:${port}${path}`;
}
