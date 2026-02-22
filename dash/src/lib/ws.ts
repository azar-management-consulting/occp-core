"use client";

import { useEffect, useRef, useState, useCallback } from "react";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/api/v1";

export interface PipelineEvent {
  event: string;
  task_id: string;
  status?: string;
  success?: boolean;
  reason?: string;
  timestamp: string;
}

export function usePipelineWS(taskId: string | null) {
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (!taskId) return;
    const ws = new WebSocket(`${WS_BASE}/ws/pipeline/${taskId}`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => {
      try {
        const evt: PipelineEvent = JSON.parse(e.data);
        setEvents((prev) => [...prev, evt]);
      } catch {}
    };
  }, [taskId]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  return { events, connected, clear: () => setEvents([]) };
}
