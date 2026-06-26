// Shared backend HTTP URL helper.
//
// `/api/*`, `/media/*` and `/auth/*` are proxied **same-origin** by Next (see
// next.config.ts rewrites), exactly like lib/api.ts already does — returning a
// relative URL means the browser never needs CORS and the calls work transparently
// over HTTPS. Proxying `/auth/*` lets the Spotify redirect_uri stay on a single
// (Tailscale) HTTPS hostname (e.g. :3200/auth/spotify/callback) instead of pinning
// the OAuth round-trip to the backend port.
export function backendHttpUrl(path: string): string {
  if (
    path.startsWith("/api/") ||
    path === "/api" ||
    path.startsWith("/media/") ||
    path.startsWith("/auth/")
  ) {
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
