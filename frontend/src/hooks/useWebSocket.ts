import { useEffect, useRef, useState, useCallback } from "react";

interface UseWebSocketOptions {
  channel?: string;
  onMessage?: (data: any) => void;
  autoReconnect?: boolean;
  /** JWT or API key token. When provided, sent as first message for auth. */
  token?: string | null;
}

/**
 * WebSocket hook with first-message authentication.
 *
 * Phase 5: Query-string token auth (?token=...) has been removed server-side
 * to prevent token leakage. When a token is provided, it is sent as the
 * first message: {"action": "auth", "token": "..."}.
 *
 * In dev mode (auth_enabled=False server-side), the server accepts
 * connections without auth and sends {"type": "auth_ok", "dev_mode": true}.
 */
export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { channel, onMessage, autoReconnect = true, token = null } = options;
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/api/v1/ws`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      // Send auth as first message if token is available
      if (token) {
        ws.send(JSON.stringify({ action: "auth", token }));
      }
      // Subscribe to channel (server accepts immediately in dev mode,
      // or after auth_ok in production mode)
      if (channel) {
        ws.send(JSON.stringify({ action: "subscribe", channel }));
      }
      setConnected(true);
      reconnectAttemptsRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "subscribed") return; // ack
        if (data.type === "auth_ok") return; // auth confirmed
        if (data.type === "error") {
          console.error("WebSocket error:", data.message);
          return;
        }
        setMessages((prev) => [...prev.slice(-99), data]);
        onMessage?.(data);
      } catch {
        /* ignore parse errors */
      }
    };

    ws.onclose = () => {
      setConnected(false);
      if (autoReconnect) {
        const delay = Math.min(1000 * 2 ** reconnectAttemptsRef.current, 30000);
        reconnectTimeoutRef.current = window.setTimeout(() => {
          reconnectAttemptsRef.current++;
          connect();
        }, delay);
      }
    };
  }, [channel, onMessage, autoReconnect, token]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect]);

  const send = useCallback((data: any) => {
    wsRef.current?.send(JSON.stringify(data));
  }, []);

  return { connected, messages, send };
}
