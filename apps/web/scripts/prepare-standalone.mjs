/**
 * After `next build` with `output: "standalone"`, copy traced assets Next does not bundle.
 * Run from apps/web: `node scripts/prepare-standalone.mjs`
 *
 * Copies:
 *   .next/static  → .next/standalone/.next/static  (chunk/CSS assets)
 *   public/       → .next/standalone/public        (favicon, static files)
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const standalone = path.join(root, ".next", "standalone");
const staticSrc = path.join(root, ".next", "static");
const staticDst = path.join(standalone, ".next", "static");
const publicSrc = path.join(root, "public");
const publicDst = path.join(standalone, "public");

if (!fs.existsSync(standalone)) {
  console.error("[prepare-standalone] Missing .next/standalone — run `next build` first.");
  process.exit(1);
}
if (!fs.existsSync(staticSrc)) {
  console.error("[prepare-standalone] Missing .next/static — run `next build` first.");
  process.exit(1);
}

fs.mkdirSync(path.dirname(staticDst), { recursive: true });
fs.rmSync(staticDst, { recursive: true, force: true });
fs.cpSync(staticSrc, staticDst, { recursive: true });
console.log("[prepare-standalone] Copied .next/static → .next/standalone/.next/static");

fs.rmSync(publicDst, { recursive: true, force: true });
if (fs.existsSync(publicSrc)) {
  fs.cpSync(publicSrc, publicDst, { recursive: true });
  console.log("[prepare-standalone] Copied public → .next/standalone/public");
} else {
  fs.mkdirSync(publicDst, { recursive: true });
  console.log("[prepare-standalone] Created empty .next/standalone/public (no public/ in repo)");
}
