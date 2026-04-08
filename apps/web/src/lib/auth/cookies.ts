const AT = "esn_at";
const RT = "esn_rt";

function parseCookies(): Record<string, string> {
  if (typeof document === "undefined") return {};
  return Object.fromEntries(
    document.cookie.split(";").map((c) => {
      const [k, ...v] = c.trim().split("=");
      return [k, decodeURIComponent(v.join("="))];
    }),
  );
}

export function getAccessToken(): string | null {
  const v = parseCookies()[AT];
  return v || null;
}

export function getRefreshToken(): string | null {
  const v = parseCookies()[RT];
  return v || null;
}

/** Client-only: set Lax cookies for middleware + API client */
export function setAuthCookies(access: string, refresh: string) {
  const accessMax = 60 * 15;
  const refreshMax = 60 * 60 * 24 * 7;
  const base = "; path=/; SameSite=Lax";
  document.cookie = `${AT}=${encodeURIComponent(access)}; max-age=${accessMax}${base}`;
  document.cookie = `${RT}=${encodeURIComponent(refresh)}; max-age=${refreshMax}${base}`;
}

export function clearAuthCookies() {
  const base = "; path=/; max-age=0";
  document.cookie = `${AT}=${base}`;
  document.cookie = `${RT}=${base}`;
}
