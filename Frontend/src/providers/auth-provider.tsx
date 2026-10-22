"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, use, useCallback, useEffect, useMemo, useState } from "react";

import {
  applySession,
  clearToken,
  onSession,
  refreshAccessToken,
  setOnAuthLost,
  type TokenResponse,
  type User,
} from "@/lib/api/auth";
import { api } from "@/lib/api/client";
import { resetStreams } from "@/lib/chat/stream-store";
import { toastError, unwrap } from "@/lib/api/errors";
import type { components } from "@/lib/api/schema";

export type AuthStatus = "loading" | "authenticated" | "anonymous";
export type RegisterInput = components["schemas"]["RegisterRequest"];

type AuthContextValue = {
  user: User | null;
  status: AuthStatus;
  /** Resolves to the session (check `must_change_password`); throws ApiError on bad credentials. */
  login: (email: string, password: string) => Promise<TokenResponse>;
  register: (input: RegisterInput) => Promise<TokenResponse>;
  logout: () => Promise<void>;
  /** Signs out every other session; this device gets a fresh session (must_change_password off). */
  changePassword: (currentPassword: string, newPassword: string) => Promise<TokenResponse>;
  /** Re-read the current user (after a profile or password change). */
  refreshUser: () => Promise<User>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const becomeAnonymous = useCallback(() => {
    clearToken();
    resetStreams(); // stop any chat reply in progress
    setUser(null);
    setStatus("anonymous");
    queryClient.clear(); // never show one user's cached data to the next
  }, [queryClient]);

  useEffect(() => {
    // Every new session (login, register, any background refresh) carries the fresh user.
    const unsubscribe = onSession((session) => {
      setUser(session.user);
      setStatus("authenticated");
    });
    setOnAuthLost(becomeAnonymous);

    // Restore the session from the httpOnly refresh cookie. refreshAccessToken() is
    // single-flight, so React's dev double-mount still sends only one refresh.
    let cancelled = false;
    refreshAccessToken()
      .then((session) => {
        if (!session && !cancelled) becomeAnonymous();
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        becomeAnonymous();
        toastError(error); // backend unreachable
      });

    return () => {
      cancelled = true;
      unsubscribe();
      setOnAuthLost(null);
    };
  }, [becomeAnonymous]);

  const login = useCallback(
    async (email: string, password: string) => {
      const session = unwrap(await api.POST("/api/v1/auth/login", { body: { email, password } }));
      queryClient.clear();
      applySession(session);
      return session;
    },
    [queryClient],
  );

  const register = useCallback(
    async (input: RegisterInput) => {
      const session = unwrap(await api.POST("/api/v1/auth/register", { body: input }));
      queryClient.clear();
      applySession(session);
      return session;
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    try {
      await api.POST("/api/v1/auth/logout"); // revokes the refresh token, clears the cookie
    } catch {
      // offline: still forget the session locally
    }
    becomeAnonymous();
  }, [becomeAnonymous]);

  const changePassword = useCallback(async (currentPassword: string, newPassword: string) => {
    const session = unwrap(
      await api.POST("/api/v1/users/me/password", {
        body: { current_password: currentPassword, new_password: newPassword },
      }),
    );
    applySession(session);
    return session;
  }, []);

  const refreshUser = useCallback(async () => {
    const me = unwrap(await api.GET("/api/v1/users/me"));
    setUser(me);
    return me;
  }, []);

  const value = useMemo(
    () => ({ user, status, login, register, logout, changePassword, refreshUser }),
    [user, status, login, register, logout, changePassword, refreshUser],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthContextValue {
  const context = use(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
