import { defineConfig } from "vitest/config";

// Vite 8 compiles TSX with oxc (React automatic runtime from tsconfig) and resolves the
// "@/*" alias from tsconfig, so no React or tsconfig-paths plugins are needed.
export default defineConfig({
  resolve: { tsconfigPaths: true },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
    env: { NEXT_PUBLIC_API_URL: "http://api.test" },
  },
});
