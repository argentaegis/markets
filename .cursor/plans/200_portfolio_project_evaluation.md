# 200: Portfolio Project Evaluation — Shared Portfolio Library for Markets

## Project Evaluation Summary

### Markets Ecosystem

| Project | Role | Key Dependencies |
|---------|------|------------------|
| **strategizer** | Shared strategy library (leaf) | None |
| **backtester** | Historical simulator | strategizer, exchange-calendars, pandas |
| **observer** | Live futures recommender | strategizer (backend) |

### Current Portfolio State (Duplication)

| Location | Types | Accounting | Notes |
|----------|-------|-------------|-------|
| **backtester** | PortfolioState, Position (multiplier, instrument_type) | apply_fill, mark_to_market, settle_expirations, assert_invariants | Full P&L, mark-to-market, expiration handling |
| **observer** | PortfolioState, Position (minimal) | create_mock_portfolio only | Mock for MVP |
| **strategizer** | PortfolioView (protocol) | — | Consumers implement; no concrete types |

### Gaps

1. **Duplication**: Position/PortfolioState defined twice; accounting logic only in backtester.
2. **Divergence risk**: Observer may add realized_pnl, equity; backtester may evolve; no single source of truth.
3. **Reuse**: Future tools (live broker reconciliation, portfolio API, risk dashboard) would reimplement or depend on backtester.
4. **Strategizer alignment**: PortfolioView protocol expects get_positions, get_cash, get_equity; backtester/observer adapt, but no shared concrete type.

---

## Objective

Create a **portfolio** project: a shared Python library for portfolio state and accounting. Same pattern as strategizer — leaf package, no dependency on observer or backtester. Consumers adopt it and deprecate local implementations.

---

## Scope

### In Scope

- **Domain types**: Position, PortfolioState (cash, positions, realized_pnl, unrealized_pnl, equity)
- **Protocols**: FillLike, OrderLike (duck-typed; backtester Fill/Order already satisfy)
- **Accounting (pure functions)**: apply_fill, mark_to_market, settle_positions (generic settlement), assert_portfolio_invariants
- **Consumers**: backtester (primary), observer (deferred)

### Out of Scope (MVP)

- extract_marks (depends on MarketSnapshot/Quote; stays in backtester)
- Persistence / broker sync
- Multi-currency
- Tax lot tracking (FIFO/LIFO)
- Observer adoption (deferred until observer needs real accounting)

---

## Architecture

### Principle: Leaf Package

Portfolio has **no** dependency on strategizer, backtester, or observer. It is a leaf. Strategizer's PortfolioView is a protocol; portfolio provides a type that satisfies it via duck typing (no import of strategizer).

```
                    ┌─────────────────┐
                    │    portfolio    │  (leaf)
                    │ Position        │
                    │ PortfolioState  │
                    │ apply_fill      │
                    │ mark_to_market  │
                    │ settle_positions│
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼               ▼
       ┌────────────┐ ┌────────────┐  ┌────────────┐
       │ backtester │ │  observer  │  │ future API │
       │ uses       │ │ (deferred) │  │ uses       │
       └────────────┘ └────────────┘  └────────────┘
```

### Domain Types

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
    equity: float = 0.0  # Invariant: cash + sum(mark_value)
```

### Protocols (not dataclasses)

Portfolio uses protocols for Fill and Order so that consumers pass their existing types with zero adapter code. Backtester's Fill and Order already have these attributes.

```python
class FillLike(Protocol):
    fill_price: float
    fill_qty: int
    fees: float

class OrderLike(Protocol):
    instrument_id: str
    side: str  # "BUY" | "SELL"
```

### Accounting Functions (Pure)

```python
def apply_fill(
    portfolio: PortfolioState,
    fill: FillLike,
    order: OrderLike,
    *,
    multiplier: float = 1.0,
    instrument_type: str = "equity",
) -> PortfolioState: ...

def mark_to_market(
    portfolio: PortfolioState,
    marks: dict[str, float],
) -> PortfolioState: ...

def settle_positions(
    portfolio: PortfolioState,
    settlements: dict[str, float],  # instrument_id -> settlement price
) -> PortfolioState: ...

def assert_portfolio_invariants(
    portfolio: PortfolioState,
    marks: dict[str, float] | None = None,
    tolerance: float = 0.01,
) -> None: ...
```

### apply_fill: multiplier consistency

When adding to an existing position, apply_fill uses the position's stored multiplier and instrument_type rather than the caller-provided values. Caller-provided values are only used when creating a new position. This prevents inconsistency and reduces caller burden.

### settle_positions (renamed from settle_expirations)

The settlement math is generic: close position at a given price, compute realized PnL. The detection of *what* has expired (options expiry, futures rolls, forced liquidation) is consumer-specific. Backtester's `_detect_expirations` stays in the engine; it passes the result to `settle_positions`.

### extract_marks stays in backtester

`extract_marks` depends on `MarketSnapshot`, `Quote`, and `QuoteStatus`. These are backtester domain types. It remains in `backtester/src/portfolio/accounting.py` (or moves to the engine).

---

## Package Layout

```
portfolio/
├── pyproject.toml
├── README.md
├── src/
│   └── portfolio/
│       ├── __init__.py
│       ├── domain.py      # Position, PortfolioState
│       ├── protocols.py   # FillLike, OrderLike
│       └── accounting.py  # apply_fill, mark_to_market, settle_positions, assert_invariants
└── tests/
    ├── test_domain.py
    └── test_accounting.py
```

---

## Implementation Steps

| Step | Name | Description |
|------|------|-------------|
| **200** | Evaluation (this doc) | Analysis, decisions, architecture |
| **210** | Package skeleton | pyproject.toml, src layout, empty `__init__.py` |
| **220** | Domain types | Position, PortfolioState; FillLike/OrderLike protocols |
| **230** | Accounting | apply_fill, mark_to_market, settle_positions, assert_invariants |
| **240** | Tests | Port backtester accounting tests; parity verification |
| **250a** | Backtester shim adoption | Add dependency; re-export shims in src.domain.portfolio, src.domain.position, src.portfolio; all tests pass unchanged |
| **250b** | Backtester full migration | Replace imports file-by-file; remove shims; remove old files |
| **260** | Observer adoption (deferred) | When observer needs real accounting; mock-only usage doesn't justify the risk now |

---

## Dependency Order

```
210 (skeleton) -> 220 (domain + protocols) -> 230 (accounting) -> 240 (tests)
                                                -> 250a (backtester shim)
                                                    -> 250b (backtester migration)
```

260 is independent and deferred.

---

## Adoption Notes

### Backtester (Step 250a: Shim)

- Add `portfolio @ file:../portfolio` to pyproject.toml
- Create re-export shims in existing locations:
  - `src/domain/portfolio.py`: `from portfolio import PortfolioState`
  - `src/domain/position.py`: `from portfolio import Position`
  - `src/portfolio/accounting.py`: `from portfolio import apply_fill, mark_to_market, settle_positions, assert_portfolio_invariants`
- All 39 import sites and all tests continue to work with zero changes
- extract_marks stays in backtester (depends on MarketSnapshot/Quote)

### Backtester (Step 250b: Full Migration)

- Replace `from src.domain.portfolio import PortfolioState` with `from portfolio import PortfolioState` across ~22 files
- Replace `from src.portfolio.accounting import ...` with `from portfolio import ...`
- Remove shim files and old implementations
- settle_expirations in engine: rename call to settle_positions
- Incremental: can be done file-by-file with tests passing at each step

### Import Site Count (backtester)

| Import | Files |
|--------|-------|
| `src.domain.portfolio` | 18 |
| `src.domain.position` | 12 |
| `src.portfolio.accounting` / `src.portfolio` | 9 |
| **Total** | ~39 sites across ~22 files |

### Observer (Step 260: Deferred)

Observer uses portfolio in 8 import sites but only for mock (`create_mock_portfolio`). Observer's Position lacks multiplier/instrument_type. Adopting the richer portfolio types adds risk for near-zero benefit. Revisit when observer needs real accounting.

### Strategizer PortfolioView

- portfolio.PortfolioState satisfies PortfolioView via duck typing if it implements get_positions, get_cash, get_equity
- Or: consumer adapters (backtester already has `_BacktesterPortfolioView`)
- No change to strategizer (stays protocol-only)

---

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Fill/Order types | Protocols (FillLike, OrderLike) | Backtester Fill/Order already satisfy; zero adapter code |
| settle_expirations | Include as settle_positions | Settlement math is generic; detection stays in consumer |
| extract_marks | Stays in backtester | Depends on MarketSnapshot, Quote |
| Observer adoption | Deferred | Mock-only usage; not worth the risk now |
| Multiplier in apply_fill | Use existing position's value for additions | Prevents inconsistency between caller and stored state |
| Python version | 3.10+ | Align with strategizer, backtester |
| Dependencies | None for MVP (stdlib + dataclasses) | Leaf package |
| Workspace tooling | Not yet; note for future | Three file:../ path deps is manageable; revisit at four packages |

---

## Acceptance Criteria

- Portfolio package installable (`pip install -e .` from portfolio/)
- apply_fill, mark_to_market, settle_positions produce identical results to current backtester for same inputs
- Backtester tests pass after shim adoption (250a) and after full migration (250b)
- All tests in portfolio/tests pass
