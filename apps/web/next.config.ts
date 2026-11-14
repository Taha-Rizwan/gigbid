import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Deployed as a Docker container: `node .next/standalone/server.js`.
  output: "standalone",
  // Server-Sent Events from /api/runs/{id}/stream must not be buffered by gzip.
  compress: false,
  poweredByHeader: false,
  // Same-origin API: the browser only ever talks to this origin, so the
  // backend's httpOnly session cookie is first-party and no CORS is needed.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_URL}/api/:path*`,
      },
    ];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
