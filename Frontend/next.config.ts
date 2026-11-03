import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker: .next/standalone holds a minimal server.js + only the node_modules it needs.
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  experimental: {
    // Pages render inside a client-side auth guard (no session on the server), so automatic
    // instant-navigation validation can never see them and reports every page as "dropped".
    // Validate only segments that opt in with `export const instant`.
    instantInsights: { validationLevel: "manual-warning" },
    // Self-hosted `next start` buffers forwarded request bodies (rewrites below) up to 10 MB by
    // default and cuts the rest: allow the API's 25 MB uploads plus multipart overhead.
    proxyClientMaxBodySize: "26mb",
  },
  // Hosted without Nginx (Vercel + a separately hosted API): set BACKEND_URL (server-side, read
  // at build time) and leave NEXT_PUBLIC_API_URL empty. The browser then calls /api on THIS
  // origin and the request is forwarded, so the refresh cookie stays first-party (SameSite=Lax).
  async rewrites() {
    const backend = process.env.BACKEND_URL?.replace(/\/+$/, "");
    return backend ? [{ source: "/api/:path*", destination: `${backend}/api/:path*` }] : [];
  },
  // Keep the dev-only Next.js badge away from the user menu and the chat composer.
  devIndicators: { position: "top-right" },
  turbopack: {
    // This folder is the app root (the repo root also holds ai/ and Backend/); pinning it stops
    // Next from picking up stray lockfiles in parent folders.
    root: path.join(__dirname),
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
