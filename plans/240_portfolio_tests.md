# 240: Portfolio Tests

Conforms to [200_portfolio_project_evaluation.md](200_portfolio_project_evaluation.md). Depends on [230](230_portfolio_accounting.md).

---

## Objective

Unit tests for all portfolio domain types and accounting functions. Port relevant tests from backtester to verify parity.

---

## Source Tests

Tests to port from backtester:

| Backtester file | Coverage |
|----------------|----------|
| [src/domain/tests/test_position.py](../backtester/src/domain/tests/test_position.py) | Position creation, field access, instrument_type |
| [src/domain/tests/test_portfolio.py](../backtester/src/domain/tests/test_portfolio.py) | PortfolioState creation, field defaults |
| [src/portfolio/tests/test_accounting.py](../backtester/src/portfolio/tests/test_accounting.py) | apply_fill (open, add, close, partial, flip), mark_to_market, assert_invariants, settle_expirations |

---

## Deliverables

### tests/test_domain.py

- Position: creation with all fields, defaults (multiplier=1.0, instrument_type="equity")
- PortfolioState: creation, field defaults (realized_pnl=0, unrealized_pnl=0, equity=0)
- FillLike/OrderLike: verify backtester-shaped objects satisfy the protocols

### tests/test_accounting.py

#### apply_fill tests

Port from backtester test_accounting.py:
- Open new position (BUY)
- Open new short position (SELL)
- Add to existing position (weighted avg)
- Full close (qty -> 0, realized PnL)
- Partial close
- Short close
- Fees deducted from cash
- **New test**: multiplier consistency — adding to existing position uses position's multiplier, not caller's

#### mark_to_market tests

- Updates unrealized_pnl and equity
- Short position marking
- Missing mark uses cost basis
- Realized PnL unchanged

#### settle_positions tests

Port settle_expirations tests:
- Settle long position at intrinsic value
- Settle short position
- Multiple positions settled
- Position not in portfolio (no-op)

#### assert_portfolio_invariants tests

- NaN detection (cash, equity, pnl)
- qty must be int
- Equity invariant check with marks

---

## Parity Verification

For key tests, use identical inputs and assert identical outputs to backtester. This is the primary acceptance gate: if portfolio produces different results, the adoption (250a/250b) would break backtester tests.

---

## Verification

- `cd portfolio && pytest tests/ -v` — all pass
- No linter errors

---

## Files

| File | Action |
|------|--------|
| portfolio/tests/test_domain.py | Create |
| portfolio/tests/test_accounting.py | Create |
