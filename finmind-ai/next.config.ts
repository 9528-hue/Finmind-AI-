import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  // Do NOT add trailing slashes to URLs automatically
  trailingSlash: false,

  // Proxy all /api/* requests to the FastAPI backend.
  // This makes the entire app single-origin on localhost:3000.
  // The browser never sees port 8000 — no CORS issues.
  async rewrites() {
    return [
      {
        source: "/api/health",
        destination: `${BACKEND_URL}/health`,
      },
      // FastAPI's collection routes require trailing slashes. Route these
      // explicitly so Next.js does not trigger a cross-origin 307 that drops
      // the Authorization header.
      {
        source: "/api/analytics",
        destination: `${BACKEND_URL}/analytics/`,
      },
      {
        source: "/api/transactions",
        destination: `${BACKEND_URL}/transactions/`,
      },
      {
        source: "/api/alerts",
        destination: `${BACKEND_URL}/alerts/`,
      },
      // Match /api/some/path AND /api/some/path/ (with or without trailing slash)
      {
        source: "/api/:path*/",
        destination: `${BACKEND_URL}/:path*/`,
      },
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
