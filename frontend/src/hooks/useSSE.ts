import { useEffect, useRef, useState } from "react";
import { sseFetch } from "@/api/client";

interface UseSSEOptions<T> {
  onEvent: (data: T) => void;
  enabled?: boolean;
}

export function useSSE<T>(path: string, options: UseSSEOptions<T>) {
  const { onEvent, enabled = true } = options;
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!enabled) return;

    let retries = 0;
    const maxRetries = 5;
    let controller: AbortController | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      controller = sseFetch(path, {
        onOpen: () => {
          retries = 0;
          setIsConnected(true);
          setError(null);
        },
        onEvent: (raw) => {
          try {
            const data = JSON.parse(raw) as T;
            onEventRef.current(data);
          } catch {
            // ignore parse errors
          }
        },
        onError: (err) => {
          setIsConnected(false);
          if (retries < maxRetries) {
            retries++;
            const delay = Math.min(1000 * Math.pow(2, retries), 30_000);
            retryTimer = setTimeout(connect, delay);
          } else {
            setError(new Error("SSE connection failed after max retries: " + err.message));
          }
        },
      });
    }

    connect();

    return () => {
      controller?.abort();
      if (retryTimer) clearTimeout(retryTimer);
      setIsConnected(false);
    };
  }, [path, enabled]);

  return { isConnected, error };
}

export function isStageProgress(
  data: unknown,
): data is { stage: string; index: number; total: number; elapsed: number } {
  return (
    typeof data === "object" &&
    data !== null &&
    "stage" in data &&
    typeof (data as Record<string, unknown>).stage === "string"
  );
}

export function isDone(data: unknown): data is { done: true } {
  return typeof data === "object" && data !== null && "done" in data;
}
