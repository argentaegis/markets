# 220: Portfolio Domain Types

Conforms to [200_portfolio_project_evaluation.md](200_portfolio_project_evaluation.md). Depends on [210](210_portfolio_skeleton.md).

---

## Objective

Define Position, PortfolioState, FillLike, and OrderLike in the portfolio package.

---

## Deliverables

### domain.py: Position and PortfolioState

```python
@dataclass
class Position:
    instrument_id: str
    qty: int
    avg_price: float
    multiplier: float = 1.0
    instrument_type: str = "equity"  # "equity" | "option" | "future"

@dataclass
class PortfolioState:
    cash: float
    positions: dict[str, Position]
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    equity: float = 0.0
```

These match the backtester existing types exactly:
- backtester/src/domain/position.py: Position with instrument_id, qty, avg_price, multiplier, instrument_type
- backtester/src/domain/portfolio.py: PortfolioState with cash, positions, realized_pnl, unrealized_pnl, equity

### protocols.py: FillLike and OrderLike

```python
class FillLike(Protocol):
    fill_price: float
    fill_qty: int
    fees: float

class OrderLike(Protocol):
    instrument_id: str
    side: str  # "BUY" | "SELL"
```

Backtester existing types satisfy these protocols with zero changes:
- backtester/src/domain/fill.py: Fill has fill_price, fill_qty, fees (plus order_id, ts, liquidity_flag)
- backtester/src/domain/order.py: Order has instrument_id, side (plus id, ts, qty, order_type, limit_price, tif, trailing_stop_ticks)

---

## Design Notes

### Why not frozen dataclasses?

Backtester PortfolioState is mutable (replaced, not mutated, but still a regular dataclass). Position is also a regular dataclass. Matching existing behavior avoids adoption friction.

### Why protocols instead of concrete Fill/Order types?

Backtester already has Fill and Order with extra fields (order_id, ts, order_type, etc.). Defining FillLike/OrderLike as protocols means apply_fill accepts backtester types directly. No adapter, no field extraction, no new types to construct.

---

## Verification

- `from portfolio import Position, PortfolioState` works
- `from portfolio import FillLike, OrderLike` works
- Position and PortfolioState field names and defaults match backtester existing types

---

## Files

| File | Action |
|------|--------|
| portfolio/src/portfolio/domain.py | Implement Position, PortfolioState |
| portfolio/src/portfolio/protocols.py | Implement FillLike, OrderLike |
| portfolio/src/portfolio/__init__.py | Update re-exports |
