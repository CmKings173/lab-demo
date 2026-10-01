import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  agentRules: false,
  async rewrites() {
    return {
      // afterFiles rewrites precede dynamic filesystem routes. This exact
      // explanation exception reaches the shared handler through an internal alias.
      beforeFiles: [{
        source: "/api/backend/runs/:runId/explanation",
        destination: "/api/lab3/runs/:runId/explanation",
      }],
      afterFiles: [{
        source: "/api/backend/:path*",
        destination: `${backendUrl}/:path*`,
      }],
    };
  },
};

export default nextConfig;
