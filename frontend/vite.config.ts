import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/income": "http://127.0.0.1:8000",
      "/taxes": "http://127.0.0.1:8000",
      "/w4": "http://127.0.0.1:8000",
      "/projections": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});
