import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../../.stylecapture/playwright",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    baseURL: process.env.STYLECAPTURE_E2E_BASE_URL ?? "http://127.0.0.1:5173",
    viewport: { width: 390, height: 844 },
    trace: "off",
    screenshot: "off"
  }
});
