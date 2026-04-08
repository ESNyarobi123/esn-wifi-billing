const DEFAULT_API = "http://localhost:8000";

let warnedMissingApiUrl = false;

/**
 * JSON API origin (no trailing slash).
 *
 * - **Browser:** always uses `NEXT_PUBLIC_API_URL` (inlined at build time for client bundles).
 * - **Server (RSC, SSR):** uses `INTERNAL_API_URL` when set (e.g. `http://api:8000` in Docker),
 *   then falls back to `NEXT_PUBLIC_API_URL`. This avoids SSR calling `localhost` inside a container.
 *
 * Staging: bake `NEXT_PUBLIC_API_URL` at **build** to the URL browsers must use; set `INTERNAL_API_URL`
 * at **runtime** for the service mesh / Docker network name if it differs.
 */
export function getApiBaseUrl(): string {
  if (typeof window === "undefined") {
    const internal = process.env.INTERNAL_API_URL?.trim();
    if (internal) return internal.replace(/\/$/, "");
  }

  const raw = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!raw) {
    if (typeof window !== "undefined" && process.env.NODE_ENV === "development" && !warnedMissingApiUrl) {
      warnedMissingApiUrl = true;
      console.warn(`[ESN Web] NEXT_PUBLIC_API_URL is unset; using default ${DEFAULT_API}`);
    }
  }
  return raw || DEFAULT_API;
}

export const API_V1 = (path: string) =>
  `${getApiBaseUrl().replace(/\/$/, "")}/api/v1${path.startsWith("/") ? path : `/${path}`}`;
