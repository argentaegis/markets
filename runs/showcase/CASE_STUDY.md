# Flagship Case Study — Tactical Asset Allocation

This is the primary showcase run for the backtester. It demonstrates a Faber-style tactical asset allocation strategy across six ETFs with closed trades, multi-year CAGR, Sharpe, and turnover.

## Strategy Thesis

Faber-style TAA aims to reduce drawdowns in bear regimes by moving to cash when an asset's price crosses below its 200-day SMA. The trade-off: turnover from tactical shifts, whipsaws in choppy markets, and underperformance in strong trending bull markets when the strategy may sit in cash during early recoveries. This run tests that thesis over 2019–2026.

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

## Benchmark Comparison

Same window (2019-03-01 to 2026-03-10), same broker (`ibkr_equity_spread`), same fill timing (`next_bar_open`). Benchmark: SPY buy-and-hold (`configs/buy_and_hold_underlying_spy_benchmark.yaml`).

| Metric | TAA (flagship) | SPY buy-and-hold |
|--------|----------------|-------------------|
| Final equity | ~$183,131 | ~$237,625 |
| Total return | ~83.1% | ~137.6% |
| CAGR | ~9.0% | ~13.1% |
| Max drawdown % | 24.4% | 19.7% |
| Sharpe | 0.73 | 0.74 |
| Turnover | 21.38 | 0.63 |

**Interpretation:** Over this period, passive SPY buy-and-hold outperformed TAA on return and drawdown. SPY's strong trend from 2019–2026 favored staying invested; the TAA trend filter reduced exposure during pullbacks but also during recoveries. Turnover (21.4 vs 0.6) reflects the cost of tactical shifts. Similar Sharpe suggests comparable risk-adjusted returns despite different paths. This run does not prove TAA is inferior—regime and window matter—but it provides honest context.

## What This Run Demonstrates

- Multi-asset, multi-year TAA: Faber-style trend filter across 6 ETFs
- End-to-end pipeline: config-driven run, catalog data, strategy signals, next-bar-open fills, portfolio accounting, CSV/JSON/HTML artifacts
- Risk-adjusted reporting: Sharpe, CAGR, turnover from step returns and fill notional
- Execution realism: 10 bps equity costs, `next_bar_open` fill timing

## Interpretation

Sharpe ~0.73 indicates modest risk-adjusted returns. CAGR ~9% and 24% max drawdown show the strategy participated in upside but experienced meaningful drawdowns. Turnover 21.4 reflects monthly rebalancing and trend-filter exits; the 10 bps cost is factored in. The trade-off: trend filters can reduce exposure during crashes but also during rebounds—regime sensitivity matters.

## Limitations

This run does **not** prove robustness. No walk-forward validation, no out-of-sample test, no parameter sensitivity analysis. Execution is simplified (no partial fills, no market impact). Results are specific to this window; different start/end dates may yield different relative performance vs benchmarks.

## End-of-Run State

`num_open_positions: 15` at cutoff is expected. TAA rebalances monthly; the run ends mid-cycle. Positions held when price is above the 200-day SMA remain open—no forced liquidation at the end date. The engine does not auto-close at cutoff; positions are marked-to-market for final equity.

## Reproducing This Run

Requires catalog data: `backtester/data/catalog.yaml` and `backtester/data/exports/` for SPY, QQQ, IWM, TLT, GLD, USO. Fetch via market-data CLI or provide your own.

```bash
make backtester-run BACKTESTER_CONFIG=configs/tactical_asset_allocation_example.yaml
```

## Known Simplifications

- **Market impact:** none
- **Partial fills:** none
- **Buying-power:** conservative, not broker-grade margin
- See backtester README "Still simplified" for full list
