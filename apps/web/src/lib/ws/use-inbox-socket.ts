"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { InboxEvent } from "@javobai/shared-types";
import { WS_URL } from "@/lib/config";

type EventHandler = (event: InboxEvent) => void;

/**
 * Phase 8 realtime transport for the inbox. Exchanges a one-time ticket
 * (minted through the normal cookie-authed proxy at POST /auth/ws-ticket)
 * for a direct websocket connection to the API — see javobai/ws/router.py
 * for why this can't just go through the usual /api/proxy route.
 *
 * Handles reconnects on its own: a closed/broken socket triggers a fresh
 * ticket fetch + reconnect after a short delay.
 */
export function useInboxSocket(onEvent: EventHandler) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const onEventRef = useRef(onEvent);
  const mountedRef = useRef(true);
  onEventRef.current = onEvent;

  const connect = useCallback(async () => {
    if (!mountedRef.current) return;
    try {
      const res = await fetch("/api/proxy/auth/ws-ticket", { method: "POST" });
      if (!res.ok || !mountedRef.current) return;
      const { ticket } = (await res.json()) as { ticket: string };

      const ws = new WebSocket(`${WS_URL}?ticket=${encodeURIComponent(ticket)}`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (mountedRef.current) setConnected(true);
      };
      ws.onclose = () => {
        if (!mountedRef.current) return;
        setConnected(false);
        wsRef.current = null;
        setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (event: MessageEvent<string>) => {
        try {
          const data = JSON.parse(event.data) as InboxEvent;
          onEventRef.current(data);
        } catch {
          // ignore malformed frames
        }
      };
    } catch {
      if (mountedRef.current) setTimeout(connect, 5000);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);

  const sendPresence = useCallback((conversationId: string, joined: boolean) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(
        JSON.stringify({
          type: joined ? "presence.join" : "presence.leave",
          conversation_id: conversationId,
        })
      );
    }
  }, []);

  return { connected, sendPresence };
}
