# 230: Portfolio Accounting

Conforms to [200_portfolio_project_evaluation.md](200_portfolio_project_evaluation.md). Depends on [220](220_portfolio_domain_types.md).

---

## Objective

Implement pure accounting functions: apply_fill, mark_to_market, settle_positions, assert_portfolio_invariants. Identical logic to backtester current implementation with one improvement: multiplier consistency for existing positions.

---

## Deliverables

### accounting.py

#### apply_fill

Port from backtester/src/portfolio/accounting.py lines 18-103.

Signature:

```python
def apply_fill(
    portfolio: PortfolioState,
    fill: FillLike,
    order: OrderLike,
    *,
    multiplier: float = 1.0,
    instrument_type: str = "equity",
) -> PortfolioState:
```

Logic identical to backtester except:
- Default multiplier is 1.0 (not 100.0): equity is the common case for the shared library
- When adding to an existing position (same direction), use existing.multiplier and existing.instrument_type instead of caller-provided values

Handles:
- New position (open)
- Add to existing (same direction): weighted avg price
- Full close (opposite direction, qty goes to 0): realized PnL
- Partial close (opposite direction, qty remains): realized PnL on closed portion
- Flip (opposite direction, qty changes sign): close old, open new remainder

Returns new PortfolioState; never mutates input.

#### mark_to_market

Port from backtester lines 106-130. No changes to logic.

```python
def mark_to_market(
    portfolio: PortfolioState,
    marks: dict[str, float],
) -> PortfolioState:
```

#### settle_positions

Port from backtester settle_expirations (lines 183-220), renamed. No changes to logic except the name.

```python
def settle_positions(
    portfolio: PortfolioState,
    settlements: dict[str, float],
) -> PortfolioState:
```

Takes settlements: dict mapping instrument_id to settlement price. Closes each position at the settlement price, computes realized PnL. Generic: works for options expiry, futures rolls, forced liquidation.

Note: the backtester settle_expirations accepted a ts parameter that was unused in the body. settle_positions drops it.

#### assert_portfolio_invariants

Port from backtester lines 150-180. No changes to logic.

```python
def assert_portfolio_invariants(
    portfolio: PortfolioState,
    marks: dict[str, float] | None = None,
    tolerance: float = 0.01,
) -> None:
```

---

## What stays in backtester

- extract_marks: depends on MarketSnapshot, Quote, QuoteStatus
- _detect_expirations: depends on DataProvider, ContractSpec (options-specific detection)

---

## Multiplier Consistency Detail

Current backtester behavior (potential bug): when adding to an existing LONG position, the caller passes multiplier and instrument_type, but these could differ from what is stored on the existing position. The new implementation:

```python
if (existing.qty > 0) == (signed_qty > 0):
    # Adding to position: use existing multiplier/instrument_type
    mult = existing.multiplier
    itype = existing.instrument_type
    ...
```

For new positions and closes, caller-provided values are used as before.

---

## Verification

- All four functions importable from portfolio
- apply_fill produces identical output to backtester for same inputs (tested in step 240)
- mark_to_market produces identical output
- settle_positions produces identical output to settle_expirations
- assert_portfolio_invariants raises on same conditions

---

## Files

| File | Action |
|------|--------|
| portfolio/src/portfolio/accounting.py | Implement apply_fill, mark_to_market, settle_positions, assert_portfolio_invariants |
