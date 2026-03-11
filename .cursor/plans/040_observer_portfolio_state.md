---
name: 040 Observer Portfolio State
overview: "Add PortfolioState (or equivalent) to observer. Mock implementation for MVP; engine passes portfolio to strategies. Prepare for replacement when observer becomes portfolio-aware."
todos: []
isProject: false
---

# 040: Observer Portfolio State

Conforms to [000_strategizer_mvp_plan.md](000_strategizer_mvp_plan.md) §4.1 and §13.

---

## Objective

Add portfolio state to the observer so strategies can receive a portfolio view. Per 000 §13, use a **mock** portfolio for MVP. Design for replacement when observer becomes portfolio-aware (broker/persistence).

---

## Existing Foundation

- observer/backend: Engine, MarketState, Context, BaseStrategy
- observer/backend/src/state/: context.py, market_state.py
- observer/backend/src/engine/: engine.py

---

## Target Design

### PortfolioState (observer domain)

```python
@dataclass
class PortfolioState:
    cash: float
    positions: dict[str, Position]  # symbol/instrument_id -> Position

@dataclass
class Position:
    instrument_id: str
    qty: int
    avg_price: float
```

Align with backtester domain for future adapter consistency. Observer may extend with `realized_pnl`, `unrealized_pnl`, `equity` when needed.

### MockPortfolio

```python
def create_mock_portfolio() -> PortfolioState:
    """Empty portfolio for MVP. Replace with real source later."""
    return PortfolioState(cash=0.0, positions={})
```

---

## Integration Points

### Engine

- Engine receives portfolio (or portfolio factory) at init
- `evaluate()` builds Context and passes portfolio to strategies
- Strategies that use BaseStrategy today: extend signature to `evaluate(ctx, portfolio)` OR pass portfolio in Context

### Context Extension Option

- Add `portfolio: PortfolioState` to Context
- Engine: `ctx = state.get_context(portfolio=portfolio)`
- Backward compatible: portfolio defaults to mock; existing strategies ignore

---

## Implementation Phases

### Phase 0: Domain types

| Stage | Tasks |
|-------|-------|
| Create | observer/backend/src/core/portfolio.py (or state/portfolio.py): Position, PortfolioState |
| Test | Unit tests for Position, PortfolioState |

### Phase 1: Mock portfolio

| Stage | Tasks |
|-------|-------|
| Create | create_mock_portfolio() or MockPortfolio class |
| Wire | Config: portfolio.source = "mock" |

### Phase 2: Engine integration

| Stage | Tasks |
|-------|-------|
| Extend | Context: add portfolio field (optional, default mock) |
| Extend | MarketState.get_context(): accept portfolio param |
| Extend | Engine.evaluate(): pass portfolio to strategies |
| Extend | BaseStrategy.evaluate(ctx) -> evaluate(ctx, portfolio) with default for backward compat |

### Phase 3: Config

| Stage | Tasks |
|-------|-------|
| Add | config.yaml portfolio section (enabled, source: mock) |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Portfolio in Context vs separate arg | In Context | Single object passed to strategies; Context already has market state |
| Mock implementation | Empty positions, zero cash | Sufficient for MVP; strategies can branch on empty |
| Position shape | Match backtester Position | Facilitates future PortfolioView protocol implementation |
| Backward compatibility | portfolio optional, default mock | Existing strategies (DummyStrategy, ORB) work without changes |

---

## Acceptance Criteria

- [ ] PortfolioState, Position defined in observer
- [ ] Mock portfolio returns empty state
- [ ] Context includes portfolio (or engine passes it)
- [ ] Engine passes portfolio to strategy.evaluate()
- [ ] Existing tests pass (backward compatible)
- [ ] Config documents portfolio.source: mock

---

## Out of Scope

- Real portfolio persistence (SQLite, broker)
- Position updates from fills (observer has no execution)
- PortfolioView protocol implementation (step 050)
