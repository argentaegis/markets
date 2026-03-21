# Plan 278 — Change Default fill_timing to next_bar_open

## 1. Goal

Change the default `fill_timing` from `same_bar_close` to `next_bar_open` so that new configs are safe-by-default against lookahead bias. Existing configs that intentionally use same_bar_close become explicit.

## 2. Exact Repo Areas Likely Affected

| File | Change |
|------|--------|
| `backtester/src/domain/config.py` | Change default: `fill_timing: str = "next_bar_open"` |
| `backtester/configs/*.yaml` | Audit all configs. Any that should keep same_bar_close must set it explicitly. Any that already set next_bar_open: no change needed |
| `backtester/README.md` | Update modeling assumptions section to note next_bar_open is now the default. Explain same_bar_close is available for benchmarking/comparison |
| `backtester/src/domain/tests/test_config.py` | Update test that checks default fill_timing value |
| `backtester/tests/integration/test_engine.py` | Verify integration tests still pass (they may construct configs explicitly) |

## 3. Acceptance Criteria

- [ ] `BacktestConfig.fill_timing` defaults to `"next_bar_open"` in config.py
- [ ] All YAML configs in `backtester/configs/` audited:
  - Configs that already specify `fill_timing: next_bar_open` — no change
  - Configs that don't specify fill_timing — verify they work correctly with new default
  - Any config that needs same_bar_close for a reason (e.g., options where fill is at quote time) — add explicit `fill_timing: same_bar_close` with a comment explaining why
- [ ] `test_config.py` updated to assert default is `"next_bar_open"`
- [ ] All integration tests pass with new default
- [ ] Backtester README updated: "Default fill timing is next_bar_open (orders placed on bar N fill at bar N+1 open). Set fill_timing: same_bar_close for strategies where decision and execution are genuinely simultaneous."
- [ ] Showcase TAA run unaffected (already uses next_bar_open explicitly)
- [ ] `make test` passes — all 893+ tests green

## 4. What "Done" Looks Like for Interview Use

A code reviewer who reads config.py sees that the default prevents lookahead bias. The owner can explain: "Fill timing defaults to next-bar-open — the strategy decides on bar N's close and fills at bar N+1's open, which models the realistic latency between decision and execution. Same-bar-close is available for specific use cases but requires an explicit opt-in."

## 5. What Should Be Deferred Until Later

- VWAP fill model (fill at volume-weighted average of next bar)
- Configurable fill delay (N bars instead of just 0 or 1)
- Partial fills / fill probability model
- Market impact as a function of order size
- Intraday fill timing for sub-daily bars (e.g., fill at next bar's mid-point)
