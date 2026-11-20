import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// In development the UI runs on :5173 and proxies the API and WebSocket to `bb serve` on :8765.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8765",
      "/ws": { target: "ws://127.0.0.1:8765", ws: true },
    },
  },
  test: {
    environment: "node",
  },
});
