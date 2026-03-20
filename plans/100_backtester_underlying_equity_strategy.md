# 100: Underlying Equity Strategy for Validation (Red-Green-Refactor)

## The Problem

The broker and fill model already support underlying equity orders (`instrument_id == symbol`), but the engine calls `apply_fill` without specifying the multiplier, so it defaults to `100.0` (options). For equity, it should be `1.0`.

```python
# Before fix — src/engine/engine.py _process_orders:
for fill in fills:
    matched_order = order_by_id[fill.order_id]
    portfolio = apply_fill(portfolio, fill, matched_order)  # defaults to multiplier=100.0
```

`apply_fill` signature in `src/portfolio/accounting.py`:

```python
def apply_fill(portfolio, fill, order, *, multiplier=100.0, instrument_type="option"):
```

## What Already Works

- `_instrument_available` in `src/broker/broker.py` returns `True` when `instrument_id == symbol` and an underlying bar exists
- `fill_order` in `src/broker/fill_model.py` fills underlying orders using `bar.close` with synthetic spread
- `validate_order` already uses `mult = 1.0` when `instrument_id == symbol`
- `extract_marks` in `src/portfolio/accounting.py` includes `symbol -> bar.close` in marks
- `_detect_expirations` safely skips non-option positions (no `ContractSpec` found)

## Implementation Phases

### Phase 1: Engine Multiplier Fix

| Stage | Tasks |
|-------|-------|
| **Red** | Test in `src/engine/tests/test_engine.py`: buy underlying symbol (instrument_id="SPY") -> position has `multiplier=1.0` and `instrument_type="equity"`. Cash reduced by `price * qty * 1.0` not `price * qty * 100.0`. Existing option tests still pass with `multiplier=100.0`. |
| **Green** | Fix `_process_orders` in `src/engine/engine.py`: determine multiplier and instrument_type from `order.instrument_id == config.symbol`. Pass to `apply_fill`. |
| **Refactor** | Extract helper `_instrument_params(instrument_id, symbol) -> (multiplier, instrument_type)`. |

### Phase 2: BuyAndHoldUnderlying Strategy

| Stage | Tasks |
|-------|-------|
| **Red** | Tests in `src/strategies/tests/test_buy_and_hold_underlying.py`: (1) Is a `Strategy` subclass. (2) First `on_step` returns 1 BUY order with `instrument_id=symbol`. (3) Second call returns empty. (4) Order has `order_type="market"`, `side="BUY"`. (5) `symbol` and `qty` configurable. (6) Order `ts` matches snapshot `ts`. |
| **Green** | Implement `BuyAndHoldUnderlying` in `src/strategies/buy_and_hold_underlying.py`. Constructor takes `symbol` and `qty` (default 100 shares). |
| **Refactor** | Docstrings with reasoning. Export from `__init__.py`. |

### Phase 3: Integration Tests (fixture data)

| Stage | Tasks |
|-------|-------|
| **Red** | Tests in `tests/integration/test_underlying_strategy.py` using existing fixture data (`src/loader/tests/fixtures/`). |
| **Green** | All pass with Phase 1+2 implementation. |

Integration test specifications (all `@pytest.mark.integration`, shared fixtures):

- `test_underlying_buy_and_hold_fills` -- BuyAndHoldUnderlying(symbol="SPY", qty=10): 1 fill, fill_price near bar.close, position has multiplier=1.0
- `test_underlying_equity_curve_tracks_price` -- equity curve varies as SPY price changes across steps
- `test_underlying_no_expiration` -- no LIFECYCLE expiration events (equities don't expire)
- `test_underlying_invariants_hold` -- portfolio invariants: equity == cash + positions, no NaN, integer qty
- `test_underlying_report_all_files` -- `generate_report` produces all 6 files; trades.csv is header-only (no round-trip)

### Phase 4: Real-Data Integration Test (23-month SPY)

| Stage | Tasks |
|-------|-------|
| **Red** | Test in `tests/integration/test_underlying_strategy.py`: run BuyAndHoldUnderlying against `data/exports/spy/` with 1d bars over a meaningful date range (e.g. 2024-03-01 to 2025-12-31). |
| **Green** | Passes with existing implementation + date-level matching fix in `LocalFileDataProvider.get_underlying_bars` for 1d bars. |

Real-data test specifications:

- `test_real_spy_buy_and_hold` -- BuyAndHoldUnderlying(symbol="SPY", qty=100) over ~22 months of 1d bars. Equity curve has 400+ points. Final equity > initial (SPY went from ~510 to ~680). Total return roughly matches SPY actual return. No NaN. Invariants hold. Uses `report_output_dir` so `--save-reports` produces inspectable output.
- Skips with `pytest.mark.skipif` if `data/exports/spy/SPY_1d.parquet` doesn't exist.

### Phase 5: Exports and Registry

- Export `BuyAndHoldUnderlying` from `src/strategies/__init__.py`
- Add `"buy_and_hold_underlying"` to `STRATEGY_REGISTRY` in `src/runner.py`
- Save plan as `planning/100_underlying_equity_strategy.md`

## Additional Fix: Daily Bar Timestamp Matching

During Phase 4, a timestamp mismatch was discovered: real-world data from Polygon.io stores daily bar timestamps at `05:00 UTC` (midnight ET), while the NYSE clock generates timestamps at `21:00 UTC` (4pm ET close). Both represent the same trading session. Fixed `LocalFileDataProvider.get_underlying_bars` to use date-level matching for `1d` timeframe bars.
