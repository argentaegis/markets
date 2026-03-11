# 260: Observer Adoption (Deferred)

Conforms to [200_portfolio_project_evaluation.md](200_portfolio_project_evaluation.md).

---

## Status: Deferred

Observer adoption is deferred until observer needs real portfolio accounting. Current usage is mock-only.

---

## Rationale

Observer uses portfolio in 8 import sites across 7 files:

| File | Usage |
|------|-------|
| backend/src/engine/engine.py | PortfolioState, create_mock_portfolio |
| backend/src/api/app.py | create_mock_portfolio |
| backend/src/state/context.py | PortfolioState, create_mock_portfolio |
| backend/src/state/market_state.py | PortfolioState |
| backend/src/core/__init__.py | Position, PortfolioState, create_mock_portfolio |
| backend/tests/unit/core/test_portfolio.py | Position, PortfolioState, create_mock_portfolio |
| backend/tests/unit/state/test_context.py | Position, PortfolioState, create_mock_portfolio |
| backend/tests/unit/state/test_market_state.py | Position, PortfolioState |

All usage is either:
- `create_mock_portfolio()` which returns `PortfolioState(cash=0.0, positions={})`
- Type annotations referencing PortfolioState or Position

Observer's Position is minimal (instrument_id, qty, avg_price) — no multiplier or instrument_type. Adopting the richer portfolio package Position adds fields observer doesn't use. Not harmful, but not helpful either.

---

## When to Revisit

Adopt when any of these occur:
1. Observer needs `apply_fill` or `mark_to_market` (real portfolio accounting)
2. Observer adds a broker integration that produces fills
3. A shared API or dashboard needs consistent portfolio types across observer and backtester

---

## Adoption Plan (for when ready)

1. Add `portfolio @ file:../portfolio` to observer/backend/pyproject.toml
2. Replace `from core.portfolio import Position, PortfolioState` with `from portfolio import Position, PortfolioState`
3. Keep `create_mock_portfolio` in observer as a thin wrapper or move to portfolio as a factory
4. Update 8 import sites across 7 files
5. Delete `observer/backend/src/core/portfolio.py`
6. Run observer tests

---

## Files (no changes now)

No files modified in this step.
