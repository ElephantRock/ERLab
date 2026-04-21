import { useEffect, useRef, useState } from "react";
import { sseUrl } from "@/api/client";

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

    const url = sseUrl(path);
    let retries = 0;
    const maxRetries = 5;
    let es: EventSource | null = null;

    function connect() {
      es = new EventSource(url);

      es.onopen = () => {
        retries = 0;
        setIsConnected(true);
        setError(null);
      };

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as T;
          onEventRef.current(data);
        } catch {
          // ignore parse errors
        }
      };

      es.onerror = () => {
        setIsConnected(false);
        es?.close();

        if (retries < maxRetries) {
          retries++;
          const delay = Math.min(1000 * Math.pow(2, retries), 30_000);
          setTimeout(connect, delay);
        } else {
          setError(new Error("SSE connection failed after max retries"));
        }
      };
    }

    connect();

    return () => {
      es?.close();
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
