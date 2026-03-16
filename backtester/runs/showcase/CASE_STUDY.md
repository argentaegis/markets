# Flagship Case Study — Tactical Asset Allocation

This is the primary showcase run for the backtester. It demonstrates a Faber-style tactical asset allocation strategy across six ETFs with closed trades, multi-year CAGR, Sharpe, and turnover.

## Strategy

`tactical_asset_allocation`: hold each ETF when its close is above a 200-day SMA, otherwise cash. Monthly rebalance with equal weight across active positions. Uses next-bar-open execution and explicit equity trading costs (10 bps).

## Run Parameters

- **Instruments:** SPY, QQQ, IWM, TLT, GLD, USO (6 ETFs)
- **Config:** `configs/tactical_asset_allocation_example.yaml`
- **Data:** Catalog (data/exports/ for each symbol)
- **Window:** 2019-03-01 to 2026-03-10 (~7 years, 1765 daily steps)
- **Broker:** `ibkr_equity_spread` (10 bps equity spread/slippage)
- **Fill timing:** `next_bar_open` (avoids execution lookahead)

## Key Metrics

| Metric | Value |
|--------|-------|
| Initial cash | $100,000 |
| Final equity | ~$183,131 |
| Total return | ~83.1% |
| Max drawdown | ~$39,279 (24.4%) |
| Closed trades | 192 (132 winners, 60 losers) |
| Win rate | ~68.8% |
| Sharpe | 0.73 (annualized) |
| CAGR | ~9.0% |
| Turnover | 21.38 |

## What This Run Demonstrates

- Multi-asset, multi-year TAA: Faber-style trend filter across 6 ETFs
- End-to-end pipeline: config-driven run, catalog data, strategy signals, next-bar-open fills, portfolio accounting, CSV/JSON/HTML artifacts
- Risk-adjusted reporting: Sharpe, CAGR, turnover from step returns and fill notional
- Execution realism: 10 bps equity costs, `next_bar_open` fill timing

## Reproducing This Run

Requires catalog data: `backtester/data/catalog.yaml` and `backtester/data/exports/` for SPY, QQQ, IWM, TLT, GLD, USO. Fetch via market-data CLI or provide your own.

```bash
make backtester-run BACKTESTER_CONFIG=configs/tactical_asset_allocation_example.yaml
```

## Known Simplifications

- No partial fills or market impact
- Buying-power logic is conservative, not broker-grade margin
- See backtester README "Still simplified" for full list
