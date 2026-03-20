---
name: 040 Clock Calendar
overview: "Clock/Calendar module for Step 2 of the MVP: iter_times(start, end, timeframe_base) yields bar-close timestamps (UTC), respects market hours, supports 1d/1h/1m. Test-first (Red-Green-Refactor)."
todos: []
isProject: false
---

# 040: Clock / Calendar

Conforms to [000_options_backtester_mvp.md](000_options_backtester_mvp.md) §4 M2 and [001_mvp_implementation_roadmap.md](001_mvp_implementation_roadmap.md) Step 2.

---

## Project Practice: Test-First (Red-Green-Refactor)

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests that specify the expected behavior. Run tests; they fail. |
| **Green** | Implement minimal code to make the tests pass. Run tests; they pass. |
| **Refactor** | Clean up implementation while keeping tests green. |

Each phase uses discrete Red → Green → Refactor stages. No implementation code before tests.

---

## Objective

- **Interface**: `iter_times(start, end, timeframe_base) -> Iterable[datetime]` (000 §4 M2)
- **Responsibilities**: Generate bar-close timestamps; skip non-trading times; support 1d, 1h, 1m
- **Integration**: Consumes `BacktestConfig.start`, `.end`, `.timeframe_base`
- **Alignment**: Bar `ts` = bar close time (UTC) per [010_m1_dataprovider_execution_plan.md](010_m1_dataprovider_execution_plan.md) §3

---

## Interface Contract

```python
def iter_times(
    start: datetime,
    end: datetime,
    timeframe_base: str,
    calendar: ExchangeCalendar | None = None,
) -> Iterator[datetime]:
    """Yield bar-close timestamps for the simulation loop.

    - start, end: inclusive range [start, end]
    - timeframe_base: "1d" | "1h" | "1m"
    - calendar: defaults to NYSE if None
    - All yielded datetimes are timezone-aware UTC
    - Each ts = bar close time (end of interval)
    """
```

---

## Timeframe Rules

| timeframe_base | Bar close | Example (US market) |
|----------------|-----------|---------------------|
| 1d | End of trading day | 2024-01-02 21:00:00 UTC (16:00 ET) |
| 1h | End of each trading hour | 2024-01-02 15:30, 16:30, ... UTC |
| 1m | End of each trading minute | 2024-01-02 14:31, 14:32, ... UTC |

- US market hours: 9:30–16:00 ET
- All timestamps UTC
- Skip non-trading days (weekends, holidays) and outside market hours

---

## Market Calendar

- **MVP**: US equity (NYSE). Use `exchange_calendars` library.
- **Config**: Optional `exchange` in BacktestConfig (default "NYSE"); future swap path documented.

---

## Module Layout

```
src/clock/
  __init__.py    # exports iter_times
  clock.py       # iter_times implementation
  tests/
    __init__.py
    test_iter_times.py
```

---

## Implementation Phases

### Phase 1: iter_times for 1d (trading days)

| Stage | Tasks | Status |
|-------|-------|--------|
| **Red** | Write `src/clock/tests/test_iter_times.py`: tests for 1d — trading days only in [start, end], inclusive; empty range when no sessions; determinism; timestamps UTC | Done |
| **Green** | Add `exchange_calendars` to pyproject.toml; implement `iter_times` for 1d using NYSE calendar | Done |
| **Refactor** | Extract calendar selection if needed | — |

### Phase 2: iter_times for 1h and 1m (intraday)

| Stage | Tasks | Status |
|-------|-------|--------|
| **Red** | Write tests: 1h yields hourly bar closes within market hours; 1m yields minute bar closes | Done |
| **Green** | Extend `iter_times` to handle 1h and 1m | Done |
| **Refactor** | Share logic between timeframes | — |

### Phase 3: Configuration and integration

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: optional `exchange` in config; invalid timeframe_base raises |
| **Green** | Wire to BacktestConfig; validate timeframe_base |
| **Refactor** | Document engine usage |

---

## Acceptance Criteria

- [x] `iter_times(start, end, "1d")` yields trading-day bar closes in [start, end], UTC
- [x] `iter_times` for 1h, 1m yields intraday bar closes
- [x] Empty range when no trading sessions
- [x] Determinism: same inputs → identical sequence (A5)
- [x] Unit tests in `src/clock/tests/`; all pass
