import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/v1": apiProxyTarget,
        "/healthz": apiProxyTarget
      }
    },
    preview: {
      port: 4173
    },
    test: {
      environment: "jsdom",
      globals: true,
      include: ["tests/**/*.test.{ts,tsx}"],
      setupFiles: ["./tests/setup.ts"]
    }
  };
});
