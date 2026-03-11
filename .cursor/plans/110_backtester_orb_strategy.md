---
name: 110 Backtester ORB Strategy
overview: "Implement ORBFuturesStrategy wrapping strategizer ORB. Add to strategy registry. Config supports instrument_type future, symbol ESH26, timeframe_base 5m, qty."
todos: []
isProject: false
---

# 110: Backtester ORB Strategy

Conforms to [000_strategizer_mvp_plan.md](000_strategizer_mvp_plan.md) §5.5.

---

## Objective

Implement a backtester strategy that wraps the strategizer ORB. When config specifies `strategy.name: orb_5m` and `instrument_type: future`, the engine runs ORB from strategizer via the adapter. Produces Orders that the broker fills.

---

## Prerequisites (Blockers)

These must be addressed before or as part of 110:

| Blocker | Current state | What's needed |
|---------|---------------|---------------|
| **Clock** | `iter_times` supports only `"1d"`, `"1h"`, `"1m"` | Add 5m support (e.g. `_iter_5m` with 5-minute bar closes) |
| **Config / loader** | BC6 restricts `timeframe_base` to ["1d","1h","1m"] | Allow `"5m"`; parse `instrument_type`, `futures_contract_spec` |
| **DataProvider** | `timeframes_supported` default excludes `"5m"` | Include 5m; provide ESH26_5m data (or use `get_underlying_bars`) |
| **Engine** | Single bar per step; no bar history | Fetch and pass bar history for futures runs |
| **Fill model** | Handles market/limit only | Extend for stop orders (fill when bar crosses stop level) |
| **Runner** | `_build_backtest_config` doesn't parse futures | Parse strategy params, instrument_type, futures_contract_spec; inject into strategy for orb_5m |

---

## Existing Foundation

- Step 100: Adapter (snapshot_to_strategizer_input, signal_to_order, BacktesterPortfolioView)
- Step 070–090: Futures domain, DataProvider, fill model
- backtester: Strategy ABC (on_step), STRATEGY_REGISTRY, runner._build_strategy
- strategizer: ORB5mStrategy

---

## ORBFuturesStrategy

**Design choice:** Strategy receives bar history via snapshot. No provider in strategy; engine owns data flow. Constructor stays simple.

```python
class ORBFuturesStrategy(Strategy):
    """Wraps strategizer ORB for backtester. Produces Orders for futures."""
    def __init__(self, symbol: str, spec: FuturesContractSpec, qty: int = 1,
                 min_range_ticks: int = 4, max_range_ticks: int = 40): ...
    def on_step(self, snapshot: MarketSnapshot, state_view: PortfolioState) -> list[Order]:
        # 1. Build bars_by_symbol from snapshot.futures_bars (engine-populated)
        # 2. Adapt snapshot + portfolio via snapshot_to_strategizer_input(..., bars=futures_bars)
        # 3. Call strategizer ORB.evaluate(...)
        # 4. Adapt signals to Orders via signal_to_order
```

Runner passes symbol, spec (from config.futures_contract_spec), and params from strategy config.

---

## Bar History Design

Strategizer ORB needs `bars_by_symbol[symbol]["5m"]` = list of BarInput (lookback ~80 bars).

**Choice:** Extend MarketSnapshot with `futures_bars: list[BarRow] | None`. Engine populates it when `instrument_type == "future"` by calling `provider.get_underlying_bars(symbol, "5m", config.start, ts)`.

Strategy uses `snapshot.futures_bars` and passes to `snapshot_to_strategizer_input(..., bars=futures_bars)`. Strategy stays stateless; engine owns data flow.

---

## Stop Order Fill Model

ORB emits `entry_type="STOP"` with `entry_price` as the stop level. Current fill model handles market/limit only.

**Logic:** BUY stop at X fills when bar high ≥ X (fill price = X, or bar open if gap). SELL stop at X fills when bar low ≤ X.

Implementation: in `fill_order`, branch on `order.order_type == "stop"`; use `snapshot.underlying_bar` high/low vs `order.limit_price`; fill accordingly.

---

## DataProvider and 080

For 110 without step 080: use `get_underlying_bars(symbol, "5m", start, end)` with layout `{symbol}_{timeframe}.parquet` (e.g. ESH26_5m.parquet). Pass `config.futures_contract_spec` into strategy; no `get_futures_contract_spec` needed for ORB wiring.

080 required only if formal futures metadata and `get_futures_bars` path are desired. MVP can use underlying bars + config.

---

## Implementation Phases

### Phase 0: Prerequisites

| Stage | Tasks |
|-------|-------|
| Clock | Add 5m support to `iter_times` (e.g. `_iter_5m`) |
| Config | Allow timeframe_base `"5m"`; parse instrument_type, futures_contract_spec in runner |
| DataProvider | Include `"5m"` in timeframes_supported; add ESH26_5m fixture or resample |

### Phase 1: Engine bar history

| Stage | Tasks |
|-------|-------|
| Extend | MarketSnapshot: optional `futures_bars: list[BarRow] | None` |
| Extend | Engine: for futures, fetch bar history via `get_underlying_bars(symbol, "5m", start, ts)` |
| Extend | `_build_step_snapshot`: populate `futures_bars` when instrument_type=future |

### Phase 2: Fill model stops

| Stage | Tasks |
|-------|-------|
| Extend | fill_order: branch on order_type="stop"; fill when bar high/low crosses stop level |

### Phase 3: ORBFuturesStrategy

| Stage | Tasks |
|-------|-------|
| Implement | ORBFuturesStrategy(symbol, spec, qty, min_range_ticks, max_range_ticks) |
| Implement | on_step: snapshot_to_strategizer_input with bars, ORB.evaluate, signal_to_order |
| Register | STRATEGY_REGISTRY["orb_5m"] = ORBFuturesStrategy |
| Config | strategy.name: orb_5m, params: min_range_ticks, max_range_ticks, qty |

### Phase 4: Wiring

| Stage | Tasks |
|-------|-------|
| Runner | _build_backtest_config parses instrument_type, futures_contract_spec |
| Runner | _build_strategy(strategy_config, config, provider) for orb_5m |
| Runner | Pass symbol, spec, params when constructing ORBFuturesStrategy |
| Test | Unit test with mock provider; integration test with canned data |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Bar history | Engine fetches and passes in snapshot.futures_bars | Strategy stays stateless; engine owns data flow |
| Provider in strategy | No | History in snapshot; spec from config |
| Registry key | "orb_5m" | Matches strategizer strategy name |
| qty | From params, default 1 | 000 §13 |
| Stop fills | True stop logic (bar crosses level) | ORB emits STOP; approximate market fill is wrong |

---

## Acceptance Criteria

- [ ] Clock supports timeframe_base 5m
- [ ] Config parses instrument_type, futures_contract_spec; runner wires to BacktestConfig
- [ ] MarketSnapshot has futures_bars; engine populates for futures runs
- [ ] Fill model handles stop orders (bar crosses stop level)
- [ ] ORBFuturesStrategy implements Strategy; uses snapshot.futures_bars
- [ ] Registry includes orb_5m
- [ ] Config: instrument_type future, symbol ESH26, strategy orb_5m
- [ ] Strategy produces Orders on breakout
- [ ] Integration test: run with canned data

---

## Open Decisions

| Topic | Options |
|-------|---------|
| 080 first? | Implement 110 with get_underlying_bars + config spec; or wait for 080 |
| Timeframe expansion | Add only 5m for ORB; or design general timeframe extensibility |

---

## Out of Scope

- Multi-symbol ORB in same run
- Options strategies from strategizer
- Golden test (step 120)
