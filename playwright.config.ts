import { defineConfig } from "@playwright/test";

const baseURL =
  process.env.EKC_WEB_URL ?? "https://enterprise-knowledge-copilot-wine.vercel.app";

export default defineConfig({
  testDir: "e2e",
  timeout: 120_000,
  expect: { timeout: 45_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI
    ? [["github"], ["html", { open: "never" }]]
    : [["list"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    actionTimeout: 20_000,
    navigationTimeout: 60_000,
  },
});
