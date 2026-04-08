"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { apiGet, apiPost, ApiRequestError } from "@/lib/api/client";
import type { TokenPair, UserPublic } from "@/lib/api/types";
import { clearAuthCookies, getAccessToken, setAuthCookies } from "@/lib/auth/cookies";

type AuthCtx = {
  user: UserPublic | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshUser = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const data = await apiGet<UserPublic>("/auth/me");
      setUser(data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    const data = await apiPost<{ user: UserPublic; tokens: TokenPair }>("/auth/login", {
      email,
      password,
    });
    setAuthCookies(data.tokens.access_token, data.tokens.refresh_token);
    setUser(data.user);
  }, []);

  const logout = useCallback(() => {
    clearAuthCookies();
    setUser(null);
  }, []);

  const loginWrapped = useCallback(
    async (email: string, password: string) => {
      try {
        await login(email, password);
      } catch (e) {
        const msg = e instanceof ApiRequestError ? e.message : "Login failed";
        setError(msg);
        throw e;
      }
    },
    [login],
  );

  const value = useMemo<AuthCtx>(
    () => ({
      user,
      loading,
      error,
      login: loginWrapped,
      logout,
      refreshUser,
    }),
    [user, loading, error, loginWrapped, logout, refreshUser],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}
