# 262: Reporting Analytics Work Package

Refines the "Most important next step" from [evaluation_output_202603111457.md](evaluation_output_202603111457.md) into the smallest concrete work package that materially improves project credibility for quant, risk, and analytics interviews.

---

## 1. Goal of the next step

Upgrade the backtester reporting layer from basic simulation output to a small, interview-grade analytics package.

This work package should:
- Add a few **high-signal performance metrics** that help a reviewer evaluate results more credibly
- Make **open vs. closed trade reporting** easier to interpret
- Improve the quality of the repo's results discussion **without** turning the project into a full analytics platform

This is not a dashboard rewrite. It is a focused credibility upgrade for result interpretation.

---

## 2. Exact repo areas affected

### Primary implementation areas
- `backtester/src/reporter/summary.py`
- `backtester/src/reporter/reporter.py`
- `backtester/src/reporter/visualize.py`

### Tests
- `backtester/src/reporter/tests/test_summary.py`
- `backtester/src/reporter/tests/test_reporter.py`
- `backtester/src/reporter/tests/test_visualize.py`
- `backtester/tests/integration/test_golden.py` — golden summary JSON files **must** be regenerated

### Golden files (regenerate via `--update-golden`)
- `backtester/tests/golden/expected_buy_and_hold_summary.json`
- `backtester/tests/golden/expected_covered_call_summary.json`
- `backtester/tests/golden/expected_covered_call_fees_summary.json`

### Documentation / artifact layer
- `backtester/README.md`
- `backtester/runs/showcase/summary.json` and `backtester/runs/showcase/report.html` — **must** be refreshed after metric additions

### Evidence that drives the change
- `backtester/src/reporter/summary.py` currently exposes only return, drawdown, win rate, fees, and trade counts
- `backtester/src/reporter/visualize.py` already distinguishes open trades in the HTML report, which should be reflected more clearly in the summary layer
- `backtester/runs/showcase/summary.json` currently shows `num_trades: 0` even though the run contains a marked open trade in `trades.csv`

---

## 3. Acceptance criteria

### Metrics

`summary.json` gains exactly three new analytics fields:

1. **Sharpe ratio** — non-annualized: `mean(step_returns) / std(step_returns)`. Emit `null` when the equity curve has fewer than 20 return observations. Non-annualized is more honest for short backtests and avoids the need to choose an annualization factor that depends on bar frequency.

2. **CAGR** — `(final_equity / initial_cash) ^ (1 / years) - 1` where `years = (end - start).total_seconds() / (365.25 * 86400)`. Emit `null` when the run spans less than 1 calendar day, since annualizing sub-day returns produces meaningless numbers.

3. **Turnover** — `sum(abs(fill_notional)) / mean(equity)`. Measures how actively capital was deployed. Computable entirely from existing `result.fills` and `result.equity_curve` data. *Not* exposure rate, which would require per-step cash data that `BacktestResult` does not currently store (engine-level change, out of scope).

All three are deterministically computed from existing run outputs. No new engine-level data is required.

### Open vs. closed trade clarity

New fields in `SummaryMetrics`:
- `num_closed_trades` — closed round-trips used for win/loss stats (replaces the current `num_trades` semantically)
- `num_open_positions` — positions still held at run end, marked to final price
- Retain `num_trades` as `num_closed_trades + num_open_positions` for total visibility

A reviewer looking at `summary.json` should immediately understand why the showcase run has zero closed trades but one open position, without needing to cross-reference `trades.csv`.

### HTML report
- The summary table surfaces Sharpe, CAGR, and turnover in the existing summary section (new rows, no new chart)
- Open/closed counts are shown clearly (e.g. "Trades: 0 closed / 1 open")
- The report preserves its current lightweight character; no new large visualization layer

### Verification
- Reporter unit tests cover the new metrics and edge cases (short window → `null`, zero std → `null`, etc.)
- All 3 golden JSON files regenerated via `--update-golden` and committed
- Existing reporter, integration, and golden tests pass
- Showcase run refreshed and committed

---

## 4. Prerequisite refactor

`generate_report` in `reporter.py` currently reconstructs the entire `SummaryMetrics` dataclass field-by-field to inject `elapsed_seconds`:

```python
if elapsed_seconds is not None:
    summary = SummaryMetrics(
        initial_cash=summary.initial_cash,
        final_equity=summary.final_equity,
        # ... every field repeated ...
    )
```

Adding new fields makes this pattern fragile — any new field omitted here is silently dropped. **First step**: replace this with `dataclasses.replace(summary, elapsed_seconds=elapsed_seconds)`. This is a zero-behavior-change refactor that unblocks safe field additions.

---

## 5. Deliverables (execution order)

1. **Prerequisite refactor** — replace field-by-field `SummaryMetrics` reconstruction in `reporter.py` with `dataclasses.replace`
2. **Open/closed trade fields** — add `num_closed_trades`, `num_open_positions` to `SummaryMetrics`; update `compute_summary`; update `to_dict`
3. **Sharpe, CAGR, turnover** — add fields to `SummaryMetrics`; implement computation in `compute_summary` with null guards
4. **HTML report** — add new metric rows and open/closed counts to summary table in `visualize.py`
5. **Unit tests** — extend `test_summary.py` for new metrics, edge cases, null guards; update `test_reporter.py` and `test_visualize.py` for new fields
6. **Golden tests** — run `pytest --update-golden`, commit regenerated golden JSON files
7. **Showcase refresh** — re-run the showcase backtest, commit updated `summary.json` and `report.html`
8. **README update** — mention new analytics in `backtester/README.md` showcase section

---

## 6. What "done" looks like for interview use

Done means a reviewer can:
1. Open `summary.json` or `report.html` and see more than raw return and win rate
2. Understand whether the run had closed trades, open marked positions, or both
3. Hear the owner explain results using a small but credible analytics vocabulary rather than only simulator output
4. Leave with the impression that the project evaluates strategies, not just executes them

In practical interview terms, "done" means the owner can answer:
- Was the strategy profitable?
- How volatile or risk-adjusted was that result?
- Was capital actually deployed or was performance driven by a tiny number of trades?
- Why does the run show an open position but zero closed trades?

without hand-waving around the current reporting limitations.

---

## 7. What should be deferred until later

Defer these until after this reporting work package is complete:
- Benchmark comparison, alpha/beta, or attribution
- Multi-strategy portfolio analytics
- Exposure rate (requires per-step cash data — engine-level change)
- A large report UI redesign
- Advanced charting beyond small additions to the existing HTML summary
- Execution-model changes unrelated to how results are presented
- New strategies added only to show more outputs

---

## Why this should be next

The repo narrative, showcase artifact, and monorepo workflow are now mostly in place. The next credibility gain is not more architecture work. It is making the project's results easier to evaluate in the way a quant, risk, or analytics reviewer expects.

This is the smallest meaningful improvement because it strengthens interview discussion directly while staying within the existing reporter pipeline and avoiding a large scope jump.
