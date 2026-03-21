# Plan 276 — Trade-Level Analytics

## 1. Goal

Add trade-level metrics (avg win/loss, profit factor, expectancy, reward-to-risk ratio, trade duration) to the backtester reporter so that strategy quality can be discussed in interview terms, not just curve-level aggregates.

## 2. Exact Repo Areas Likely Affected

| File | Change |
|------|--------|
| `backtester/src/reporter/summary.py` | Add 6 new metric calculations over existing `closed_trades` list |
| `backtester/src/reporter/visualize.py` | Add new rows to the HTML summary table |
| `backtester/src/reporter/tests/test_summary.py` | Unit tests for each new metric |
| `backtester/README.md` | Add metric definitions to the glossary section |

No new files. No architectural changes. All data already exists in `closed_trades` (entry_price, exit_price, realized_pnl, entry_ts, exit_ts, qty, multiplier).

## 3. Acceptance Criteria

- [ ] `avg_win`: mean realized_pnl of trades where realized_pnl > 0. None if no winners.
- [ ] `avg_loss`: mean realized_pnl of trades where realized_pnl <= 0. None if no losers.
- [ ] `profit_factor`: sum(winning_pnl) / abs(sum(losing_pnl)). None if no losers.
- [ ] `expectancy`: (win_rate × avg_win) + ((1 - win_rate) × avg_loss). None if no closed trades.
- [ ] `reward_risk_ratio`: avg_win / abs(avg_loss). None if no losers.
- [ ] `avg_trade_duration_bars`: mean of (exit_step_index - entry_step_index) across closed trades. None if no closed trades.
- [ ] All 6 metrics appear in summary.json
- [ ] All 6 metrics appear in the HTML report summary table
- [ ] Unit tests cover: normal case, all-winners, all-losers, single-trade, no-closed-trades
- [ ] Metrics glossary in backtester/README.md updated with definitions
- [ ] Showcase run (TAA) regenerated; new summary.json committed with updated values
- [ ] `make test` passes — all 893+ tests green

## 4. What "Done" Looks Like for Interview Use

The owner can open any backtest report and say: "Profit factor is 1.8 — every dollar lost generated $1.80 in winning trades. Win rate is 69% with a 1.5:1 reward-to-risk ratio, giving positive expectancy of $X per trade. Average trade duration is 22 bars." This is the vocabulary quant interviewers expect and currently can't be derived from the project's output without manual calculation.

## 5. What Should Be Deferred Until Later

- Consecutive win/loss streaks
- Per-symbol trade statistics breakdown
- Trade P&L distribution histogram in HTML report
- Monte Carlo simulation of trade sequences
- Sortino ratio, Calmar ratio (separate plan if pursued)
