 # Cursor Instructions: Options Backtester MVP

## 0) Objective
Build a **modular Python options backtester** that is:
- **Replaceable by module** (swap data, strategy, fill model, fees, reporting)
- **Deterministic and reproducible**
- Supports **bar sizes** `1d`, `1h`, `1m` in MVP (tick is post-MVP)
- Uses **quote-based fills** when possible; otherwise uses an explicit synthetic spread model
- Starts with **single strategy + single underlying**, but architecture must not block multi-strategy / multi-underlying / portfolio later

This document is the **MVP backbone**. All module task docs must conform to it.

---

## 1) MVP Scope

### In scope (must build)
- Event-driven loop driven by a `Clock` (bar-time events)
- Data ingestion via a `DataProvider` interface
- Canonical domain objects (`Order`, `Fill`, `Position`, `PortfolioState`, `MarketSnapshot`, `Event`)
- Strategy interface that outputs orders only (no side effects)
- Broker + FillModel with baseline quote-cross fills
- Portfolio accounting with mark-to-market each step
- Expiration settlement behavior (simplified)
- Fees/commissions (simple)
- Reporting artifacts: equity curve + trade ledger + order/fill log + summary metrics
- Run manifest for reproducibility (config snapshot + seed + data window)

### Out of scope (do not build in MVP)
- Tick-by-tick microstructure, queue position, level2
- Full broker margin parity
- Sophisticated corporate actions beyond “do not break”
- Live trading integration

If something is requested outside MVP:
1) add an interface/stub + config flag
2) implement simplest safe default
3) log clearly as not implemented / approximated

---

## 2) Architecture Rules (hard constraints)

### A1. Strategy ≠ execution
- Strategy produces **Orders** (intent).
- Broker/Execution produces **Fills** (reality).
- Portfolio updates ONLY from fills and lifecycle events.

### A2. Modules communicate via domain objects only
Do not pass raw pandas dataframes across module boundaries except inside `DataProvider` internals.

### A3. Clock-driven simulation
At each simulation timestamp:
1) Build `MarketSnapshot` for that timestamp
2) Call `Strategy.on_step(snapshot, portfolio_view)`
3) Validate and submit orders to `Broker`
4) Generate fills using `FillModel`
5) Update portfolio/accounting
6) Emit events and record logs/metrics

### A4. Configuration-first
- All runs driven by a typed `BacktestConfig`.
- Config is saved with run artifacts.
- Any stochastic behavior uses a seeded RNG from config.

### A5. Determinism
Given the same data + config + seed, outputs must be identical.

### A6. Logging and invariants
- Log all order/fill events.
- Fail fast (or configurable strictness) on missing critical data.
- Assert core invariants at each step.

---

## 3) Canonical Domain Objects (required)

Implement these dataclasses (or pydantic models) and treat them as stable:

- `Order`
  - id, ts, symbol/contract_id, side, qty, order_type (market/limit), limit_price (optional), tif
- `Fill`
  - order_id, ts, fill_price, fill_qty, fees, liquidity_flag (optional)
- `Position`
  - instrument_id, qty, avg_price, multiplier, instrument_type
- `PortfolioState`
  - cash, positions (map), realized_pnl, unrealized_pnl, equity
- `MarketSnapshot`
  - ts, underlying_bar (OHLCV), option_quotes (bid/ask or mid), metadata
- `Event`
  - ts, type (MARKET/ORDER/FILL/LIFECYCLE), payload

All IDs must be stable strings. Options must include a stable `contract_id`.

---

## 4) MVP Module Interfaces (required)

### M1) DataProvider
Responsibilities:
- Load underlying bars for `1d/1h/1m`.
- Provide option quotes at each ts for contracts needed by strategy.
- Provide contract metadata: strike, expiry, right, multiplier.

Required methods:
- `get_underlying_bars(symbol, timeframe, start, end) -> Bars`
- `get_option_chain(symbol, ts) -> list[contract_id]` OR `get_option_quotes(contract_ids, ts) -> Quotes`
- `get_contract_metadata(contract_id) -> ContractSpec`

Notes:
- Internal storage can be csv/parquet/duckdb; external interface stays stable.

### M2) Clock / Calendar
Responsibilities:
- Generate timestamps for the run based on base timeframe and market calendar.
- Skip non-trading times.

Required:
- `iter_times(start, end, timeframe_base) -> Iterable[datetime]`

### M3) Strategy
Responsibilities:
- Read snapshot + portfolio view, emit orders.
- No side effects.

Required:
- `on_step(snapshot: MarketSnapshot, state_view: PortfolioStateView) -> list[Order]`

### M4) Broker / Execution
Responsibilities:
- Validate orders (basic sanity checks).
- Apply FeeModel.
- Route to FillModel to generate fills.

Required:
- `submit_orders(orders, snapshot, portfolio_state) -> list[Fill]`

### M5) FillModel (baseline realism)
Rules (MVP baseline):
- If bid/ask exists:
  - Buy fills at ask
  - Sell fills at bid
- If only mid exists:
  - Use explicit synthetic spread: `mid +/- spread/2`
- Optional features are config flags but default off:
  - partial fills
  - mid-improvement probability (must be seeded)

### M6) FeeModel
- Per-contract commission + per-order fee (configurable).

### M7) Portfolio / Accounting
Responsibilities:
- Update positions and cash from fills.
- Mark-to-market each step.
- Compute realized/unrealized P&L and equity.

Lifecycle (MVP):
- Expiration settlement at intrinsic value (config chooses cash-settled vs underlying-settled if needed).
- Early assignment: config flag; default OFF. If OFF, log that it is ignored.

### M8) Reporter
Outputs per run:
- `equity_curve.csv`
- `orders.csv`
- `fills.csv`
- `trades.csv`
- `summary.json` (metrics)
- `run_manifest.json` (config snapshot, seed, data range, symbols, git hash if available)

---

## 5) Timeframe Rules (MVP)
- Exactly one **base timeframe** drives the simulation loop (`timeframe_base`).
- Higher timeframe indicators must be derived via internal resampling from base bars.
- Tick support is post-MVP; do not build tick ingestion yet, but do not hardcode bars-only assumptions into interfaces.

---

## 6) Invariants (must assert)
At each step:
- `portfolio.equity == portfolio.cash + sum(mark_value(position))` within tolerance
- No NaNs in cash/equity/pnl fields
- Option quantities are integers (contracts)
- Multipliers applied exactly once to value and P&L
- Every fill references a valid order id
- No position exists for unknown instrument_id

---

## 7) MVP Acceptance Criteria (Definition of Done)
MVP is complete when:
- Runs a single strategy on one underlying over a date range
- Supports `1d` and `1m` (and/or `1h`) bars with a consistent clock
- Uses bid/ask fills when available; otherwise synthetic spread with explicit config
- Produces order log, fill log, trade ledger, equity curve, and summary metrics
- Deterministic with a fixed seed
- Handles expiration settlement (simplified)
- Includes basic fees/commissions
- Unit tests exist for core invariants + a small golden dataset run

---

## 8) Implementation Order (Cursor should follow)
1) Domain objects + config
2) Clock/Calendar
3) DataProvider stub (local files) + MarketSnapshot builder
4) Portfolio accounting + marking
5) Broker + FillModel + FeeModel
6) Backtest engine loop wiring
7) Reporter outputs
8) Minimal example strategy + golden test run

---

## 9) Output Folder Layout
- `runs/{run_id}/`
  - `run_manifest.json`
  - `summary.json`
  - `equity_curve.csv`
  - `orders.csv`
  - `fills.csv`
  - `trades.csv`
  - `logs.jsonl` (optional structured events)

---

## 10) Coding Standards
- Python 3.11+.
- **Imports at top of file** unless there is an overriding reason (e.g. documented circular import workaround).
- Prefer `dataclasses` (or pydantic if needed), type hints everywhere.
- No hidden globals; pass dependencies explicitly.
- Keep modules small and testable.
- **Provide reasoning in docstrings**: Document why modules, classes, and significant functions exist—what problem they solve and how they fit the architecture. Use a "Reasoning" line in class/function docstrings where it clarifies intent.
- Any approximation (synthetic spread, ignored assignment) must be:
  - configurable
  - logged
  - documented in manifest

---
