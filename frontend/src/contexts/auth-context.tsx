/** Auth context — provides user state and token management (BATCH-28). */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import {
  login as apiLogin,
  register as apiRegister,
  getMe,
  type AuthUser,
} from "@/api/auth";

// ── Token Storage ──────────────────────────────────────────────────

const TOKEN_KEY = "erock_jwt_token";

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ── Intercept apiFetch to include JWT token ────────────────────────

// Monkey-patch apiFetch to add Authorization header when JWT token exists.
// We do this at module level so it applies globally.
const originalFetch = window.fetch;
window.fetch = function patchedFetch(input, init) {
  const token = getToken();
  if (token && typeof input === "string" && input.includes("/api/v1/")) {
    const headers = new Headers(init?.headers);
    // Don't override if already set
    if (!headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    init = { ...init, headers };
  }
  return originalFetch.call(this, input, init);
};

// ── Context Types ──────────────────────────────────────────────────

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// ── Provider ───────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore session on mount
  useEffect(() => {
    const token = getToken();
    if (token) {
      getMe()
        .then((u) => setUser(u))
        .catch(() => {
          // Token expired or invalid
          clearToken();
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const handleLogin = useCallback(async (username: string, password: string) => {
    const resp = await apiLogin(username, password);
    setToken(resp.token);
    setUser(resp.user);
  }, []);

  const handleRegister = useCallback(
    async (username: string, email: string, password: string) => {
      const resp = await apiRegister(username, email, password);
      setToken(resp.token);
      setUser(resp.user);
    },
    [],
  );

  const handleLogout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login: handleLogin,
        register: handleRegister,
        logout: handleLogout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ── Hook ───────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
