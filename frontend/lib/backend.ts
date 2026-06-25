// Shared backend HTTP URL helper.
// The Next.js page is served on :3200 but the backend API lives on :8200.
// This mirrors backendWsUrl() in useGameSocket.ts and the private copy in
// useSpotifyPlayer.ts.

export function backendHttpUrl(path: string): string {
  if (typeof window === "undefined") {
    // SSR guard — backend URL is not available server-side.
    return path;
  }
  const proto = window.location.protocol; // "http:" or "https:"
  const port = process.env.NEXT_PUBLIC_BACKEND_PORT ?? "8200";
  return `${proto}//${window.location.hostname}:${port}${path}`;
}
