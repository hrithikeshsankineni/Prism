import { useEffect, useRef, useCallback, useState } from "react";
import useSessionStore from "../store/sessionStore";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

export default function useWebSocket() {
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const [isConnected, setIsConnected] = useState(false);

  const sessionId = useSessionStore((s) => s.sessionId);
  const lastSequence = useSessionStore((s) => s.lastSequence);
  const handleEvent = useSessionStore((s) => s.handleEvent);

  const connect = useCallback(
    (sid, query) => {
      if (wsRef.current) {
        wsRef.current.close();
      }

      const ws = new WebSocket(`${WS_BASE}/ws/${sid}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        // Send the query as first message
        ws.send(JSON.stringify({ query }));
      };

      ws.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data);
          if (event.error) {
            console.error("Server error:", event.error);
            return;
          }
          handleEvent(event);
        } catch (err) {
          console.error("Failed to parse WS message:", err);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;
      };

      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
      };
    },
    [handleEvent]
  );

  const disconnect = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => disconnect();
  }, [disconnect]);

  return { isConnected, connect, disconnect };
}
