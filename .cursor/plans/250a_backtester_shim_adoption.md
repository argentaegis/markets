# 250a: Backtester Shim Adoption

Conforms to [200_portfolio_project_evaluation.md](200_portfolio_project_evaluation.md). Depends on [240](240_portfolio_tests.md).

---

## Objective

Add portfolio as a dependency to backtester and create re-export shims so all 39 existing import sites and 83 tests continue to work with zero import changes.

---

## Approach

Replace the *implementations* in backtester's domain/portfolio files with re-exports from the portfolio package. Every existing `from src.domain.portfolio import PortfolioState` still works because the shim file re-exports the same name from the new source.

---

## Deliverables

### 1. Add dependency

In [backtester/pyproject.toml](../backtester/pyproject.toml), add:

```toml
dependencies = [
    ...existing...,
    "portfolio @ file:../portfolio",
]
```

### 2. Install portfolio

```bash
cd portfolio && pip install -e .
cd ../backtester && pip install -e .
```

### 3. Create shims

#### backtester/src/domain/portfolio.py

Replace implementation with re-export:

```python
"""PortfolioState — re-exported from portfolio package (Plan 250a)."""
from portfolio import PortfolioState

__all__ = ["PortfolioState"]
```

#### backtester/src/domain/position.py

Replace implementation with re-export:

```python
"""Position — re-exported from portfolio package (Plan 250a)."""
from portfolio import Position

__all__ = ["Position"]
```

#### backtester/src/portfolio/accounting.py

Replace implementations of apply_fill, mark_to_market, settle_expirations, assert_portfolio_invariants with re-exports. Keep extract_marks in place (it depends on backtester types).

```python
"""Portfolio accounting — shared functions re-exported from portfolio package.
extract_marks stays here (depends on MarketSnapshot/Quote).
"""
from portfolio import (
    apply_fill,
    assert_portfolio_invariants,
    mark_to_market,
    settle_positions as settle_expirations,  # backward compat alias
)

# extract_marks stays: depends on MarketSnapshot, Quote, QuoteStatus
from src.domain.quotes import Quote
from src.domain.snapshot import MarketSnapshot

def extract_marks(snapshot: MarketSnapshot, symbol: str) -> dict[str, float]:
    ...  # existing implementation unchanged
```

Note: `settle_positions` is aliased as `settle_expirations` for backward compatibility. All existing callers continue to work.

#### backtester/src/portfolio/__init__.py

Update to re-export from the shim:

```python
from src.portfolio.accounting import (
    apply_fill,
    assert_portfolio_invariants,
    extract_marks,
    mark_to_market,
    settle_expirations,
)
```

No change needed — it already imports from `src.portfolio.accounting`.

---

## Import Sites (no changes needed)

| Import pattern | Count | Status |
|----------------|-------|--------|
| `from src.domain.portfolio import PortfolioState` | 18 | Works via shim |
| `from src.domain.position import Position` | 12 | Works via shim |
| `from src.portfolio.accounting import ...` | 6 | Works via shim |
| `from src.portfolio import ...` | 3 | Works via __init__.py |
| **Total** | 39 | All unchanged |

---

## Verification

- `cd backtester && pip install -e .` succeeds
- `pytest tests/ -v` — all 83 tests pass
- No import errors
- No linter errors
- Confirm portfolio package types are the actual runtime types: `type(PortfolioState) is portfolio.domain.PortfolioState`

---

## Files

| File | Action |
|------|--------|
| backtester/pyproject.toml | Add portfolio dependency |
| backtester/src/domain/portfolio.py | Replace with re-export shim |
| backtester/src/domain/position.py | Replace with re-export shim |
| backtester/src/portfolio/accounting.py | Replace shared functions with re-exports; keep extract_marks |
