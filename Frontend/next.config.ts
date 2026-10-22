import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  experimental: {
    // Pages render inside a client-side auth guard (no session on the server), so automatic
    // instant-navigation validation can never see them and reports every page as "dropped".
    // Validate only segments that opt in with `export const instant`.
    instantInsights: { validationLevel: "manual-warning" },
  },
  // Keep the dev-only Next.js badge away from the sidebar's user menu (bottom-left).
  devIndicators: { position: "bottom-right" },
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
