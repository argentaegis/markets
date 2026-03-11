import { useCallback, useEffect, useRef, useState } from 'react';
import type { TradeCandidate } from '../types/candidate.ts';
import type { WsMessage } from '../types/ws.ts';
import { fetchSnapshot } from '../api/snapshot.ts';

export interface UseCandidatesResult {
  candidates: TradeCandidate[];
  selectedId: string | null;
  selectedCandidate: TradeCandidate | null;
  select: (id: string | null) => void;
}

export function useCandidates(
  subscribe: (handler: (msg: WsMessage) => void) => () => void,
  reconnectCount: number,
): UseCandidatesResult {
  const [candidates, setCandidates] = useState<TradeCandidate[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const loadedRef = useRef(false);

  useEffect(() => {
    if (!loadedRef.current || reconnectCount > 0) {
      loadedRef.current = true;
      fetchSnapshot()
        .then(snap => { setCandidates(snap.candidates); })
        .catch(() => {});
    }
  }, [reconnectCount]);

  useEffect(() => {
    return subscribe((msg) => {
      if (msg.type === 'candidates_update') {
        setCandidates(prev => {
          const newIds = new Set(msg.data.map(c => c.id));
          const kept = prev.filter(c => !newIds.has(c.id));
          return [...kept, ...msg.data];
        });
      }
    });
  }, [subscribe]);

  const select = useCallback((id: string | null) => {
    setSelectedId(prev => prev === id ? null : id);
  }, []);

  const selectedCandidate = candidates.find(c => c.id === selectedId) ?? null;

  return { candidates, selectedId, selectedCandidate, select };
}
