export type DataQuality = "OK" | "STALE" | "MISSING" | "PARTIAL";

export interface Quote {
  symbol: string;
  bid: number;
  ask: number;
  last: number;
  bid_size: number;
  ask_size: number;
  volume: number;
  timestamp: string;
  source: string;
  quality: DataQuality;
}

export interface Bar {
  symbol: string;
  timeframe: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  timestamp: string;
  source: string;
  quality: DataQuality;
}
