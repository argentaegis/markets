import type { Quote, Bar } from './market.ts';
import type { TradeCandidate } from './candidate.ts';

export interface SnapshotResponse {
  quotes: Record<string, Quote>;
  bars: Record<string, Record<string, Bar[]>>;
  candidates: TradeCandidate[];
}
