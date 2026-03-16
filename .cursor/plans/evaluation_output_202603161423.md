# Project Evaluation — Markets Backtester

**Date:** 2026-03-16  
**Evaluator:** Senior reviewer per `.cursor/rules/evaluation_instructions.md`  
**Scope:** Quantitative finance demonstration project for career transition

---

## 1. Executive assessment

- **Current maturity:** Solid portfolio-project level: monorepo, shared packages, config-driven backtester, reporter artifacts, quick start, fixture vs catalog docs, and a Metrics glossary (Plans 267, 268).
- **Credibility as quant demo:** **Credible but incomplete.** Strong enough to show system design, reproducible research, zero-friction onboarding, and defensible result evaluation; not yet strong enough for a deep quant/risk discussion.
- **Strongest parts:** Architecture (config → data → signal → execution → portfolio → report); quick start on fresh clone; fixture vs catalog table; Metrics subsection (Sharpe, CAGR, turnover defined); portfolio accounting and invariants; broker fee schedules and fill timing; physical assignment for options.
- **Weakest parts:** Execution remains simplified (same-bar close default, no partial fills, no market impact); no Sortino, Calmar, or exposure breakdown; `next_bar_open` not yet recommended for trend strategies.
- **Verdict:** **Credible but incomplete** — usable for interviews; quick-start and metrics-explanation gaps closed.
- **Scope:** Appropriate for a career-transition project.

---

## 2. Current-state evidence table

| Area | Status | Evidence found | Why it matters |
|------|--------|----------------|----------------|
| Architecture and code organization | Strong | `engine.py` separates provider, strategy, broker, portfolio, reporting; `strategizer_adapter.py`; `portfolio/accounting.py`; `OptionFetchSpec` | Clear separation; extensible |
| Repo/documentation coherence | Strong | Root and backtester README; Quick start; fixture vs catalog; Metrics subsection; Modeling Assumptions | Docs match runtime; onboarding and metrics clear |
| Data ingestion / normalization | Strong | `provider.py`: as-of quotes, sigma-filtered chain, cache, stale policies; `data_provider` override | Disciplined data handling |
| Execution simulation | Partial | Bid/ask option fills, synthetic spread, stop orders, fees; `next_bar_open` for TAA | Real modeling but simplified |
| Portfolio / position tracking | Strong | `accounting.py`: apply_fill, mark_to_market, settle_expirations, settle_physical_assignment | Core quant infra is robust |
| Avoidance of backtesting mistakes | Partial | As-of quotes; `next_bar_open` opt-in; invariants; golden tests | Several pitfalls avoided; same-bar default remains |
| Risk and performance analysis | Strong | `summary.py`: return, drawdown, win rate, Sharpe, CAGR, turnover; Metrics subsection defines formulas | Baseline + risk-adjusted; definitions documented |
| Strategy support | Strong | 7 strategies; `STRATEGY_REGISTRY`; variety without bloat | Breadth without bloat |
| Reproducibility | Strong | Config YAML; `run_manifest.json` with git hash; fixture-backed quick start; Makefile | Easy to rerun |
| Tests and validation | Strong | 383+ backtester, 68 strategizer, 28 portfolio, 412 observer | Good confidence |
| Sample outputs | Partial | `runs/showcase/`; config table clarifies fixture vs catalog | Showcase exists; catalog configs documented |
| Interview usefulness | Strong | Quick start, metrics glossary, modeling assumptions, honest limitations | Discussable; metrics and onboarding clear |
| Scope control | Strong | Focused on backtesting, strategies, portfolio; observer sidecar | Appropriately bounded |

---

## 3. Gap analysis

| Gap | Severity | Why it is a gap | Suggested remedy | Priority |
|-----|----------|-----------------|------------------|----------|
| Same-bar close default not flagged for trend strategies | Medium | Lookahead-sensitive strategies (trend, breakout) can overstate performance; `next_bar_open` exists but is not recommended | Add one sentence to README or config comments: recommend `fill_timing: next_bar_open` for trend/breakout strategies | Now |
| No Sortino, Calmar, or exposure metrics | Low | Quant reviewers may expect additional risk-adjusted metrics | Add Sortino if minimal effort; defer Calmar and exposure | Next |
| Execution realism remains simplified | Low | Same-bar default, no partial fills; documented in "Still simplified" | Keep documentation honest; no code change needed for scope | Later |

---

## 4. Top 3 risks to project credibility

1. **Same-bar close default for trend strategies**
   - **Why risky:** Trend-following and breakout strategies are especially vulnerable to lookahead when fills use same-bar close; a quant reviewer may flag this.
   - **Evidence:** Default is `same_bar_close`; TAA uses `next_bar_open`; README does not recommend `next_bar_open` for trend/breakout configs.
   - **Mitigation:** Add one sentence recommending `fill_timing: next_bar_open` for trend and breakout strategies in the README or relevant config comments.

2. **Execution realism remains visibly simplified**
   - **Why risky:** No partial fills, no market impact can make results optimistic.
   - **Evidence:** `fill_model.py`; README "Still simplified" lists these.
   - **Mitigation:** Keep "Still simplified" prominent; emphasize TAA as the realistic showcase; do not oversell.

3. **Catalog configs require data setup**
   - **Why risky:** TAA or covered_call may fail on fresh clone.
   - **Evidence:** README documents fixture vs catalog; quick start points to fixture configs.
   - **Mitigation:** Already addressed; continue to surface fixture-backed configs.

---

## 5. Most important next step

**Recommendation:** Add one sentence to `backtester/README.md` recommending `fill_timing: next_bar_open` for trend and breakout strategies.

- **Why highest leverage:** The remaining obvious weakness is lookahead risk for trend/breakout runs. The fix already exists (`next_bar_open`); it just needs to be recommended. One sentence closes the gap.
- **What it should include:**
  - A sentence in the "Fill timing" bullet (Modeled today) or "Still simplified" section.
  - Example: "For trend-following or breakout strategies, use `fill_timing: next_bar_open` to avoid execution lookahead."
- **What it should avoid:**
  - Changing default behavior or config parsing.
  - Long explanations.
- **Interview impact:** The owner can say "we recommend next-bar-open for trend strategies to avoid lookahead" and point to the README.

---

## 6. Secondary next steps

1. **Add Sortino** — One additional risk-adjusted metric if the summary layer can absorb it with minimal code.
2. **Add recommendation to trend/breakout config comments** — e.g., `fill_timing: next_bar_open` in `trend_entry_trailing_stop_example.yaml` or `orb_5m_example.yaml` with a brief comment.
3. **Surface metrics in report.html** — Optional tooltip linking to README Metrics section.

---

## 7. What not to work on yet

- Live trading or broker API integration.
- Full options Greeks or volatility surface.
- Benchmark comparison or factor attribution.
- Additional strategies beyond the current seven.
- Richer observer UI.

---

## 8. Interview positioning note

Describe this as a modular backtesting and strategy-evaluation codebase with a live observer sidecar. The strongest pitch: it demonstrates clear flow from config → data → strategy → execution → portfolio → report, a quick start on fresh clone, shared strategy and accounting layers, disciplined data handling, broker fee schedules, configurable fill timing (including `next_bar_open` for TAA), risk-adjusted metrics (Sharpe, CAGR, turnover) with definitions in the README, and options support including covered call with physical assignment. Limitations: execution is intentionally simplified (no partial fills, no market impact); default fill timing is same-bar close; margin/short-borrow not modeled. For quant, risk, or analytics roles, emphasize architecture, reproducibility, data discipline, metrics documentation, and the quick-start path; acknowledge execution simplifications as documented tradeoffs.

---

## If the owner only does one thing next, what should it be, and why?

**Add one sentence recommending `fill_timing: next_bar_open` for trend and breakout strategies.**

Reason: Quick start and metrics glossary are done. The remaining obvious gap is lookahead risk for trend/breakout strategies. The engine already supports `next_bar_open`; documenting the recommendation costs one sentence and materially improves credibility for reviewers who care about backtest rigor.
