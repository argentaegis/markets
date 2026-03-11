import type { Quote, Bar } from './market.ts';
import type { TradeCandidate } from './candidate.ts';

export type WsMessage =
  | { type: "quote_update"; data: Quote }
  | { type: "bar_update"; data: Bar }
  | { type: "candidates_update"; data: TradeCandidate[] };
