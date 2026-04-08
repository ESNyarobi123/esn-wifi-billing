import { API_V1 } from "@/lib/config";
import type { ApiErrorBody, ApiSuccess, TokenPair } from "@/lib/api/types";
import { clearAuthCookies, getAccessToken, getRefreshToken, setAuthCookies } from "@/lib/auth/cookies";

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: ApiErrorBody,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

async function tryRefresh(): Promise<boolean> {
  const rt = getRefreshToken();
  if (!rt || typeof window === "undefined") return false;
  try {
    const res = await fetch(API_V1("/auth/refresh"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
    const raw = await res.text();
    let json: ApiSuccess<{ tokens: TokenPair }> | ApiErrorBody;
    try {
      json = (raw ? JSON.parse(raw) : {}) as ApiSuccess<{ tokens: TokenPair }> | ApiErrorBody;
    } catch {
      return false;
    }
    if (!res.ok || !("success" in json) || !json.success || !json.data?.tokens) return false;
    const { access_token, refresh_token } = json.data.tokens;
    setAuthCookies(access_token, refresh_token);
    return true;
  } catch {
    return false;
  }
}

type Opts = RequestInit & { skipAuth?: boolean; _retried?: boolean };
type DownloadOpts = Omit<Opts, "body"> & { body?: unknown };
type DownloadResult = { blob: Blob; filename: string | null };

async function readJsonBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return {};
  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new ApiRequestError("The server returned an unreadable response.", res.status);
  }
}

function filenameFromDisposition(header: string | null): string | null {
  if (!header) return null;
  const utf = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf?.[1]) return decodeURIComponent(utf[1]);
  const basic = header.match(/filename="?([^"]+)"?/i);
  return basic?.[1] ?? null;
}

export async function apiFetch<T>(path: string, opts: Opts = {}): Promise<T> {
  const { skipAuth, _retried, ...init } = opts;
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body && typeof init.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  if (!skipAuth && typeof window !== "undefined") {
    const at = getAccessToken();
    if (at) headers.set("Authorization", `Bearer ${at}`);
  }

  let res: Response;
  try {
    res = await fetch(API_V1(path), { ...init, headers });
  } catch {
    throw new ApiRequestError("Network error — check your connection and API URL.", 0);
  }

  const json = (await readJsonBody(res)) as ApiSuccess<T> | ApiErrorBody;

  if (res.status === 401 && !_retried && !skipAuth) {
    const ok = await tryRefresh();
    if (ok) return apiFetch<T>(path, { ...opts, _retried: true });
    clearAuthCookies();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    }
  }

  if (!res.ok || typeof json !== "object" || json === null || !("success" in json) || !json.success) {
    const err = (typeof json === "object" && json !== null ? json : {}) as ApiErrorBody;
    const message =
      typeof err.message === "string" && err.message
        ? err.message
        : res.status === 429
          ? "Too many requests."
          : res.statusText || "Request failed.";
    throw new ApiRequestError(message, res.status, "success" in err ? err : undefined);
  }
  return json.data as T;
}

export async function apiDownload(path: string, opts: DownloadOpts = {}): Promise<DownloadResult> {
  const { skipAuth, _retried, body, ...init } = opts;
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && body && typeof body === "string") {
    headers.set("Content-Type", "application/json");
  }
  if (!headers.has("Content-Type") && body && typeof body !== "string") {
    headers.set("Content-Type", "application/json");
  }
  if (!skipAuth && typeof window !== "undefined") {
    const at = getAccessToken();
    if (at) headers.set("Authorization", `Bearer ${at}`);
  }

  let res: Response;
  try {
    res = await fetch(API_V1(path), {
      ...init,
      headers,
      body: body !== undefined && typeof body !== "string" ? JSON.stringify(body) : body,
    });
  } catch {
    throw new ApiRequestError("Network error — check your connection and API URL.", 0);
  }

  if (res.status === 401 && !_retried && !skipAuth) {
    const ok = await tryRefresh();
    if (ok) return apiDownload(path, { ...opts, _retried: true });
    clearAuthCookies();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    }
  }

  if (!res.ok) {
    const contentType = res.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const json = (await readJsonBody(res)) as ApiSuccess<unknown> | ApiErrorBody;
      const err = (typeof json === "object" && json !== null ? json : {}) as ApiErrorBody;
      const message =
        typeof err.message === "string" && err.message
          ? err.message
          : res.status === 429
            ? "Too many requests."
            : res.statusText || "Request failed.";
      throw new ApiRequestError(message, res.status, "success" in err ? err : undefined);
    }
    const message = (await res.text()) || res.statusText || "Request failed.";
    throw new ApiRequestError(message, res.status);
  }

  return {
    blob: await res.blob(),
    filename: filenameFromDisposition(res.headers.get("content-disposition")),
  };
}

export async function apiGet<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: "GET" });
}

export async function apiGetPublic<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: "GET", skipAuth: true });
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export async function apiPostPublic<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    body: body !== undefined ? JSON.stringify(body) : undefined,
    skipAuth: true,
  });
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function apiDelete<T>(path: string): Promise<T | void> {
  try {
    return await apiFetch<T>(path, { method: "DELETE" });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 204) return;
    throw e;
  }
}
