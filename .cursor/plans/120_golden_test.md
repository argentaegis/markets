---
name: 120 Golden Test
overview: "Deterministic backtest: ORB on ES 5m canned data. Assert fill count, fill prices (tick-aligned), equity. Same data and config produce identical output."
todos: []
isProject: false
---

# 120: Golden Test

Conforms to [000_strategizer_mvp_plan.md](000_strategizer_mvp_plan.md) §7 and §9.

---

## Objective

Create a deterministic golden test that runs the ORB strategy on futures (ES 5m) with canned data. Assert:
- Fill count (and order count)
- Fill prices (tick-aligned)
- Final equity
- Reproducibility: same data + config → identical outputs

---

## Fill Count vs Trade Count

ORB emits entry signals only; positions remain open at session end. `derive_trades` yields **closed** round-trips, so for entry-only ORB we get **0 trades**.

**Choice:** Assert on **fill count** (and order count), not trade count. A single LONG breakout yields 1 order, 1 fill, 0 closed trades.

---

## Existing Foundation

- Step 110: ORBFuturesStrategy, engine passes bar history, orb_5m registry
- Step 090: Tick-aligned fills, stop order fill model
- backtester: Reporter produces equity_curve.csv, trades.csv, orders.csv, fills.csv
- derive_trades supports instrument_multipliers (futures point_value)
- Existing golden infra: test_golden.py, generate_golden.py for BuyAndHold/CoveredCall

---

## Golden Data Design

**Layout:** Overwrite `src/loader/tests/fixtures/underlying/ESH26_5m.parquet`. Keeps path wiring simple; no separate golden fixture tree.

**Minimal scenario:** Two 5m bars that produce one LONG breakout and fill.

| Bar | ts (UTC) | open | high | low | close | Role |
|-----|----------|------|------|-----|-------|------|
| 1 | 2026-01-02 14:35 | 5400 | 5410 | 5405 | 5408 | OR bar (9:35 ET). Range 20 ticks ✓ |
| 2 | 2026-01-02 15:00 | 5409 | 5415 | 5408 | 5412 | Breakout: close>5410. Stop 5410.25, high≥stop → fill ✓ |

- RTH: 9:30–16:00 ET. First RTH bar close = 9:35 ET = 14:35 UTC (January EST).
- OR range 5405–5410 = 20 ticks (within min 4, max 40).
- Breakout bar: close 5412 > OR high 5410 → LONG. Entry stop = 5410.25. Bar high 5415 ≥ 5410.25 → fill model fills.

**Config:** instrument_type future, symbol ESH26, timeframe_base 5m, strategy orb_5m, initial_cash 500_000 (futures margin: ~270k for 1 ES @ 5410), FuturesContractSpec from config.

---

## Test Structure

```python
def test_orb_futures_golden():
    """Deterministic ORB backtest. Same input -> same output."""
    config = _golden_orb_config()  # BacktestConfig with futures, 5m, 500k cash
    provider = LocalFileDataProvider(config.data_provider_config)
    strategy = ORBFuturesStrategy(symbol=..., spec=..., qty=1, ...)
    result = run_backtest(config, strategy, provider)

    assert len(result.fills) == 1
    assert len(result.orders) == 1
    for fill in result.fills:
        assert (fill.fill_price * 4) % 1 == 0  # ES tick 0.25
    assert result.equity_curve[-1].equity == pytest.approx(expected, rel=1e-6)
```

Provider config must include `"5m"` in timeframes_supported.

---

## Reproducibility Check

Run twice with same config; assert equity_curve and fills identical. Engine is deterministic; no seed used currently.

---

## Implementation Phases

### Phase 0: Golden data

| Stage | Tasks |
|-------|-------|
| Create | Synthetic ESH26_5m.parquet with OR + breakout bars (see table) |
| Replace | src/loader/tests/fixtures/underlying/ESH26_5m.parquet |
| Ensure | timeframes_supported includes "5m" in provider config |

### Phase 1: Test implementation

| Stage | Tasks |
|-------|-------|
| Implement | test_orb_futures_golden |
| Assert | Fill count, order count, tick alignment, final equity |
| Implement | test_orb_futures_golden_reproducibility (run twice, compare) |

### Phase 2: CI integration

| Stage | Tasks |
|-------|-------|
| Add | pytest marker (golden or integration) |
| Document | How to regenerate ESH26_5m.parquet if scenario changes |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Golden data | Overwrite existing ESH26_5m fixture | Simple path; no extra dirs |
| Assertions | Fill count + equity + tick alignment | ORB entry-only; 0 closed trades |
| initial_cash | 500_000 | 1 ES @ 5410 ≈ 270k; safety margin |
| Regeneration | Manual doc | If bar logic changes, update fixture; rare |

---

## Acceptance Criteria

- [ ] Golden test passes
- [ ] Deterministic (same run twice)
- [ ] Asserts fill count, tick-aligned fills, final equity
- [ ] Fixture data and scenario documented

---

## Open Decisions

| Topic | Options |
|-------|---------|
| Expand scenario | Add exit bar for closed trade assertion; or keep minimal |
| Golden snapshot | Assert values only; or add expected_orb_*.json for diff |

---

## Out of Scope

- Multiple golden scenarios
- Performance benchmarking
- Live data validation
