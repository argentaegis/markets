# Portfolio

Shared portfolio state and accounting package for the markets repo.

This package is intentionally small and focused: it owns position state, cash/equity accounting, mark-to-market updates, settlement, and invariant checks. `backtester/` imports it directly so portfolio logic stays isolated from strategy and execution code.

## Install

```bash
pip install -e .
```

## Public API

The main exports are:

- `PortfolioState`
- `Position`
- `apply_fill()`
- `mark_to_market()`
- `settle_positions()`
- `assert_portfolio_invariants()`

## What It Does

- applies fills to long or short positions
- tracks cash, realized P&L, unrealized P&L, and total equity
- marks positions to current prices
- settles positions at explicit settlement prices
- validates basic accounting invariants

## Typical Usage

```python
from portfolio import PortfolioState, apply_fill, mark_to_market
```
