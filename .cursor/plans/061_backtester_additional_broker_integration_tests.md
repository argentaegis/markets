---
name: 061 Additional Broker Integration Tests
overview: "Add integration tests covering end-to-end Broker-to-Portfolio flow, FeeModel with real fees, mixed valid/invalid batches, multiple contracts, stale quote behavior, and invariant verification."
todos: []
isProject: false
---

# 061: Additional Broker Integration Tests

Recommended integration tests to strengthen Broker coverage, using real DataProvider fixtures in [tests/integration/test_portfolio.py](../tests/integration/test_portfolio.py).

---

## Current Gap Analysis

| Area       | Covered                                             | Gap                                        |
| ---------- | --------------------------------------------------- | ------------------------------------------ |
| FillModel  | Buy at ask, sell at bid, synthetic underlying, qty  | Fees, custom fill_config                   |
| Validation | Unknown instrument, insufficient cash, negative qty | —                                          |
| Pipeline   | Manual fill + apply_fill                            | Broker-produced fill through full pipeline |
| Batch      | Single order                                        | Mixed valid/invalid, multiple contracts    |
| Edge cases | —                                                   | Stale quote, no bar for underlying          |

---

## Recommended Tests

### 1. End-to-End: Broker → Portfolio Pipeline (High Value)

**Name:** `test_broker_submit_then_apply_fill_invariant`

**Purpose:** Verify full flow with real data: `submit_orders` → `apply_fill` → `mark_to_market` → `assert_portfolio_invariants`.

```python
# Flow: submit_orders -> apply_fill for each fill -> mark_to_market -> assert_portfolio_invariants
# Uses real provider, snapshot, portfolio. Fills come from Broker, not hand-constructed.
```

**Why:** Current `test_apply_fill_then_mark_invariant` uses hand-built fills. This validates Broker output drives Portfolio correctly.

---

### 2. FeeModel with Real Fees (High Value)

**Name:** `test_broker_fees_applied_and_deducted`

**Purpose:** Pass `FeeModelConfig(per_contract=0.65, per_order=0.50)` to `submit_orders`. Apply fills; assert `cash = initial - (fill_price * qty * mult) - fees`.

```python
fee_config = FeeModelConfig(per_contract=0.65, per_order=0.50)
fills = submit_orders([order], snapshot, portfolio, symbol="SPY", fee_config=fee_config)
# apply_fill for each; verify fees reduce cash
```

---

### 3. Mixed Batch: Valid and Invalid Orders (Medium Value)

**Name:** `test_broker_mixed_batch_valid_and_rejected`

**Purpose:** `submit_orders([valid_order, invalid_order_unknown, invalid_order_negative_qty])`. Assert exactly one fill with `order_id == valid_order.id`.

**Why:** Ensures Broker correctly skips invalid orders without affecting valid ones.

---

### 4. Multiple Contracts in One Batch (Medium Value)

**Name:** `test_broker_multiple_contracts_in_batch`

**Purpose:** Request quotes for C480 and C485 (both in fixtures). Submit BUY for each. Assert 2 fills with distinct `order_id`s and correct `fill_price` per contract.

**Fixtures:** `SPY|2026-01-17|C|480|100`, `SPY|2026-03-20|C|485|100` have quotes at 14:35.

---

### 5. Stale Quote Produces No Fill (Medium Value)

**Name:** `test_broker_stale_quote_produces_no_fill`

**Purpose:** Order for `SPY|2026-01-10|C|490|10` at ts 2026-01-02 14:35. Fixture has only quote at 2025-12-01 (stale). Assert `submit_orders` returns 0 fills.

**Note:** Behavior depends on provider `max_quote_age`. Conftest uses `max_quote_age=None`; verify whether that yields STALE or different behavior, and document.

---

### 6. Invariant: Every Fill References Valid Order (Low Value)

**Name:** `test_broker_fill_order_id_in_orders`

**Purpose:** After `submit_orders`, assert `all(f.order_id in {o.id for o in orders} for f in fills)`. 000 §6 invariant.

---

### 7. Custom FillModelConfig for Underlying (Low Value)

**Name:** `test_broker_synthetic_spread_config_affects_fill_price`

**Purpose:** Underlying BUY with `FillModelConfig(synthetic_spread_bps=100.0)`. Assert `fill_price > bar.close` by expected half-spread. Verifies config flows through.

---

## Test Placement

Add all to [tests/integration/test_portfolio.py](../tests/integration/test_portfolio.py) under a new section, e.g.:

```markdown
# --- Broker integration (extended) ---
```

---

## Suggested Priority

| Priority | Test                         | Effort                                |
| -------- | ---------------------------- | ------------------------------------- |
| 1        | End-to-end pipeline (#1)     | Low                                   |
| 2        | FeeModel with fees (#2)      | Low                                   |
| 3        | Mixed batch (#3)             | Low                                   |
| 4        | Multiple contracts (#4)      | Low                                   |
| 5        | Stale quote (#5)             | Low (may need fixture/behavior check) |
| 6        | Fill order_id invariant (#6) | Trivial                               |
| 7        | Synthetic spread config (#7) | Low                                   |

---

## Out of Scope (For Later)

- **SELL to open (short)** — Behavior (allow/reject) not fully specified in 000; unit test covers it.
- **No underlying bar** — Would need fixture with missing bar at ts; lower value.
- **Limit orders** — MVP focus is market orders; limit would need FillModel changes.
