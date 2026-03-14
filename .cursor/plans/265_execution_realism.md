# Plan 265 — Execution Realism: Next-Bar-Open Fills and Cost Model

*Refined from `evaluation_output_202502271430.md`. Strategizer doc fix is done. This targets the remaining Medium-severity gap: execution realism.*

---

## 1. Goal of the next step

Move execution simulation from "visibly simplified" to "defensible and documented" by addressing the two most interview-visible weaknesses:

1. **Fill timing**: Market/limit orders currently fill at the same bar's close where the signal fires. This is a subtle execution lookahead — in practice, a signal computed from bar-close data cannot fill at that bar's close. Add a `fill_timing: next_bar_open` mode where orders are queued and filled at the next bar's open.

2. **Equity cost model**: The fee model only supports `per_contract + per_order`, which is options-centric. Extend it to support `pct_of_notional` (basis-point spread/slippage cost), which is the standard way to model equity execution costs. Apply it to the TAA showcase.

The combination lets the project demonstrate awareness of execution-timing bias and realistic cost assumptions — two topics a quant reviewer is very likely to probe.

---

## 2. Exact repo areas likely affected

### A. Next-bar-open fill timing

| Area | Change |
|------|--------|
| `backtester/src/engine/engine.py` | Add pending-order queue. When `fill_timing == "next_bar_open"`, orders from step N are held and filled against step N+1's bar open. Trailing stops and stop orders that trigger on intrabar levels should continue to use current-bar logic (they already reference bar.high/low, not close). |
| `backtester/src/broker/fill_model.py` | Add `fill_at_open(order, snapshot)` path: use `bar.open` instead of `bar.close` as mid for synthetic spread. Existing `fill_order` can accept a `use_open: bool` parameter or a separate function. |
| `backtester/src/domain/config.py` | Add `fill_timing: str = "same_bar_close"` to `BacktestConfig`. Valid values: `"same_bar_close"` (default, backward-compatible) and `"next_bar_open"`. Serialize/deserialize for manifest. |
| `backtester/src/runner.py` | Parse `fill_timing` from YAML config. Also parse `fill_config` (currently not wired from YAML — existing gap). |

### B. Equity cost model

| Area | Change |
|------|--------|
| `backtester/src/broker/fee_model.py` | Add optional `pct_of_notional: float = 0.0` to `FeeModelConfig`. `compute_fees` adds `pct_of_notional * abs(fill_price * fill_qty * multiplier)` to existing per-contract + per-order fees. When multiplier is not available at fee-computation time, use 1.0 (equity default). |
| `backtester/src/broker/broker.py` | Pass multiplier to `compute_fees` so pct-of-notional can use it. |
| `backtester/src/domain/config.py` | Serialize/deserialize `pct_of_notional` in fee config. |
| `backtester/src/runner.py` | Parse `pct_of_notional` from YAML `fee_config` block. |

### C. TAA showcase and docs

| Area | Change |
|------|--------|
| `backtester/configs/tactical_asset_allocation_example.yaml` | Add `fill_timing: next_bar_open` and `fee_config: { pct_of_notional: 0.001 }` (10 bps round-trip spread cost — a common equity backtest assumption). |
| TAA run artifacts | Regenerate run. Summary will show non-zero `total_fees` and fill timing in manifest. |
| `backtester/README.md` | Update "Modeled today" section to mention next-bar-open fill timing and basis-point cost model. Update "Still simplified" to reflect what remains. |

---

## 3. Acceptance criteria

- [ ] `BacktestConfig` supports `fill_timing` field; default `"same_bar_close"` preserves all existing behavior
- [ ] Engine queues orders and fills at next bar's open when `fill_timing == "next_bar_open"`
- [ ] `fill_model.py` can fill at bar open (not just close) for underlying/equity orders
- [ ] `FeeModelConfig` supports `pct_of_notional`; `compute_fees` uses it when set
- [ ] `runner.py` parses both `fill_timing` and `fill_config` (including `pct_of_notional`) from YAML
- [ ] All existing tests pass unchanged (default fill_timing = same_bar_close)
- [ ] New unit tests for next-bar-open fill timing (at least: orders queue, fill at next step's open, final-step orders unfilled)
- [ ] New unit tests for pct_of_notional fee calculation
- [ ] TAA config uses `fill_timing: next_bar_open` and `fee_config: { pct_of_notional: 0.001 }`
- [ ] TAA run shows `total_fees > 0` and `fill_timing` in run_manifest
- [ ] `backtester/README.md` updated
- [ ] `make test` passes

---

## 4. What "done" looks like for interview use

**Before**: "Fills happen at bar close — isn't that lookahead?" / "No fees on the equity showcase?"

**After**: "The engine supports configurable fill timing. The default is same-bar-close for simplicity, but the TAA showcase uses next-bar-open to avoid execution lookahead. Equity costs are modeled as basis-point spread cost — 10 bps round-trip, configurable per run. The fill model and cost model are documented in the README with explicit notes on what remains simplified."

This demonstrates:
- Awareness of execution-timing bias (a common interview question)
- Realistic cost modeling for equities (not options-style per-share fees)
- Configuration-driven assumptions (different runs can use different models)
- Honesty about remaining simplifications

---

## 5. Design notes

### Next-bar-open: engine changes

The engine loop currently does: `snapshot → strategy → orders → fill → mark → record`. For next-bar-open:

```
step N:   snapshot(N) → strategy → orders(N) → [queue orders(N)] → fill pending_orders(N-1) at bar(N).open → mark → record
step N+1: snapshot(N+1) → strategy → orders(N+1) → [queue orders(N+1)] → fill pending_orders(N) at bar(N+1).open → mark → record
```

Key decisions:
- Orders from the final step that cannot fill (no next bar) are simply unfilled — consistent with "position open at run end" semantics
- Stop orders should remain current-bar (they use intrabar high/low, not close); only market/limit orders queue
- Trailing stop fills (already evaluated separately) are unaffected
- `fill_timing` is a run-level setting, not per-order

### Pct-of-notional fee: why this model

- Equity execution cost is dominated by spread, not commissions (which are zero at most retail brokers)
- 10 bps round-trip is a common institutional equity backtest assumption
- `pct_of_notional` composes with existing `per_contract + per_order` (options runs can use both)
- The multiplier (1.0 for equity, 50.0 for ES futures, 100.0 for options) ensures notional is correct across instrument types

---

## 6. What should be deferred until later

- Partial fills or market-impact models
- VWAP / TWAP execution simulation
- Broker-grade margin logic
- Sortino, Calmar, or additional risk metrics
- Adding fill_timing to other example configs (leave them on default)
- Per-instrument or per-strategy cost configurations

---

## Reference

- Evaluation: `.cursor/plans/evaluation_output_202502271430.md` (gap: "Execution realism remains baseline", Medium severity)
- Engine loop: `backtester/src/engine/engine.py` lines 269–355
- Fill model: `backtester/src/broker/fill_model.py`
- Fee model: `backtester/src/broker/fee_model.py`
- Config: `backtester/src/domain/config.py`, `backtester/src/runner.py`
- TAA config: `backtester/configs/tactical_asset_allocation_example.yaml`
