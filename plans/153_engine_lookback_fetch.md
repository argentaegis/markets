# Plan 153: Engine Lookback Fetch (Phase B)

## Goal

Narrow the bar fetch range in the engine so the provider returns only the last `lookback` bars for futures runs, instead of the full history from `config.start` to `ts`. Reduces DataFrame slicing and BarRow creation in the provider from O(n) to O(lookback) per step. Builds on Plan 152.

## Scope

- **Change**: `backtester/src/engine/engine.py`
- **Optional**: `backtester/src/loader/provider.py` if engine passes lookback

## Prerequisites

- Plan 152 (adapter truncation) completed and verified.

## Implementation

### 1. Get lookback from strategy

Introduce helper to obtain lookback:

```python
def _get_lookback(strategy: Strategy) -> int:
    req = getattr(strategy, "requirements", None)
    if req is None:
        return 500
    return req().lookback
```

### 2. Compute effective start for futures

For `instrument_type == "future"`, map lookback (bars) to time duration based on timeframe:
- 1m: 1 bar = 1 minute
- 5m: 1 bar = 5 minutes
- 1h: 1 bar = 1 hour
- 1d: 1 bar = 1 day

```python
def _lookback_to_timedelta(timeframe: str, lookback: int) -> timedelta:
    if timeframe == "1m":
        return timedelta(minutes=lookback)
    if timeframe == "5m":
        return timedelta(minutes=lookback * 5)
    if timeframe == "1h":
        return timedelta(hours=lookback)
    if timeframe == "1d":
        return timedelta(days=lookback)
    return timedelta(days=lookback)  # fallback
```

### 3. Narrow fetch range in _build_step_snapshot

Pass `strategy` into `_build_step_snapshot` (or pass `lookback` from caller). For futures:

```python
if config and config.instrument_type == "future":
    lookback = _get_lookback(strategy)
    delta = _lookback_to_timedelta(timeframe, lookback)
    effective_start = max(config.start, ts - delta)
    history = provider.get_underlying_bars(symbol, timeframe, effective_start, ts)
    # ... rest unchanged
```

### 4. Thread strategy into _build_step_snapshot

`run_backtest` already has `strategy`; pass it to `_build_step_snapshot(provider, symbol, timeframe, ts, config=config, strategy=strategy)`.

## Verification

1. **Full suite**: Run `pytest backtester/` — all tests must pass.
2. **Backtest run**: `python -m src.runner configs/trend_entry_trailing_stop_es_1mo.yaml --silent` — measure wall time; expect further 2–10× speedup vs Plan 152.
3. **Result parity**: summary.json and trades.csv must match Plan 152 output (deterministic).

## Files

| File | Change |
|------|--------|
| backtester/src/engine/engine.py | Add _get_lookback, _lookback_to_timedelta; pass strategy to _build_step_snapshot; narrow (start, ts) for futures |
| backtester/src/loader/provider.py | No change required (engine passes narrower range) |
