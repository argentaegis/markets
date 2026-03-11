import { useEffect, useRef, useState } from 'react';
import type { Quote, Bar } from '../types/market.ts';
import type { WsMessage } from '../types/ws.ts';
import { fetchSnapshot } from '../api/snapshot.ts';

export interface MarketData {
  quotes: Record<string, Quote>;
  bars: Record<string, Record<string, Bar[]>>;
}

export function useMarketData(
  subscribe: (handler: (msg: WsMessage) => void) => () => void,
  reconnectCount: number,
): MarketData {
  const [quotes, setQuotes] = useState<Record<string, Quote>>({});
  const [bars, setBars] = useState<Record<string, Record<string, Bar[]>>>({});
  const loadedRef = useRef(false);

  useEffect(() => {
    if (!loadedRef.current || reconnectCount > 0) {
      loadedRef.current = true;
      fetchSnapshot()
        .then(snap => { setQuotes(snap.quotes); setBars(snap.bars); })
        .catch(() => {});
    }
  }, [reconnectCount]);

  useEffect(() => {
    return subscribe((msg) => {
      if (msg.type === 'quote_update') {
        const q = msg.data;
        setQuotes(prev => ({ ...prev, [q.symbol]: q }));
      } else if (msg.type === 'bar_update') {
        const b = msg.data;
        setBars(prev => {
          const symBars = { ...(prev[b.symbol] ?? {}) };
          const tfBars = [...(symBars[b.timeframe] ?? []), b];
          if (tfBars.length > 500) tfBars.shift();
          symBars[b.timeframe] = tfBars;
          return { ...prev, [b.symbol]: symBars };
        });
      }
    });
  }, [subscribe]);

  return { quotes, bars };
}
