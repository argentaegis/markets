---
name: Tactical Asset Allocation
overview: Extend the backtester engine to support multi-symbol equity runs, then implement a Faber-style Tactical Asset Allocation strategy across the six core ETFs (SPY, QQQ, IWM, TLT, GLD, USO) on daily bars.
todos:
  - id: 263-config
    content: Add `symbols` list to BacktestConfig with to_dict/from_dict support
    status: pending
  - id: 263-provider
    content: Add `extra_underlying_paths` to DataProviderConfig; teach LocalFileDataProvider to load current bars and history for multiple symbols
    status: pending
  - id: 263-snapshot
    content: Add explicit multi-symbol current-bar and history structures to MarketSnapshot; extend engine to populate them for multi-symbol equity runs
    status: pending
  - id: 263-engine-orders
    content: Extend broker, fill model, _instrument_params, and extract_marks to handle orders/marks for any symbol in the universe
    status: pending
  - id: 263-adapter
    content: Update StrategizerStrategy adapter to pass multi-symbol bars and specs; add TAA init branch
    status: pending
  - id: 263-runner
    content: Update runner to parse `symbols` from YAML, resolve each from catalog, wire extra_underlying_paths
    status: pending
  - id: 263-strategy
    content: Implement TacticalAssetAllocationStrategy in strategizer with SMA filter + monthly rebalance + equal-weight sizing
    status: pending
  - id: 263-tests
    content: Write strategizer unit tests for TAA strategy logic
    status: pending
  - id: 263-config-yaml
    content: Create backtester/configs/tactical_asset_allocation_example.yaml
    status: pending
  - id: 263-verify
    content: Run TAA backtest end-to-end; verify multi-asset positions, monthly trades, and report output
    status: pending
isProject: false
---

# 263: Multi-Symbol Engine + Tactical Asset Allocation

## Goal

Enable the backtester to run a single backtest across multiple symbols simultaneously, then implement a classic **Faber Tactical Asset Allocation (TAA)** strategy that rotates across SPY, QQQ, IWM, TLT, GLD, USO on daily bars using a trend filter and monthly rebalancing.

This is a two-part plan: a targeted engine extension (Part 1), then the strategy itself (Part 2).

---

## Part 1: Multi-Symbol Engine Extension

The engine currently wires one symbol per run. The strategizer `evaluate` interface already accepts `bars_by_symbol: dict[str, dict[str, list[BarInput]]]`, so the gap is in config, data loading, snapshot building, broker/fill handling, and order processing.

### 1a. Config: add `symbols` list

In [backtester/src/domain/config.py](backtester/src/domain/config.py):

- Add `symbols: list[str] = field(default_factory=list)` to `BacktestConfig`
- When `symbols` is non-empty, it is the universe; `symbol` becomes the "primary" symbol (used for run_id, reporting title)
- When `symbols` is empty, fall back to `[symbol]` (backward compat)
- Update `to_dict` / `from_dict` to round-trip the new field

### 1b. Runner: resolve multiple symbols from catalog

In [backtester/src/runner.py](backtester/src/runner.py):

- `_build_backtest_config` reads a new `symbols:` list from the YAML config
- For each symbol in the list, resolve underlying_path from the catalog via `_resolve_from_catalog`
- Store the mapping as a new field on `DataProviderConfig` or pass it alongside
- Add `"tactical_asset_allocation"` to `STRATEGY_NAMES`

The cleanest approach: add `extra_underlying_paths: dict[str, Path]` to `DataProviderConfig` ([backtester/src/loader/config.py](backtester/src/loader/config.py)) mapping symbol -> path for additional symbols beyond the primary. This avoids restructuring the existing single-path flow.

### 1c. Data provider: load bars and history for additional symbols

In [backtester/src/loader/provider.py](backtester/src/loader/provider.py):

- `LocalFileDataProvider._get_underlying_df` already takes `(symbol, timeframe)` and resolves `{symbol}_{timeframe}.parquet` from `self._config.underlying_path`
- For symbols in `extra_underlying_paths`, resolve from that symbol's path instead
- Add a method `get_underlying_bars_multi(symbols, timeframe, start, end) -> dict[str, Bars]` for bulk loading
- Keep the single-symbol `get_underlying_bars()` path intact for backward compatibility and tests

### 1d. Engine: build multi-symbol snapshot

In [backtester/src/engine/engine.py](backtester/src/engine/engine.py):

- Add explicit multi-symbol fields to `MarketSnapshot` ([backtester/src/domain/snapshot.py](backtester/src/domain/snapshot.py)):
  - `underlying_bars_by_symbol: dict[str, BarRow | None]`
  - `underlying_history_by_symbol: dict[str, list[BarRow]]`
- In `_build_step_snapshot`, when `config.symbols` is non-empty and `instrument_type == "equity"`:
  - Fetch the current bar for each symbol in the universe
  - Fetch the lookback window for each symbol in the universe
  - Populate both multi-symbol fields on the snapshot
- Existing single-symbol flow unchanged when `symbols` is empty

This avoids the design mismatch where one field is asked to represent both the current bar and the full history required for a 200-day SMA.

### 1e. Broker, fill model, and engine: handle orders for multiple instruments

The order/fill path in `_process_orders` already routes by `order.instrument_id`, but the current broker and fill model still assume one underlying symbol. For equity multi-symbol:

- Each order's `instrument_id` is the symbol (e.g. "SPY", "TLT")
- Extend `broker._instrument_available()` to check `snapshot.underlying_bars_by_symbol[order.instrument_id]` for equities, not only `instrument_id == config.symbol`
- Extend `fill_model.fill_order()` to price equity fills from the matching symbol's current bar, not only `snapshot.underlying_bar`
- Extend `_instrument_params()` so any instrument in `config.symbols` is treated as `(1.0, "equity")`
- Extend `extract_marks()` to emit marks for all available underlying symbols in the snapshot, not just `config.symbol`
- Keep option and futures behavior unchanged

Without this step, non-primary equity orders would be rejected or filled off the wrong bar.

### 1f. Adapter: pass multi-symbol bars to strategizer

In [backtester/src/strategies/strategizer_adapter.py](backtester/src/strategies/strategizer_adapter.py):

- When `config.symbols` is non-empty, build strategizer `bars_by_symbol` from `snapshot.underlying_history_by_symbol`
- Build `specs` for each symbol (all use `_MinimalSpec` for equities)
- Add `elif strategy_name == "tactical_asset_allocation":` init branch

---

## Part 2: Tactical Asset Allocation Strategy

### Strategy: Faber TAA

A well-known strategy from Meb Faber's *"A Quantitative Approach to Tactical Asset Allocation"* (2007). The six ETFs represent a diversified macro portfolio: US large cap (SPY), US tech (QQQ), US small cap (IWM), long bonds (TLT), gold (GLD), oil (USO).

**Logic (evaluated daily, acts monthly):**

1. On the first trading day of each month (or when the month changes vs. the previous bar):
2. For each symbol in the universe:
  - Compute 200-day SMA from bar history
  - If `close > SMA` -> signal ON (hold equal-weight allocation)
  - If `close <= SMA` -> signal OFF (go to cash for that slot)
3. Target allocation per active symbol = `equity / count(active symbols)`, or 0 if no signals are on
4. Compare target qty vs. current position qty; emit BUY/SELL orders to rebalance
5. Between rebalance dates, do nothing

**Parameters:**

- `sma_period`: 200 (default)
- `rebalance_day`: 1 (first trading day of month)
- `symbols`: list of symbols in universe

**Key design points:**

- Long-only, no leverage, no shorting
- Cash is the "risk-off" asset (no explicit bond rotation)
- Equal-weight across active signals (not risk-parity -- that's a future enhancement)
- The strategy is portfolio-aware: it reads positions and equity to compute rebalance targets
- SELL orders must be capped at the current held quantity so rebalance-down logic cannot accidentally create short positions
- When there are fewer than `sma_period` bars for a symbol, that symbol is skipped until fully warmed up

### Files to create/modify

**New file:** `strategizer/src/strategizer/strategies/tactical_asset_allocation.py`

- `TacticalAssetAllocationStrategy(Strategy)` with `evaluate()` logic above
- Requires `lookback=210` (200 SMA + buffer), `needs_quotes=False`

**Update:** `strategizer/src/strategizer/strategies/__init__.py`

- Register `"tactical_asset_allocation": TacticalAssetAllocationStrategy` in `STRATEGY_REGISTRY`

**New file:** `strategizer/tests/test_tactical_asset_allocation.py`

- Unit tests: SMA filter on/off, monthly rebalance trigger, equal-weight sizing, no-trade between months, all-off goes to full cash, and rebalance-down never emits a sell larger than the current holding

**New file:** `backtester/configs/tactical_asset_allocation_example.yaml`

```yaml
symbol: SPY
symbols: [SPY, QQQ, IWM, TLT, GLD, USO]
instrument_type: equity
start: "2019-03-01T00:00:00+00:00"
end: "2026-03-10T00:00:00+00:00"
timeframe_base: "1d"
initial_cash: 100000.0
strategy:
  name: tactical_asset_allocation
  sma_period: 200
```

`2019-03-01` is late enough to leave a full 200-trading-day warmup from the current `2018-05-01` data start. `2019-01-02` is not.

---

## What changes vs. what stays the same

- **Single-symbol backtests are unaffected** -- when `symbols` is empty, everything falls back to the current `symbol`-only path
- **No changes to portfolio accounting internals** -- portfolio state already supports multiple instruments by `instrument_id`
- **Broker and fill model do require targeted multi-symbol equity changes** -- they are currently single-underlying
- **No changes to reporter** -- it already handles multiple instruments in trades.csv and summary
- **The strategizer evaluate interface is unchanged** -- it already accepts `bars_by_symbol`

Small report/run-manifest follow-up:

- Keep reporting changes minimal, but ensure multi-symbol runs record the full universe in run metadata and use a neutral portfolio-style title rather than implying the run is only `SPY`

---

## Data available

All 6 symbols have 1d bars from 2018-05-01 to 2026-03-10 in `data/exports/`. The config starts at 2019-03-01 to allow a full 200-trading-day SMA warmup from the 2018-05-01 data start.

---

## Verification

- Existing tests pass (single-symbol backward compat)
- Strategizer unit tests for the new strategy
- Run the TAA config end-to-end; verify:
  - Multiple positions appear in the portfolio
  - Monthly rebalancing produces trades
  - Symbols rotate in/out based on SMA filter
  - Summary and report.html show meaningful multi-asset results
  - No negative holdings are created during rebalance-down or exit-to-cash flows
  - Non-primary symbols (e.g. `TLT`, `GLD`) are accepted by broker validation and filled using their own bars
