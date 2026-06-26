import type { NextConfig } from "next";

// HTTP API is proxied through Next (avoids CORS): a phone only talks to :3200
// for REST. The WebSocket connects directly to the backend port — see lib/useGameSocket.ts.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8200";

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    // No server-side optimization: the standalone runtime is node:20-alpine (musl)
    // and sharp's prebuilt binaries are flaky there, and the optimizer adds little
    // for tiny Spotify thumbnails on a LAN. next/image still gives lazy-loading +
    // explicit dimensions (less layout shift). unoptimized bypasses the optimizer,
    // so remotePatterns aren't needed.
    unoptimized: true,
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` },
      // Serve uploaded question images same-origin (backend serves /media/*).
      { source: "/media/:path*", destination: `${BACKEND_URL}/media/:path*` },
      // Spotify OAuth login/callback proxied same-origin so a single (Tailscale)
      // HTTPS hostname works: the redirect_uri can stay on :3200 (see backend.ts).
      { source: "/auth/:path*", destination: `${BACKEND_URL}/auth/:path*` },
    ];
  },
};

export default nextConfig;
