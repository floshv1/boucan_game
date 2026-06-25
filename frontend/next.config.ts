import type { NextConfig } from "next";

// HTTP API is proxied through Next (avoids CORS): a phone only talks to :3200
// for REST. The WebSocket connects directly to the backend port — see lib/useGameSocket.ts.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8200";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` },
      // Serve uploaded question images same-origin (backend serves /media/*).
      { source: "/media/:path*", destination: `${BACKEND_URL}/media/:path*` },
    ];
  },
};

export default nextConfig;
