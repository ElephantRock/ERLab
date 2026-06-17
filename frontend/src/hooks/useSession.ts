import { useState, useCallback } from "react";

const SESSION_KEY = "erock_session_id";

/**
 * useSession — centralizes session_id management.
 *
 * Persists to localStorage so the session survives page navigation.
 * Previously this was ad-hoc local state in pipeline-new.tsx with
 * prop drilling through RunConfigForm.
 */
export function useSession() {
  const [sessionId, setSessionIdState] = useState<string>(() => {
    return localStorage.getItem(SESSION_KEY) || "";
  });

  const setSessionId = useCallback((value: string) => {
    setSessionIdState(value);
    if (value) {
      localStorage.setItem(SESSION_KEY, value);
    } else {
      localStorage.removeItem(SESSION_KEY);
    }
  }, []);

  const clearSession = useCallback(() => {
    setSessionIdState("");
    localStorage.removeItem(SESSION_KEY);
  }, []);

  return { sessionId, setSessionId, clearSession };
}
