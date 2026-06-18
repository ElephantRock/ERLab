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

// Note: JWT injection into API calls is handled centrally by
// buildAuthHeaders() in client.ts — no global fetch patch needed.

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
    // Always try getMe() — if auth is disabled on the backend,
    // it returns a dev user even without a token.
    // If auth is enabled and there's no token, it 401s → login page.
    getMe()
      .then((u) => setUser(u))
      .catch(() => {
        // No valid session — token may be expired or auth is enforced
        if (token) clearToken();
      })
      .finally(() => setLoading(false));
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
