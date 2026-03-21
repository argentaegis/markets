# Backtester

Config-driven, deterministic backtesting engine for options and futures.

The backtester loads local market data, runs a strategy, simulates fills through a simplified broker model, updates portfolio state through the shared `portfolio/` package, and writes CSV/JSON/HTML artifacts for inspection.

Strategizer runs **in-process** here. No HTTP service is required.

## Quick start

**No data setup (works on fresh clone):**

```bash
make backtester-run BACKTESTER_CONFIG=configs/buy_and_hold_example.yaml
```

Or from `backtester/`:

```bash
python -m src.runner configs/buy_and_hold_example.yaml
```

Artifacts appear in repo-root `runs/<timestamp>_*/`. The **flagship TAA** requires catalog data; see the [Showcase Run](#showcase-run) section.

## Run Backtests

| Config | Strategy | Data | Description |
|--------|----------|------|-------------|
| `configs/tactical_asset_allocation_example.yaml` | `tactical_asset_allocation` | Catalog | **Flagship.** Faber-style TAA across 6 ETFs; closed trades, Sharpe, CAGR, turnover |
| `configs/trend_follow_risk_sized_example.yaml` | `trend_follow_risk_sized` | Fixture | Portfolio-aware sizing, trailing stop |
| `configs/buy_and_hold_example.yaml` | `buy_and_hold` | Fixture | Buy one option on the first step and hold |
| `configs/orb_5m_example.yaml` | `orb_5m` | Fixture | Mechanics example: opening-range breakout on ESH1 |
| `configs/buy_and_hold_underlying_example.yaml` | `buy_and_hold_underlying` | Fixture | Buy SPY shares and hold through the run |
| `configs/covered_call_example.yaml` | `covered_call` | Catalog | True covered call, 5yr; needs `data/catalog.yaml` and exports |
| `configs/covered_call_example_quick.yaml` | `covered_call` | Catalog | Same, 3 months for fast iteration (~60 steps) |
| `configs/buy_and_hold_underlying_spy_benchmark.yaml` | `buy_and_hold_underlying` | Catalog | SPY buy-and-hold benchmark for TAA case study (same window, broker) |

**Fixture** = uses `data_provider` paths to repo fixtures; runs on fresh clone. **Catalog** = uses `data/catalog.yaml`; requires `data/exports/` for symbols (fetch via market-data CLI or provide your own).

`orb_5m` retains its historic name, but the current implementation runs on `1m` bars.

All runs write artifacts beneath repo-root `runs/`:

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
| `tactical_asset_allocation` | Faber-style trend filter, monthly rebalance, multi-ETF (Sharpe, CAGR, turnover) |
| `trend_entry_trailing_stop` | Broker-managed trailing-stop exit |
| `trend_follow_risk_sized` | Portfolio-aware position sizing from account equity and stop distance |

## Showcase Run

The committed showcase lives in repo-root `runs/showcase/`.

### Primary: tactical_asset_allocation (flagship)

Generated from `configs/tactical_asset_allocation_example.yaml` using catalog data:

- **Strategy:** `tactical_asset_allocation` — Faber-style trend filter, 200-day SMA, monthly rebalance
- **Instruments:** SPY, QQQ, IWM, TLT, GLD, USO (6 ETFs)
- **Window:** 2019-03-01 to 2026-03-10 (~7 years, 1765 steps)
- **Result:** 192 closed trades, Sharpe 0.73, CAGR ~9.0%, turnover 21.4

Why this is the primary showcase:

- Multi-asset TAA with closed trades, non-null Sharpe, CAGR, turnover, and drawdown
- End-to-end flow: config → data → strategy → broker → portfolio → report
- Case study: see [`runs/showcase/CASE_STUDY.md`](../runs/showcase/CASE_STUDY.md)

### Analytics showcase (TAA)

For runs with enough data (≥20 return observations, ≥1 day), `summary.json` and the HTML report include risk-adjusted metrics.

#### Metrics

- **Sharpe** (annualized) — Mean divided by standard deviation of step returns, scaled by `sqrt(N)` where N is periods per year from `timeframe_base` (1d→252, 1m→252×390). Null if fewer than 20 observations or zero std.
- **CAGR** — Compound annual growth rate: `(final_equity / initial_cash)^(1/years) - 1`. Null if run spans less than one day.
- **Turnover** — `sum(|fill_notional|) / mean(equity)`; total traded notional divided by average equity over the run.
- **Avg Win / Avg Loss** — Mean realized P&L of winning trades (P&L > 0) and losing trades (P&L ≤ 0) respectively. Null if no trades in that category.
- **Profit Factor** — `sum(winning P&L) / abs(sum(losing P&L))`; values above 1.0 indicate a net-profitable strategy. Null if no winners or no losers.
- **Expectancy** — `win_rate × avg_win + (1 − win_rate) × avg_loss`; expected P&L per trade. Null if no closed trades.
- **Reward / Risk** — `avg_win / abs(avg_loss)`; ratio of average winner size to average loser size. Null if no losers.
- **Avg Trade Duration** — Mean number of bars between entry fill and exit fill across closed trades. Based on `timeframe_base`.

The flagship `tactical_asset_allocation` showcase demonstrates Sharpe, CAGR, and turnover. It uses `broker: ibkr_equity_spread` (10 bps equity) and `fill_timing: next_bar_open` (the default since Plan 278) for execution realism.

## Modeling Assumptions

### Modeled today

- Option fills use quote-aware behavior: buy at ask, sell at bid when both sides are available
- When only a midpoint is available, the fill model applies a synthetic spread fallback
- Futures fills are normalized to the configured tick size
- **Fill timing**: configurable `fill_timing` — `next_bar_open` (default, Plan 278) or `same_bar_close`. With `next_bar_open`, the strategy decides on bar N's close and fills at bar N+1's open, modeling realistic decision-to-execution latency. Set `fill_timing: same_bar_close` only for strategies where decision and execution are genuinely simultaneous.
- **Broker fee schedules**: config selects a broker by name; fees differ by instrument type (equity, option, future). Built-in brokers: `ibkr`, `ibkr_equity_spread`, `tdameritrade`, `schwab`, `zero`. See `src/broker/fee_schedules.py`.
- Portfolio state tracks cash, positions, realized P&L, unrealized P&L, equity, and invariant checks
- Reports persist config snapshots, provider diagnostics, and a git hash for reproducibility

### Still simplified

- Default fill timing is `next_bar_open`; `same_bar_close` is opt-in for specific use cases
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
