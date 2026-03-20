# 250b: Backtester Full Migration

Conforms to [200_portfolio_project_evaluation.md](200_portfolio_project_evaluation.md). Depends on [250a](250a_backtester_shim_adoption.md).

---

## Objective

Replace all backtester imports of portfolio types from shim paths (`src.domain.portfolio`, `src.domain.position`, `src.portfolio`) with direct imports from the portfolio package. Remove shim files when done.

---

## Approach

Incremental, file-by-file. Run tests after each batch. Can be done in one pass or spread across commits.

---

## Migration Map

### PortfolioState imports (18 sites)

Replace `from src.domain.portfolio import PortfolioState` with `from portfolio import PortfolioState`:

| File |
|------|
| src/engine/engine.py |
| src/strategies/strategizer_adapter.py |
| src/broker/trailing_stop.py |
| src/broker/broker.py |
| src/broker/tests/test_trailing_stop.py |
| src/broker/tests/test_validation.py |
| src/broker/tests/test_broker.py |
| src/engine/tests/test_engine.py |
| src/engine/tests/test_strategy.py |
| src/engine/result.py |
| src/engine/tests/test_result.py |
| src/portfolio/accounting.py (extract_marks) |
| tests/integration/test_reporter.py |
| tests/integration/test_engine.py |
| tests/integration/test_portfolio.py |
| tests/integration/test_broker.py |
| tests/integration/test_domain_clock.py |
| src/domain/tests/test_portfolio.py |

### Position imports (12 sites)

Replace `from src.domain.position import Position` with `from portfolio import Position`:

| File |
|------|
| src/portfolio/accounting.py |
| src/portfolio/tests/test_accounting.py |
| src/broker/tests/test_trailing_stop.py |
| src/broker/tests/test_validation.py |
| src/engine/tests/test_engine.py (7 inline imports) |
| tests/integration/test_portfolio.py |
| tests/integration/test_broker.py |
| tests/integration/test_domain_clock.py |
| src/domain/tests/test_position.py |
| src/domain/tests/test_portfolio.py |

### Accounting imports (9 sites)

Replace `from src.portfolio.accounting import ...` / `from src.portfolio import ...` with `from portfolio import ...`:

| File | Current import |
|------|---------------|
| src/engine/engine.py | `from src.portfolio.accounting import apply_fill, assert_portfolio_invariants, extract_marks, mark_to_market, settle_expirations` |
| src/broker/broker.py | `from src.portfolio.accounting import extract_marks` |
| src/portfolio/__init__.py | `from src.portfolio.accounting import ...` |
| src/portfolio/tests/test_accounting.py | `from src.portfolio.accounting import ...` |
| tests/integration/test_portfolio.py | `from src.portfolio import ...` |
| tests/integration/test_broker.py | `from src.portfolio import ...` |

Note: `extract_marks` stays in backtester. Engine and broker import it from a backtester-local module.

### settle_expirations -> settle_positions rename

In [src/engine/engine.py](../backtester/src/engine/engine.py), the call to `settle_expirations(portfolio, ts, expired)` becomes `settle_positions(portfolio, expired)`. Note: `settle_positions` does not take `ts` (the original `settle_expirations` accepted `ts` but did not use it for anything except the signature).

---

## Cleanup

After all imports are migrated:

- Delete `backtester/src/domain/portfolio.py` (shim)
- Delete `backtester/src/domain/position.py` (shim)
- Move `extract_marks` to `backtester/src/engine/marks.py` or keep in a reduced `backtester/src/portfolio/marks.py`
- Update `backtester/src/portfolio/__init__.py` to only export `extract_marks`
- Delete backtester domain tests that are now covered by portfolio package tests (test_position.py, test_portfolio.py)

---

## Verification

- `pytest tests/ -v` — all 83 tests pass after each migration batch
- No remaining imports from `src.domain.portfolio` or `src.domain.position`
- `grep -r "from src.domain.portfolio" src/ tests/` returns nothing
- `grep -r "from src.domain.position" src/ tests/` returns nothing
- No linter errors

---

## Files

| File | Action |
|------|--------|
| ~22 backtester source/test files | Update imports |
| src/domain/portfolio.py | Delete (shim) |
| src/domain/position.py | Delete (shim) |
| src/portfolio/accounting.py | Reduce to extract_marks only |
| src/portfolio/__init__.py | Update exports |
