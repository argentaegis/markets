# 264: Reporting Analytics Action Plan

Refines the "Most important next step" from [evaluation_output_202502271200.md](evaluation_output_202502271200.md). Incorporates review feedback on annualization, showcase choice, notional precision, and migration path.

---

## 1. Goal of the next step

Upgrade the backtester reporting layer with a **minimal set of risk-adjusted metrics** so results can be discussed credibly in quant/risk interviews.

Add exactly three metrics (Sharpe, CAGR, turnover) plus clearer open-vs-closed trade semantics. No new charts, no engine changes, no parallel analytics system.

---

## 2. Exact repo areas affected

### Prerequisite refactor (do first)
- `backtester/src/reporter/reporter.py` — replace the field-by-field `SummaryMetrics` reconstruction (lines 238-255) with `dataclasses.replace(summary, elapsed_seconds=elapsed_seconds)`. This is a zero-behavior-change refactor that prevents silent field loss when new fields are added.

### Primary
- `backtester/src/reporter/summary.py` — add fields to `SummaryMetrics`, implement computation in `compute_summary`, update `to_dict()` with null handling
- `backtester/src/reporter/visualize.py` — add new metric rows to HTML summary table

### Tests
- `backtester/src/reporter/tests/test_summary.py` — cover new metrics and null/edge-case guards
- `backtester/src/reporter/tests/test_reporter.py` — verify `dataclasses.replace` refactor
- `backtester/src/reporter/tests/test_visualize.py` — verify new fields appear in HTML
- `backtester/tests/integration/test_golden.py` — regenerate golden summaries

### Golden files (regenerate via `--update-golden`)
- `backtester/tests/golden/expected_buy_and_hold_summary.json`
- `backtester/tests/golden/expected_covered_call_summary.json`
- `backtester/tests/golden/expected_covered_call_fees_summary.json`

### Artifacts
- `backtester/runs/showcase/summary.json` and `report.html` — refresh after implementation
- Consider promoting the TAA run as a secondary showcase (see §3 note on showcase)

---

## 3. Acceptance criteria

### Metrics

1. **Sharpe ratio (annualized)** — `mean(step_returns) / std(step_returns) * sqrt(N)` where `N` is inferred from `config.timeframe_base`: `1d` → 252, `1m` → 252×390, `1h` → 252×6.5. Emit `null` when the equity curve has fewer than 20 return observations. Step returns computed as `(equity[i] - equity[i-1]) / equity[i-1]` from the equity curve. Output should note the annualization convention used (e.g. `"sharpe_annualization": "1d/252"`).

2. **CAGR** — `(final_equity / initial_cash) ^ (1 / years) - 1` where `years = (end - start).total_seconds() / (365.25 * 86400)`. Emit `null` when: run spans less than 1 calendar day, or `final_equity <= 0`.

3. **Turnover** — `sum(abs(fill_notional)) / mean(equity)`. Notional per fill: join fill to order via `order_id` to get `instrument_id`, then `fill_notional = fill_price * fill_qty * multiplier` where multiplier comes from `result.instrument_multipliers.get(instrument_id, 1.0)`. Emit `null` when equity curve is empty.

### Open/closed trade clarity

- Add `num_open_positions` field to `SummaryMetrics`: count of positions still held at run end, marked to final price.
- **Keep `num_trades` as-is** (meaning: closed round-trips). This preserves backward compatibility with golden tests and any downstream reader. The new `num_open_positions` field provides the missing context.
- Win/loss stats continue to apply only to closed trades (no change).

### `to_dict()` updates

All new fields (`sharpe`, `cagr`, `turnover`, `num_open_positions`, `sharpe_annualization`) must be added to `to_dict()` with explicit null handling (`None` → JSON `null`).

### HTML report

- Summary table gains rows for Sharpe, CAGR, and Turnover (display `—` when null).
- Trades row shows both closed and open counts: e.g. "199 (W: 137 / L: 62) / 6 open".
- No new charts or visualization layers.

### Showcase note

The ORB showcase (`runs/showcase/`) spans 7 steps / 6 minutes. After this work, Sharpe → null, CAGR → null, Turnover → trivial. The metrics will only be visible in runs with enough data. The TAA run (`runs/202603112204_SPY_1d_20190301_20260310/`) with 1765 daily steps and 199 trades is the natural showcase for these metrics. Consider refreshing it and referencing it in the README as the analytics showcase alongside the existing ORB showcase.

### Verification

- All existing tests pass after changes
- New unit tests cover: normal case, <20 obs → null, zero std → null, <1 day → null, negative equity → null, empty fills → turnover null, multiplier join correctness
- Golden JSON files regenerated via `--update-golden` and committed
- Showcase artifacts refreshed and committed

---

## 4. Deliverables (execution order)

1. **Prerequisite refactor** — `reporter.py`: replace field-by-field `SummaryMetrics` reconstruction with `dataclasses.replace`
2. **Open/closed trade field** — add `num_open_positions` to `SummaryMetrics`; update `compute_summary` and `to_dict()`
3. **Sharpe, CAGR, turnover** — add fields to `SummaryMetrics`; implement computation in `compute_summary` with null guards and multiplier-aware notional
4. **HTML report** — add new metric rows and open count to summary table in `visualize.py`
5. **Unit tests** — extend `test_summary.py` for new metrics, edge cases, null guards; update `test_reporter.py` and `test_visualize.py`
6. **Golden tests** — run `pytest --update-golden`, commit regenerated golden JSON files
7. **Showcase refresh** — refresh ORB showcase; refresh TAA run; update README if adding TAA as analytics showcase
8. **README update** — mention new analytics in `backtester/README.md`

---

## 5. What "done" looks like for interview use

Done means the owner can:
- Point to the TAA run's `summary.json` or `report.html` and say: "Here's return, drawdown, win rate, Sharpe, CAGR, and turnover."
- Explain why the ORB showcase shows null for Sharpe/CAGR (too few observations / sub-day) — this is a feature, not a bug.
- Explain why the TAA run shows 199 closed trades and 6 open positions without cross-referencing `trades.csv`.
- Answer "How volatile or risk-adjusted was that result?" and "Was capital actively deployed?" using the new fields.

---

## 6. What should be deferred until later

- Benchmark comparison, alpha/beta, factor attribution
- Exposure rate (would require per-step cash from engine)
- Sortino, Calmar, or other advanced risk metrics
- New charts or dashboard UI
- Execution-model changes
- New strategies for the sake of more outputs
- Strategizer service entry-point fix (separate work package)
- TAA fee config fix (zero fees over 7 years is a separate credibility issue, not part of this reporting work)

---

## Side note: TAA fee config

The TAA run shows `total_fees: 0.0` across 199 trades over 7 years. This is because the TAA example YAML has no `fee_config`. While not in scope for this plan, adding a realistic fee config to the TAA example would strengthen the credibility of the analytics showcase. Flag for a follow-up.
