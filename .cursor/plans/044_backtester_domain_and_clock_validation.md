---
name: 044 Domain and Clock Validation
overview: "Integration tests that exercise 030 (domain objects + BacktestConfig) and 040 (Clock iter_times) together. Run via pytest tests/integration/test_domain_clock.py."
todos: []
isProject: false
---

# 044: Domain and Clock Validation

Exercises code from [030_domain_objects_and_config.md](030_domain_objects_and_config.md) and [040_clock_calendar.md](040_clock_calendar.md) to verify integration before Step 3 (DataProvider + MarketSnapshot).

---

## Objective

- **030**: BacktestConfig, Order, Fill, Position, PortfolioState, Event
- **040**: iter_times(start, end, timeframe_base)
- **Integration**: Build BacktestConfig → run iter_times with config params → verify timestamps

---

## Module Layout

```
tests/integration/
  conftest.py
  test_domain_clock.py   # pytest integration tests
```

---

## Run

From project root:

```bash
pytest tests/integration/test_domain_clock.py -v
```

Or all integration tests (excluding network):

```bash
pytest tests/integration -m "not network"
```

---

## Success Criteria

- [x] Creates BacktestConfig from fixtures
- [x] iter_times yields expected counts for 1d, 1h, 1m over a known range
- [x] Determinism: two calls → same sequence
- [x] Config round-trip succeeds
- [x] Sample domain objects created without error
