import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { authApi, setCsrfToken, type AuthSession } from "./authApi";
import type { AuthUser } from "./permissions";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const acceptSession = useCallback((session: AuthSession) => {
    setCsrfToken(session.csrf_token);
    sessionStorage.setItem("urbanlens_session_expires", String(session.expires_at));
    setUser(session.user);
    setError(null);
  }, []);

  useEffect(() => {
    let active = true;
    void authApi.session().then((session) => {
      if (active) acceptSession(session);
    }).catch((cause: unknown) => {
      setCsrfToken("");
      if (active) {
        setUser(null);
        if (cause instanceof Error && !cause.message.includes("Authentication required")) setError(cause.message);
      }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [acceptSession]);

  useEffect(() => {
    const expire = () => {
      setCsrfToken(""); sessionStorage.removeItem("urbanlens_session_expires");
      setUser(null); setError("Your session expired. Please sign in again.");
    };
    window.addEventListener("urbanlens:auth-expired", expire);
    return () => window.removeEventListener("urbanlens:auth-expired", expire);
  }, []);

  useEffect(() => {
    if (!user) return;
    const timer = window.setTimeout(() => {
      setCsrfToken(""); setUser(null); setError("Your session expired. Please sign in again.");
    }, Math.max(0, Number(sessionStorage.getItem("urbanlens_session_expires") ?? 0) * 1000 - Date.now()));
    return () => window.clearTimeout(timer);
  }, [user]);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    const session = await authApi.login(email, password);
    acceptSession(session);
    return session.user;
  }, [acceptSession]);

  const logout = useCallback(async () => {
    await authApi.logout();
    setCsrfToken(""); sessionStorage.removeItem("urbanlens_session_expires");
    setUser(null); setError(null);
  }, []);

  const value = useMemo(() => ({ user, loading, error, login, logout }), [user, loading, error, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
