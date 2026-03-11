# Backtester

Config-driven, deterministic backtesting engine for options and futures.

The backtester loads local market data, runs a strategy, simulates fills through a simplified broker model, updates portfolio state through the shared `portfolio/` package, and writes CSV/JSON/HTML artifacts for inspection.

Strategizer runs **in-process** here. No HTTP service is required.

## Run Backtests

The tracked example configs in `configs/` are fixture-backed and reproducible from the repo checkout.

| Config | Strategy | Source | Description |
|--------|----------|--------|-------------|
| `configs/buy_and_hold_example.yaml` | `buy_and_hold` | `strategizer/` | Buy one option on the first step and hold |
| `configs/covered_call_example.yaml` | `covered_call` | `strategizer/` | Buy an option and exit on step 3 |
| `configs/buy_and_hold_underlying_example.yaml` | `buy_and_hold_underlying` | `strategizer/` | Buy SPY shares and hold through the run |
| `configs/orb_5m_example.yaml` | `orb_5m` | `strategizer/` | Opening-range breakout example on ESH1 using 1m bars |

`orb_5m` retains its historic name, but the current implementation runs on `1m` bars.

```bash
python -m src.runner configs/orb_5m_example.yaml
```

All runs write artifacts beneath `runs/`:

- `equity_curve.csv`
- `orders.csv`
- `fills.csv`
- `trades.csv`
- `summary.json`
- `run_manifest.json`
- `report.html`

## Available Strategies

| Strategy | What it demonstrates |
|----------|----------------------|
| `buy_and_hold` | Option entry and hold-to-end behavior |
| `covered_call` | Multi-step option flow with deterministic exit timing |
| `buy_and_hold_underlying` | Underlying/equity path with multiplier `1.0` |
| `orb_5m` | Futures breakout logic, tick normalization, and futures specs |
| `trend_entry_trailing_stop` | Broker-managed trailing-stop exit |
| `trend_follow_risk_sized` | Portfolio-aware position sizing from account equity and stop distance |

## Showcase Run

The committed showcase artifact lives in `runs/showcase/`.

It was generated from `configs/orb_5m_example.yaml` using fixture data:

- Strategy: `orb_5m`
- Instrument: `ESH1` future
- Window: `2026-01-02T14:31:00Z` to `2026-01-02T14:37:00Z`
- Result: one breakout entry at `5410.25`, marked at `5412.0` by run end

Why this run is representative:

- it shows the config -> data -> strategy -> broker -> portfolio -> report flow end to end
- it exercises futures contract metadata and tick-size normalization
- it produces a non-flat equity curve with a deterministic, explainable entry

Why `summary.json` shows `num_trades: 0`:

- the position remains open at run end, so there is no closed trade
- the open position still appears in `trades.csv` and in the HTML report as a marked open trade

## Modeling Assumptions

### Modeled today

- Option fills use quote-aware behavior: buy at ask, sell at bid when both sides are available
- When only a midpoint is available, the fill model applies a synthetic spread fallback
- Futures fills are normalized to the configured tick size
- Fees are modeled through the broker fee model
- Portfolio state tracks cash, positions, realized P&L, unrealized P&L, equity, and invariant checks
- Reports persist config snapshots, provider diagnostics, and a git hash for reproducibility

### Still simplified

- Underlying market and limit-style fills use the same bar close plus synthetic spread rather than a fuller intrabar execution model
- Limit-order realism is intentionally limited
- There are no partial fills or market-impact assumptions
- Buying-power logic is conservative but not broker-grade margin modeling
- Short borrow, financing, and other live-broker details are not modeled

This is deliberate: the project is meant to be an honest backtesting and strategy-evaluation demo, not a full brokerage simulator.

## Market Data

For real-data runs, the market-data CLI can fetch and export bars and option quotes.

| Command | Description |
|---------|-------------|
| `python -m src.marketdata.cli fetch` | Fetch OHLCV from Massive/Polygon and cache it locally |
| `python -m src.marketdata.cli export` | Export cached bars to Parquet or CSV |
| `python -m src.marketdata.cli fetch-options` | Fetch option chain metadata and quotes |

Examples:

```bash
python -m src.marketdata.cli fetch --provider massive --symbol SPY --interval 1d --start 2026-01-01 --end 2026-02-01
python -m src.marketdata.cli export --provider massive --symbol SPY --interval 1d --start 2026-01-01 --end 2026-02-01 --split month --out ./data/exports/spy
python -m src.marketdata.cli fetch-options --underlying SPY --start 2026-02-01 --end 2026-03-31
```

## Setup

```bash
pip install -e .
cp .env.example .env
```

Set `MASSIVE_API_KEY` or `POLYGON_API_KEY` in `.env` only if you want to fetch fresh market data. The tracked example configs do not require API keys.

## Tests

```bash
pytest
```

Useful variants:

- `pytest -m "not network"` for CI-safe runs
- `pytest tests/integration` for project-level integration coverage
- `pytest tests/integration -m network` for network-only data-provider tests
