import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.ts",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
  server: {
    proxy: {
      "/taxes/": "http://127.0.0.1:8000",
      "/w4/": "http://127.0.0.1:8000",
      "/projections/": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});
