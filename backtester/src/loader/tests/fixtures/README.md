# Test Fixtures

Deterministic fixture data for M1 DataProvider tests. No production data.

## Underlying bars
- `underlying/SPY_1d.parquet` — 1d bars (standard); also `.csv` for legacy
- `underlying/SPY_1h.parquet`, `underlying/SPY_1m.parquet`
- `underlying/ESH1_1m.parquet` — 6 bars for ORB: OR = bars 1–5 (9:31–9:35 ET), LONG breakout at 9:36 ET
- `underlying_trailing/ESH1_1m.parquet` — 3 bars for trend_entry_trailing_stop: bar 2 low=close triggers MA cross, bar 3 triggers trailing exit
- ts = bar close UTC, min ts 2026-01-02 21:00, max ts 2026-01-08 21:00

### Regenerating ESH1 fixtures (golden scenario)
1m: 6 bars, first 5 = OR (high 5410, low 5405), bar 6 close 5412 triggers breakout at 5410.25.

## Options metadata
- `options/metadata/index.csv` — underlying, expiry, strike, right, contract_id, multiplier

## Options quotes
- `options/quotes.parquet` — consolidated (contract_id, quote_ts, bid, ask); preferred for bulk data
- `options/quotes/{contract_id}.csv` — per-contract quote_ts, bid, ask; used by fixtures
- SPY|2026-01-17|C|480|100: quotes 14:30–14:35 (includes crossed market at 14:33)
- SPY|2026-03-20|C|485|100: quotes 14:30, 14:35, 15:00
- SPY|2026-01-10|C|490|10: single stale quote 2025-12-01
