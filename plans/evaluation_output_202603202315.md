# Project Evaluation — 2026-03-20

## 1. Executive Assessment

- **Maturity:** The project is a well-architected, config-driven backtesting engine with 4 cleanly separated sub-projects (backtester, strategizer, portfolio, observer), 7 strategies spanning options/equities/futures, 893 passing tests, and a flagship TAA showcase with honest benchmark comparison
- **Credibility:** Strong as a quant-finance demo. Architecture is production-quality (protocol-driven interfaces, frozen dataclasses, zero circular dependencies, pure-function accounting). The project communicates rigor over hype
- **Strongest parts:** Architecture and code organization (excellent separation of concerns, extensible strategy ABC, dependency injection throughout); reproducibility (config-driven, run manifests with git hash, deterministic execution); honest scope control (limitations documented, benchmark comparison unflattering but included)
- **Weakest parts:** Missing standard trade-level analytics (profit factor, expectancy, avg win/loss); no exposure tracking (net/gross notional, allocation over time); no walk-forward or out-of-sample validation; no dividend/split handling for equities; default fill_timing is same_bar_close (lookahead risk unless opt-in to next_bar_open)
- **Overall verdict:** **"Credible but incomplete"** — strong enough for interviews today, with clear opportunities to move to "strong for interviews" by closing 2-3 specific gaps

## 2. Current-State Evidence Table

| Area | Status | Evidence Found | Why It Matters |
|------|--------|---------------|----------------|
| **Architecture & modularity** | Strong | 4 sub-projects, zero circular imports, Strategy ABC + registry, DataProvider ABC, protocol-based portfolio views, frozen dataclasses. Engine.py 486 lines orchestrates clean pipeline: config → data → signal → execution → report | Clean architecture is the #1 thing quant hiring managers look for in portfolio projects; proves the candidate can design systems, not just write scripts |
| **Financial realism: fees** | Strong | 5 broker fee schedules (IBKR, IBKR equity spread, TD, Schwab, zero) with per-contract + per-order + pct_of_notional model. Multiplier-aware. Configurable per run | Realistic fees show domain awareness; zero-fee backtests are a red flag |
| **Financial realism: slippage** | Partial | 50 bps synthetic spread when bid=ask; quote-based fills (buy@ask, sell@bid) when available. Configurable `synthetic_spread_bps` | Adequate for demo but no volume-dependent or moneyness-dependent spread modeling |
| **Financial realism: fill timing** | Partial | Dual mode: `same_bar_close` (default) and `next_bar_open` (opt-in). Flagship TAA uses next_bar_open. Strategy receives only current snapshot via on_step() | Default same_bar_close is a known lookahead risk; having the opt-in is good but default should be safer |
| **Financial realism: instruments** | Strong | Options: 100x multiplier, expiration detection with intrinsic value, physical assignment model. Futures: tick-size normalization, point_value, session hours. Equities: multi-symbol portfolio (6 ETFs in TAA) | Multi-instrument support with correct multipliers/expirations proves domain depth |
| **Risk & performance metrics** | Partial | Sharpe (annualized, timeframe-aware), CAGR, max drawdown ($ and %), turnover, win rate, trade count, realized P&L, total fees. All tested. Metrics glossary in README | Core metrics present and correctly implemented. Missing Sortino, Calmar, profit factor, expectancy, drawdown duration — standard items interviewers may ask about |
| **Exposure awareness** | Weak | Individual positions tracked (qty, avg_price, multiplier). Per-symbol P&L in HTML report for multi-asset runs. No aggregate net/gross exposure, no allocation-over-time chart | Quant risk roles expect exposure tracking; its absence is noticeable |
| **Trade statistics** | Partial | Win rate, trade count, winning/losing counts, realized P&L, fees. FIFO-matched round-trip trades in trades.csv | Missing avg win/loss size, profit factor, expectancy, consecutive streaks, trade duration stats — items that support interview discussion of strategy quality |
| **Reporting** | Strong | 7 artifacts per run: equity_curve.csv, orders.csv, fills.csv, trades.csv, summary.json, run_manifest.json, report.html (interactive Plotly charts with equity curve, drawdown, per-trade P&L bars, per-symbol summary) | Comprehensive and well-formatted; HTML report is interview-ready |
| **Strategy variety** | Strong | 7 strategies: buy_and_hold (option), buy_and_hold_underlying (equity), covered_call (multi-leg/assignment), orb_5m (futures breakout), trend_entry_trailing_stop, trend_follow_risk_sized (portfolio-aware sizing), tactical_asset_allocation (multi-asset Faber TAA) | Good breadth across asset classes, timeframes, and complexity levels without bloat |
| **Reproducibility** | Strong | Config-driven (BacktestConfig dataclass with to_dict/from_dict), run_manifest.json captures full config + git hash + provider diagnostics, deterministic execution (no randomness), seed field reserved | A quant interviewer can rerun any showcase result and get identical output |
| **Testing** | Strong | 893 tests passing (383 backtester, 68 strategizer, 28 portfolio, 414 observer). Unit tests mirror src/ structure. Integration tests exercise full engine loop with fixture data. Metric calculations unit-tested | High coverage of critical paths; gives confidence in correctness claims |
| **Documentation** | Strong | Root README with architecture overview, backtester README with strategy inventory + modeling assumptions + limitations, strategizer/portfolio/observer READMEs, CASE_STUDY.md with honest benchmark comparison, metrics glossary | Coherent narrative; hiring manager can understand what was built in 5 minutes |
| **Scope control** | Strong | "Not a production trading platform" stated upfront. Limitations section in backtester README. Case study acknowledges no walk-forward, no parameter sensitivity. Observer deferred (Plan 260) | Honest scope is credibility-enhancing; overselling is the biggest risk for demo projects |

## 3. Gap Analysis

| Gap | Severity | Why It Is a Gap | Suggested Remedy | Priority |
|-----|----------|-----------------|------------------|----------|
| **Missing trade-level analytics** (avg win/loss, profit factor, expectancy, trade duration) | High | These are the first questions a quant interviewer asks when reviewing strategy results. Without them, the project can show *what* happened but not *why* a strategy works | Add to summary.py: avg_win, avg_loss, profit_factor, expectancy, avg_trade_duration. Display in summary.json and HTML report | Now |
| **No exposure/allocation tracking** | High | For quant risk and analytics roles, exposure awareness is table-stakes. TAA runs 6 ETFs but doesn't show allocation over time or net/gross exposure | Add allocation-over-time chart to HTML report (% of equity per symbol at each rebalance). Add net_exposure, gross_exposure to summary.json | Now |
| **Default fill_timing is same_bar_close** | Medium | same_bar_close has inherent lookahead bias (strategy sees bar close, fills at same price). While next_bar_open exists, the unsafe option being the default is a credibility risk if a reviewer runs a config without fill_timing set | Change default to `next_bar_open` in config.py. Update all configs that intentionally use same_bar_close to be explicit | Next |
| **No walk-forward or out-of-sample validation** | Medium | Case study acknowledged this gap. A single in-sample backtest is standard for a demo, but adding even a simple train/test split would differentiate the project | Add one example showing in-sample (2019-2022) vs out-of-sample (2023-2026) for TAA. Not a framework — just a documented comparison | Next |
| **No dividend income for equity strategies** | Medium | TAA runs 6 ETFs over 7 years. Missing dividends understate returns by ~4-10% depending on holdings. A quant reviewer who checks total return against public data will notice the discrepancy | Document whether data is split/dividend-adjusted. If adjusted: no code change needed (total return captures it). If unadjusted: add disclaimer | Next |
| **Sortino and Calmar ratios missing** | Low | Standard risk-adjusted metrics that quant interviewers may ask about. Not having them isn't disqualifying but having them shows breadth | Add sortino (downside deviation) and calmar (CAGR / max_dd) to summary.py. Both are < 20 lines each | Later |
| **No regression test against showcase** | Low | Showcase artifacts are committed but not automatically compared on re-run. A CI regression test would prove determinism holds over time | Add pytest fixture that runs TAA config and compares summary.json values to committed baseline | Later |

## 4. Top 3 Risks to Project Credibility

### Risk 1: Missing trade-level analytics undermines strategy discussion

**Why it is risky:** When a quant interviewer asks "what's your profit factor?" or "what's the average winner vs loser?" and the project can't answer, it signals that the builder didn't think about trade quality — only aggregate performance. This is the difference between "wrote a backtest" and "analyzed a strategy."

**Evidence:** summary.json contains win_rate, num_winning, num_losing, realized_pnl, and total_fees — but not avg_win, avg_loss, profit_factor, expectancy, or trade_duration. The data to compute these exists in trades.csv (entry/exit prices, P&L per trade), but the calculations aren't done.

**How to reduce:** Add 5 metrics to summary.py (avg_win, avg_loss, profit_factor, expectancy, avg_trade_duration_bars). All are simple aggregations over existing closed_trades data. Display in summary.json and the HTML report's summary table.

### Risk 2: No exposure visualization for multi-asset strategies

**Why it is risky:** The flagship TAA strategy runs 6 ETFs with monthly rebalancing, but the only output is an aggregate equity curve. A reviewer cannot see *what* the strategy was holding at any point, which makes it impossible to discuss regime behavior, concentration risk, or allocation decisions — the core of TAA's value proposition.

**Evidence:** report.html shows equity curve, drawdown, and per-trade P&L bars. The per-symbol P&L table exists (visualize.py:197-218) but only shows final P&L, not allocation over time. There is no chart showing "% of equity in SPY, QQQ, TLT, etc." across the run.

**How to reduce:** Add a stacked area chart to report.html showing allocation (or weight) per symbol over time. The data is available — equity_curve tracks positions at each step; the visualization just needs to decompose it by symbol.

### Risk 3: Default fill_timing creates subtle lookahead bias

**Why it is risky:** A quant reviewer who reads the code (not just the README) will see that `fill_timing` defaults to `same_bar_close`. This means strategies that react to bar close prices get filled at those same prices — a form of lookahead bias. While the project offers `next_bar_open` as an alternative and the flagship TAA uses it, the default is the unsafe option. A reviewer who runs a custom config without setting fill_timing will get biased results.

**Evidence:** BacktestConfig in config.py line 70: `fill_timing: str = "same_bar_close"`. Only the TAA configs explicitly set `fill_timing: next_bar_open`. The buy_and_hold and trend configs don't set it, defaulting to same_bar_close.

**How to reduce:** Change the default to `next_bar_open`. Update any configs that intentionally use same_bar_close (e.g., for demonstration of the concept) to be explicit. Add a comment in config.py explaining the choice.

## 5. Most Important Next Step

**Recommendation:** Add trade-level analytics (avg win/loss, profit factor, expectancy, trade duration) to summary.py and the HTML report.

**Why this is the highest-leverage next step:** These metrics are the vocabulary of strategy evaluation in quant finance. Without them, the project can show *what* the strategy did (Sharpe, CAGR, drawdown) but not *why* it worked or how reliable it is. In an interview, "profit factor is 1.8 with 60% win rate and 1.5:1 reward-to-risk" is a much stronger statement than "Sharpe is 0.73." The data already exists in trades.csv — only the aggregation and display are missing.

**What it should include:**
- `avg_win`: mean P&L of winning trades
- `avg_loss`: mean P&L of losing trades
- `profit_factor`: sum(winning P&L) / abs(sum(losing P&L))
- `expectancy`: (win_rate × avg_win) - ((1 - win_rate) × avg_loss)
- `avg_trade_duration_bars`: mean number of bars from entry to exit
- `reward_risk_ratio`: avg_win / abs(avg_loss)
- Add all to summary.json and to the HTML report summary table

**What it should explicitly avoid:**
- Do not add Monte Carlo simulation, optimization, or parameter sweeps
- Do not refactor the reporter architecture
- Do not add new strategies
- Do not add benchmarking framework

**How it would improve interview readiness:** A candidate who can discuss profit factor, expectancy, and reward-to-risk ratio demonstrates that they understand trade-level analysis, not just curve-level metrics. This is the difference between "data scientist who wrote a backtest" and "someone who understands trading system evaluation."

## 6. Secondary Next Steps

1. **Add allocation-over-time chart to HTML report** — For the flagship TAA run, show a stacked area chart of weight per symbol over time. This makes the TAA strategy *visually explainable* in interviews ("here's where it went to cash in the 2020 drawdown"). Uses existing equity curve data; ~50-80 lines of Plotly code in visualize.py.

2. **Change default fill_timing to next_bar_open** — One-line change in config.py, update affected configs to be explicit. Removes a credibility risk for reviewers who read the source. Add a brief note in the backtester README explaining why.

3. **Add in-sample vs out-of-sample comparison for TAA** — Run TAA on 2019-2022 and 2023-2026 separately, document the comparison in CASE_STUDY.md. Not a framework — just a second run and a paragraph of analysis. Shows the candidate thinks about overfitting.

## 7. What Not to Work On Yet

- **Live trading / broker integration** — Observer already deferred (Plan 260); the backtester's value is in research, not execution. Adding live trading would dilute the project's credibility as a focused demo
- **Greeks engine / options pricing** — The backtester uses market-observed quotes, not theoretical pricing. Adding a Greeks engine would be scope creep and invite scrutiny on model choices
- **Portfolio optimization / Kelly criterion** — Interesting but not necessary for demonstrating backtesting competence. Risk-based sizing (trend_follow_risk_sized) already shows the concept
- **Parameter sensitivity / grid search** — Would be valuable eventually but is secondary to closing the trade-analytics gap. The project should first be able to *discuss* a single run well before running hundreds
- **Additional strategies** — 7 strategies across 3 asset classes is sufficient variety. Adding more without improving analytics would be breadth over depth
- **Fancy UI improvements to Observer** — The observer frontend works and demonstrates React/MUI skills, but it's not the interview artifact. Keep it functional, not polished

## 8. Interview Positioning Note

This project is a config-driven backtesting engine built in Python that demonstrates clean software architecture applied to quantitative finance. It supports options, equities, and futures across 7 strategies, with realistic fee models, configurable fill timing, and deterministic reproducibility. The flagship result is a Faber-style tactical asset allocation strategy run across 6 ETFs over 7 years, with honest benchmark comparison showing the strategy underperformed buy-and-hold SPY in this particular regime — which is itself a demonstration of intellectual honesty. The architecture is the strongest asset: protocol-driven interfaces, shared accounting via a separate portfolio package, frozen dataclasses throughout, and 893 passing tests. The project is explicitly scoped as a career-transition demonstration, not a production platform, and its limitations (simplified fills, no walk-forward validation, no market impact) are documented rather than hidden. In interviews, lead with the architecture and the honest treatment of results rather than the strategy performance numbers.

---

**If the owner only does one thing next, what should it be, and why?**

Add trade-level analytics (profit factor, expectancy, avg win/loss, reward-to-risk ratio, trade duration) to the reporter. The data already exists in trades.csv; only the aggregation is missing. This is the single change that most improves the owner's ability to *discuss strategy quality in an interview* — moving the conversation from "here's my equity curve" to "here's why the strategy has edge." It's ~40-60 lines of code in summary.py, directly addresses the most likely interviewer question ("tell me about your trade statistics"), and requires no architectural changes.
