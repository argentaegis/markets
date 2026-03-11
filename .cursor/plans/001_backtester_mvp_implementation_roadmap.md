# 001: MVP Implementation Roadmap

This document reorganizes [000_options_backtester_mvp.md](000_options_backtester_mvp.md) into discrete implementation steps. Each step maps to one or more detailed plan files that can be enacted independently. All plans must conform to 000.

---

## Project Practice: Test-First (Red-Green-Refactor)

**Default for this project:** Write tests first, then make them pass, then refactor. Each implementation unit uses discrete stages:

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests that specify the expected behavior. Run tests; they fail. |
| **Green** | Implement minimal code to make the tests pass. Run tests; they pass. |
| **Refactor** | Clean up implementation while keeping tests green. |

Plans structure work as discrete Red → Green → Refactor cycles. No implementation code before tests.

---

## Coding Standards

See **`.cursor/rules/code-standards.mdc`** for the authoritative coding standards. That file defines line length, function length, descriptive names, reasoning in docstrings, imports, and type hints.

---

## Objective (from 000 §0)

Build a **modular Python options backtester** that is:

- Replaceable by module (swap data, strategy, fill model, fees, reporting)
- Deterministic and reproducible
- Supports bar sizes `1d`, `1h`, `1m` (tick is post-MVP)
- Uses quote-based fills when possible; otherwise explicit synthetic spread model
- Starts single strategy + single underlying; architecture must not block multi-strategy / multi-underlying / portfolio later

---

## Scope Summary

**In scope:** Event-driven loop, DataProvider, domain objects, Strategy interface, Broker + FillModel, portfolio accounting, expiration settlement, fees, reporting (equity curve, trades, orders, fills, summary), run manifest.

**Out of scope:** Tick microstructure, full broker margin parity, corporate actions, live trading.

---

## Architecture Rules (000 §2 — hard constraints)

| ID | Rule |
|----|------|
| A1 | Strategy produces Orders; Broker produces Fills; Portfolio updates only from fills |
| A2 | Modules communicate via domain objects only (no raw DataFrames across boundaries) |
| A3 | Clock-driven simulation loop (MarketSnapshot → Strategy → Broker → FillModel → Portfolio → events) |
| A4 | Configuration-first: typed `BacktestConfig`, saved with run artifacts, seeded RNG |
| A5 | Determinism: same data + config + seed → identical outputs |
| A6 | Log all order/fill events; fail fast on missing critical data; assert invariants |

---

## Discrete Implementation Steps

The following steps are ordered per 000 §8. Each may have an associated plan file (e.g. `0XX_name.md`). Plans that exist are linked.

| Step | Name | Description | Plan(s) | Status |
|------|------|-------------|---------|--------|
| **1** | Domain objects + config | Canonical dataclasses: Order, Fill, Position, PortfolioState, MarketSnapshot, Event; typed BacktestConfig; contract_id, Bars, Quotes, ContractSpec | [030_domain_objects_and_config.md](030_domain_objects_and_config.md) | Done |
| **2** | Clock / Calendar | Generate timestamps for run; `iter_times(start, end, timeframe_base)`; skip non-trading times; market calendar | [040_clock_calendar.md](040_clock_calendar.md) | Done |
| **3** | DataProvider + MarketSnapshot | Load underlying bars (1d/1h/1m, parquet default), option quotes, contract metadata; build MarketSnapshot at each ts; local file stub | [010_m1_dataprovider_execution_plan.md](010_m1_dataprovider_execution_plan.md), [011_m1_dataprovider_test_plan.md](011_m1_dataprovider_test_plan.md) | Done |
| **4** | Portfolio accounting + marking | Update positions/cash from fills; mark-to-market each step; realized/unrealized P&L; equity; expiration settlement (simplified) | [050_portfolio_accounting.md](050_portfolio_accounting.md) | Done |
| **5** | Broker + FillModel + FeeModel | Validate orders; apply FeeModel; FillModel (bid/ask or synthetic spread); submit_orders → list[Fill] | [060_broker_fillmodel_feemodel.md](060_broker_fillmodel_feemodel.md) | Done |
| **6** | Backtest engine loop | Wire Clock, DataProvider, Strategy, Broker, Portfolio; A3 loop; events and logs | [070_backtest_engine_loop.md](070_backtest_engine_loop.md) | Done |
| **7** | Reporter | Outputs: equity_curve.csv, orders.csv, fills.csv, trades.csv, summary.json, run_manifest.json | [080_reporter_outputs.md](080_reporter_outputs.md) | Done |
| **8** | Example strategy + golden test | Minimal strategy; end-to-end run; unit tests for invariants + golden dataset | — | — |

---

## Supporting / Cross-Cutting Plans

These address capabilities used across multiple steps:

| Plan | Purpose |
|------|---------|
| [044_domain_and_clock_validation.md](044_domain_and_clock_validation.md) | Validation that exercises 030 (domain + config) and 040 (clock) together |
| [020_cli_market_data_fetch.md](020_cli_market_data_fetch.md) | CLI to fetch market data (md fetch, md export) for DataProvider input |
| [021_project_readme.md](021_project_readme.md) | Project documentation |
| [022_env_and_examples.md](022_env_and_examples.md) | Environment setup and examples |
| [025_marketdata_reorg_options_massive.md](025_marketdata_reorg_options_massive.md) | Market data reorganization |

---

## Required Domain Objects (000 §3)

| Object | Key Fields |
|--------|------------|
| Order | id, ts, symbol/contract_id, side, qty, order_type, limit_price?, tif |
| Fill | order_id, ts, fill_price, fill_qty, fees, liquidity_flag? |
| Position | instrument_id, qty, avg_price, multiplier, instrument_type |
| PortfolioState | cash, positions, realized_pnl, unrealized_pnl, equity |
| MarketSnapshot | ts, underlying_bar (OHLCV), option_quotes, metadata |
| Event | ts, type (MARKET/ORDER/FILL/LIFECYCLE), payload |

---

## Required Module Interfaces (000 §4)

| Module | Core Responsibility | Key Method(s) |
|--------|---------------------|---------------|
| M1 DataProvider | Load bars, option quotes, metadata | get_underlying_bars, get_option_chain, get_option_quotes, get_contract_metadata |
| M2 Clock/Calendar | Generate simulation timestamps | iter_times(start, end, timeframe_base) |
| M3 Strategy | Emit orders from snapshot + portfolio view | on_step(snapshot, state_view) → list[Order] |
| M4 Broker | Validate, fee, route to FillModel | submit_orders(orders, snapshot, portfolio) → list[Fill] |
| M5 FillModel | Quote-based or synthetic fills | (applied inside Broker) |
| M6 FeeModel | Per-contract + per-order fees | (configurable) |
| M7 Portfolio | Positions, cash, mark-to-market, P&L | Update from fills; equity invariant |
| M8 Reporter | Output artifacts | equity_curve, orders, fills, trades, summary, run_manifest |

---

## Invariants (000 §6 — must assert)

- `portfolio.equity == portfolio.cash + sum(mark_value(position))` within tolerance
- No NaNs in cash/equity/pnl
- Option quantities are integers
- Multipliers applied exactly once
- Every fill references a valid order_id
- No position for unknown instrument_id

---

## Output Folder Layout (000 §9)

```
runs/{run_id}/
  run_manifest.json
  summary.json
  equity_curve.csv
  orders.csv
  fills.csv
  trades.csv
  logs.jsonl (optional)
```

---

## MVP Acceptance Criteria (000 §7)

MVP complete when:

- Single strategy on one underlying over a date range
- Supports `1d` and `1m` (and/or `1h`) bars with consistent clock
- Bid/ask fills when available; otherwise synthetic spread with explicit config
- Order log, fill log, trade ledger, equity curve, summary metrics
- Deterministic with fixed seed
- Expiration settlement (simplified)
- Basic fees/commissions
- Unit tests for core invariants + golden dataset run

---

## Suggested Plan File Numbers (for new plans)

To keep numbering consistent as new plans are added:

| Step | Suggested plan(s) |
|------|-------------------|
| 2 — Clock | 040_clock_calendar.md |
| 4 — Portfolio | 050_portfolio_accounting.md |
| 5 — Broker/Fill/Fee | 060_broker_fillmodel_feemodel.md |
| 6 — Engine loop | 070_backtest_engine_loop.md |
| 7 — Reporter | 080_reporter_outputs.md |
| 8 — Example + golden | 090_example_strategy_golden_test.md |

---

## Dependency Order

```
1 (Domain + Config) → 2 (Clock) → 3 (DataProvider + Snapshot) → 4 (Portfolio)
                                                            ↘ 5 (Broker/Fill/Fee) → 6 (Engine) → 7 (Reporter) → 8 (Example)
```

- Steps 4 and 5 can be developed in parallel after step 3.
- Steps 6–8 are sequential after 4 and 5.
