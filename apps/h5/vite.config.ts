import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

/**
 * Serves `/device`: the H5 inside a fixed 390 × 844 frame so a desktop browser
 * shows the same proportions as the reference mobile viewport. Development only —
 * the production bundle and the real mobile viewport are untouched.
 */
function devicePreview(): Plugin {
  const page = fileURLToPath(new URL("./dev/device-frame.html", import.meta.url));
  return {
    name: "stylecapture-device-preview",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const path = request.url?.split("?")[0];
        if (path !== "/device" && path !== "/device/") {
          next();
          return;
        }
        response.setHeader("Content-Type", "text/html; charset=utf-8");
        response.setHeader("Cache-Control", "no-store");
        response.end(readFileSync(page, "utf8"));
      });
    }
  };
}

export default defineConfig({
  plugins: [react(), devicePreview()],
  server: {
    port: 5173,
    proxy: {
      "/v1": "http://localhost:8000",
      "/healthz": "http://localhost:8000"
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
});
