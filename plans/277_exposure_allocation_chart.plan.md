# Plan 277 — Exposure & Allocation-Over-Time Chart

## 1. Goal

Add an allocation-over-time stacked area chart to the HTML report so that multi-asset strategies (especially the flagship TAA) can be visually explained in interviews. A reviewer should be able to see *what* the strategy was holding at any point — not just the aggregate equity curve.

## 2. Exact Repo Areas Likely Affected

| File | Change |
|------|--------|
| `backtester/src/reporter/visualize.py` | Add Plotly stacked area chart (allocation weight per symbol over time) |
| `backtester/src/reporter/reporter.py` | Pass per-symbol position data to visualize; may need to record per-symbol equity at each step |
| `backtester/src/engine/engine.py` | Record per-symbol position value in equity curve data (currently only aggregate equity is tracked) |
| `backtester/src/reporter/summary.py` | Add `net_exposure` and `gross_exposure` to summary.json |
| `backtester/src/reporter/tests/test_summary.py` | Tests for exposure metrics |
| `backtester/tests/integration/test_reporter.py` | Verify chart renders for multi-symbol and single-symbol runs |

## 3. Acceptance Criteria

- [ ] Engine records per-symbol position value at each equity curve step (dict[str, float])
- [ ] `net_exposure`: sum of signed position values / equity at final step. Added to summary.json.
- [ ] `gross_exposure`: sum of abs(position values) / equity at final step. Added to summary.json.
- [ ] HTML report includes stacked area chart showing allocation weight (% of equity) per symbol over time, only when num_symbols > 1
- [ ] Single-symbol runs: chart not shown (or shows single-color area — no visual regression)
- [ ] TAA showcase run regenerated with new chart; visually shows entry/exit of ETFs over 7-year window
- [ ] Chart uses consistent color palette across symbols
- [ ] `make test` passes

## 4. What "Done" Looks Like for Interview Use

The owner can open the TAA report, point to the allocation chart, and say: "In March 2020, the strategy moved to 80% cash as 5 of 6 ETFs fell below their 200-day SMA. By June it re-entered equities as the trend recovered. You can see TLT maintained its allocation throughout — acting as the defensive sleeve." This transforms the TAA from an abstract Sharpe number into a visual story.

## 5. What Should Be Deferred Until Later

- Sector-level exposure grouping
- Rolling exposure metrics (exposure over time as a line chart)
- Leverage tracking / margin utilization
- Per-symbol Sharpe or risk contribution breakdown
- Benchmark overlay on allocation chart
