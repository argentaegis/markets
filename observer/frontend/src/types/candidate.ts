export type Direction = "LONG" | "SHORT";
export type EntryType = "MARKET" | "LIMIT" | "STOP";

export interface TradeCandidate {
  id: string;
  symbol: string;
  strategy: string;
  direction: Direction;
  entry_type: EntryType;
  entry_price: number;
  stop_price: number;
  targets: number[];
  score: number;
  explain: string[];
  valid_until: string;
  tags: Record<string, string>;
  created_at: string;
}
