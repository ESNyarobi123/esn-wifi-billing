/**
 * Run production server from the standalone output (same layout as Docker CMD).
 * Expects `node scripts/prepare-standalone.mjs` to have been run after build.
 *
 * Env (optional): PORT (default 3000), HOSTNAME (default 0.0.0.0)
 */
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const standalone = path.join(root, ".next", "standalone");
const serverJs = path.join(standalone, "server.js");

if (!fs.existsSync(serverJs)) {
  console.error("[run-standalone] Missing .next/standalone/server.js — run `npm run build:standalone` first.");
  process.exit(1);
}

const port = process.env.PORT || "3000";
const hostname = process.env.HOSTNAME || "0.0.0.0";
const env = {
  ...process.env,
  PORT: port,
  HOSTNAME: hostname,
  NODE_ENV: "production",
};

const r = spawnSync(process.execPath, ["server.js"], {
  cwd: standalone,
  stdio: "inherit",
  env,
});
process.exit(r.status ?? 1);
