import { defineConfig, devices } from "@playwright/test";

const port = process.env.PORT ?? "3000";
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${port}`;

/**
 * Default: `npm run build:standalone` + `start:standalone` (same as Docker/staging; avoids Turbopack HMR under Playwright).
 * `PW_WEB_SERVER=dev` uses `next dev` for local debugging only.
 */
const useDevServer = process.env.PW_WEB_SERVER === "dev";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "list",
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: useDevServer
    ? {
        command: `npm run dev -- --port ${port}`,
        url: baseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
        env: {
          ...process.env,
          NEXT_PUBLIC_API_URL: "http://127.0.0.1:8000",
        },
      }
    : {
        command: `bash -lc 'export NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 && npm run build:standalone && HOSTNAME=127.0.0.1 PORT=${port} node scripts/run-standalone.mjs'`,
        url: baseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 300_000,
        env: {
          ...process.env,
          NEXT_PUBLIC_API_URL: "http://127.0.0.1:8000",
          PORT: port,
          HOSTNAME: "127.0.0.1",
        },
      },
});
