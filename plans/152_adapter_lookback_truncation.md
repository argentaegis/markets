# Plan 152: Adapter Lookback Truncation (Phase A)

## Goal

Reduce per-step work in the StrategizerStrategy adapter by passing only the last `lookback` bars to the strategy, instead of the full bar history. This cuts BarInput creation and strategy `closes` construction from O(n) to O(lookback) per step.

## Scope

- **Change**: `backtester/src/strategies/strategizer_adapter.py` only
- **No changes** to engine, provider, or strategy logic

## Implementation

### 1. Get lookback from strategy

In `StrategizerStrategy.on_step()`, before building `bars_by_symbol`:

```python
lookback = 500  # default fallback
req = getattr(self._strategy, "requirements", None)
if req is not None:
    lookback = req().lookback
```

### 2. Truncate bar list before conversion

Where bar_list is built from `snapshot.futures_bars` or `snapshot.underlying_bar`:

```python
if self._config.instrument_type == "future" and snapshot.futures_bars:
    bar_list = list(snapshot.futures_bars)[-lookback:]
elif snapshot.underlying_bar:
    bar_list = [snapshot.underlying_bar]
```

Apply `[-lookback:]` so the strategy receives at most `lookback` bars. The existing `[_bar_row_to_bar_input(b) for b in bar_list]` then converts only that subset.

### 3. Handle strategies without requirements()

Use `getattr(self._strategy, "requirements", None)`. If `requirements` is missing, use default `lookback = 500` (covers trend_entry ma_period=125, orb lookback=80).

## Verification

1. **Unit tests**: Run `pytest backtester/tests/integration/test_trailing_stop.py -v` — must pass.
2. **Full suite**: Run `pytest backtester/` — all tests must pass.
3. **Backtest run**: `python -m src.runner configs/trend_entry_trailing_stop_es_1mo.yaml --silent` — measure wall time before/after; expect ~2–3× speedup for 1-month run.
4. **Result parity**: Compare `summary.json` and `trades.csv` from run before vs after — num_trades, realized_pnl, win_rate must match (deterministic).

## Files

| File | Change |
|------|--------|
| backtester/src/strategies/strategizer_adapter.py | Add lookback resolution; truncate `bar_list` with `[-lookback:]` |
