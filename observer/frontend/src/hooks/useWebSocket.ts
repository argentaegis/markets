import { useCallback, useEffect, useRef, useState } from 'react';
import type { WsMessage } from '../types/ws.ts';
import type { ConnectionStatus } from '../components/StatusBar/StatusBar.tsx';

const INITIAL_DELAY_MS = 1_000;
const MAX_DELAY_MS = 30_000;

type MessageHandler = (msg: WsMessage) => void;

export interface UseWebSocketResult {
  status: ConnectionStatus;
  reconnectCount: number;
  lastMessageAt: number;
  subscribe: (handler: MessageHandler) => () => void;
}

export function useWebSocket(): UseWebSocketResult {
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [reconnectCount, setReconnectCount] = useState(0);
  const [lastMessageAt, setLastMessageAt] = useState(0);

  const delayRef = useRef(INITIAL_DELAY_MS);
  const mountedRef = useRef(true);
  const wsRef = useRef<WebSocket | null>(null);
  const handlersRef = useRef<Set<MessageHandler>>(new Set());
  const connectFnRef = useRef<() => void>(() => {});

  const subscribe = useCallback((handler: MessageHandler) => {
    handlersRef.current.add(handler);
    return () => { handlersRef.current.delete(handler); };
  }, []);

  useEffect(() => {
    mountedRef.current = true;

    const doConnect = () => {
      if (!mountedRef.current) return;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = `${protocol}//${window.location.host}/ws`;
      const ws = new WebSocket(url);
      wsRef.current = ws;
      setStatus('connecting');

      ws.onopen = () => {
        if (!mountedRef.current) return;
        delayRef.current = INITIAL_DELAY_MS;
        setStatus('connected');
        setReconnectCount(c => c + 1);
      };

      ws.onmessage = (event: MessageEvent) => {
        if (!mountedRef.current) return;
        try {
          const msg = JSON.parse(event.data as string) as WsMessage;
          setLastMessageAt(c => c + 1);
          for (const handler of handlersRef.current) {
            handler(msg);
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setStatus('disconnected');
        const delay = delayRef.current;
        delayRef.current = Math.min(delay * 2, MAX_DELAY_MS);
        setTimeout(() => connectFnRef.current(), delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connectFnRef.current = doConnect;
    doConnect();

    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
    };
  }, []);

  return { status, reconnectCount, lastMessageAt, subscribe };
}
