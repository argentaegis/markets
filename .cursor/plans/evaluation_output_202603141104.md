# Project Evaluation — Markets Backtester

**Date:** 2026-03-14  
**Evaluator:** Senior reviewer per `.cursor/rules/evaluation_instructions.md`  
**Scope:** Quantitative finance demonstration project for career transition

---

## 1. Executive assessment

- **Current maturity:** Solid portfolio-project level: monorepo, shared packages (strategizer, portfolio), config-driven backtester, reporter artifacts, and a committed showcase run.
- **Credibility as quant demo:** **Credible but incomplete.** Strong enough to show system design and reproducible research; not yet strong enough for a deep quant/risk discussion.
- **Strongest parts:** Architecture (config → data → signal → execution → portfolio → report); portfolio accounting and invariants; discipline around data ingestion (as-of quotes, stale checks); broker fee schedules and fill timing; risk-adjusted metrics (Sharpe, CAGR, turnover) in summary; multiple broker presets; physical assignment for options.
- **Weakest parts:** Reporting depth is still limited (no Sortino, Calmar, exposure-by-instrument, benchmark comparison); execution remains simplified (no partial fills, no market impact); default fill timing is same-bar close; TAA showcase depends on catalog data that may not exist in a fresh clone.
- **Verdict:** **Credible but incomplete** — usable for interviews if presented honestly, with clear limitations.
- **Scope:** Appropriate for a career-transition project; not over-scoped.

---

## 2. Current-state evidence table

| Area | Status | Evidence found | Why it matters |
|------|--------|----------------|----------------|
| Architecture and code organization | Strong | `backtester/src/engine/engine.py` separates provider, strategy, broker, portfolio, reporting; `strategizer_adapter.py` bridges strategy layer; `portfolio/accounting.py` handles fills, marking, settlement; `OptionFetchSpec` for strategy-driven option fetch | Clear separation of concerns; extensible design |
| Repo/documentation coherence | Strong | Root `README.md`, `backtester/README.md` document flow; strategizer described as "library only, no HTTP service included"; Modeling Assumptions (Modeled today / Still simplified) in backtester README | Docs match runtime; honest about scope |
| Data ingestion / normalization | Strong | `provider.py`: as-of quote lookup, sigma-filtered chain, quote cache, stale/missing policies; catalog-driven paths; `data_provider` override for fixture-backed configs | Data handling is disciplined and traceable |
| Execution simulation | Partial | `fill_model.py`: bid/ask option fills, synthetic spread fallback, stop orders, futures tick normalization; `fee_schedules.py`: ibkr, tdameritrade, schwab, zero; `fill_timing: next_bar_open` for TAA; `broker.py` validates buying power | Real execution modeling but still simplified |
| Portfolio / position tracking | Strong | `portfolio/accounting.py`: apply_fill, mark_to_market, settle_expirations, settle_physical_assignment; invariant checks; multipliers; realized/unrealized P&L | Core quant infra is robust |
| Avoidance of backtesting mistakes | Partial | As-of quotes; `next_bar_open` for lookahead avoidance; sigma-filtered option chain; invariant asserts; golden tests | Several pitfalls avoided; same-bar default is a remaining risk |
| Risk and performance analysis | Partial | `summary.py`: total_return_pct, max_drawdown, win_rate, realized/unrealized P&L, Sharpe, CAGR, turnover, num_open_positions; `report.html` with equity/drawdown charts | Baseline + risk-adjusted metrics; no Sortino, Calmar, exposure breakdown |
| Strategy support | Strong | 7 strategies: buy_and_hold, buy_and_hold_underlying, covered_call, orb_5m, trend_entry_trailing_stop, trend_follow_risk_sized, tactical_asset_allocation | Breadth without bloat |
| Reproducibility | Strong | Config YAML; `run_manifest.json` with git hash; fixture-backed example configs; Makefile workflow; `runs/showcase/` committed | Easy to rerun and compare |
| Tests and validation | Strong | 383 backtester tests; integration and golden tests; `pytest` across backtester, strategizer, portfolio | Good confidence in behavior |
| Sample outputs | Partial | `runs/showcase/` with ORB result; `num_open_positions` in summary; TAA config for 2019–2026 (catalog-dependent) | Showcase exists; some runs depend on data catalog |
| Interview usefulness | Partial | Clear README, modeling-assumptions section, Makefile, showcase run; honest "Still simplified" section | Discussable; limitations are documented |
| Scope control | Strong | Focused on backtesting, strategies, portfolio; observer is sidecar; no live trading or broker integration | Appropriately bounded |

---

## 3. Gap analysis

| Gap | Severity | Why it is a gap | Suggested remedy | Priority |
|-----|----------|-----------------|------------------|----------|
| Some configs require catalog data; README overstates fixture-backing | Medium | `buy_and_hold_example.yaml` and `orb_5m_example.yaml` use `data_provider` fixtures (work on fresh clone); `tactical_asset_allocation_example.yaml` and `covered_call_example.yaml` use catalog (`data/exports/...`), which may not exist | Document which configs are fixture-backed vs catalog-backed; make README "quick start" point to fixture-backed configs only | Now |
| Reporting depth still thin for quant roles | Medium | No Sortino, Calmar, exposure-by-instrument, or benchmark; turnover is present but not prominently explained in report | Add one or two more defensible metrics (e.g., Sortino) and a short README note on metrics | Next |
| Default fill timing is same-bar close | Low | Lookahead-sensitive strategies could overstate performance; `next_bar_open` is opt-in | Document that `next_bar_open` is recommended for trend/breakout strategies; consider making it default for equity | Later |
| No explicit exposure or concentration metrics | Low | Multi-ETF TAA run has no breakdown of sector or symbol concentration | Defer; not critical for current scope | Later |

---

## 4. Top 3 risks to project credibility

1. **Catalog-dependent configs may confuse fresh-clone users**
   - **Why risky:** A reviewer clones the repo and tries `covered_call_example.yaml` or `tactical_asset_allocation_example.yaml` first; these use the catalog and may fail if `data/exports/` is empty. First impression is "doesn't work."
   - **Evidence:** `buy_and_hold_example.yaml` and `orb_5m_example.yaml` use `data_provider` with fixture paths and work on fresh clone; TAA and covered_call use catalog; README says "fixture-backed" for all example configs.
   - **Mitigation:** In README, explicitly state that `buy_and_hold_example` and `orb_5m_example` run without data setup; document TAA and covered_call as needing catalog/data.

2. **Execution realism remains visibly simplified**
   - **Why risky:** An experienced quant will notice same-bar close default, no partial fills, no market impact, and may discount results as optimistic.
   - **Evidence:** `fill_model.py` uses bar close + synthetic spread for underlying; `broker.py` does basic buying-power checks; README "Still simplified" lists these.
   - **Mitigation:** Emphasize TAA config with `next_bar_open` and `ibkr_equity_spread` as the "realistic" showcase; keep "Still simplified" section prominent; do not oversell execution.

3. **Reporting metrics lack explanation**
   - **Why risky:** Sharpe, CAGR, turnover are computed but not explained in the report or README; a reviewer may wonder how they are defined.
   - **Evidence:** `summary.py` has `_compute_sharpe`, `_compute_cagr`, `_compute_turnover`; `report.html` embeds summary; no glossary or formula note.
   - **Mitigation:** Add a short "Metrics" subsection to `backtester/README.md` or `report.html` (e.g., Sharpe = annualized mean/std of step returns, turnover = sum(|fill_notional|)/mean(equity)).

---

## 5. Most important next step

**Recommendation:** Ensure a zero-friction "quick start" path that works on a fresh clone without data setup.

- **Why highest leverage:** The biggest credibility risk is "I cloned it and it didn't run." Fixing that is cheap and has immediate impact. Architecture and reporting are already credible; data-path clarity is the remaining onboarding gap.
- **What it should include:**
  - Document in README which configs are fixture-backed vs catalog-backed.
  - Ensure `make backtester-run BACKTESTER_CONFIG=configs/buy_and_hold_example.yaml` or `orb_5m_example.yaml` works with only repo fixtures.
  - Add a one-line "Quick start: run X" that is guaranteed to work.
- **What it should avoid:**
  - Adding more configs or features.
  - Changing the catalog or data layout.
- **Interview impact:** A reviewer can run a backtest in under a minute and see artifacts. That supports "I built something that works" without overclaiming.

---

## 6. Secondary next steps

1. **Add a short metrics glossary** — One README subsection explaining Sharpe, CAGR, turnover in one sentence each. Improves interview discussion.
2. **Make `next_bar_open` the recommended default for trend strategies** — Document this in config comments or README; reduces lookahead risk for trend/breakout runs.
3. **Add Sortino or Calmar** — One additional risk-adjusted metric if the summary layer can absorb it with minimal code.

---

## 7. What not to work on yet

- Live trading or broker API integration.
- Full options Greeks or volatility surface.
- Benchmark comparison or factor attribution.
- Additional strategies beyond the current seven.
- Richer observer UI.

---

## 8. Interview positioning note

Describe this as a modular backtesting and strategy-evaluation codebase with a live observer sidecar. The strongest pitch: it demonstrates clear flow from config → data → strategy → execution → portfolio → report, shared strategy and accounting layers, disciplined data handling, broker fee schedules, configurable fill timing, and risk-adjusted metrics (Sharpe, CAGR, turnover). It supports options (including covered call with physical assignment), futures (ORB), and multi-ETF tactical allocation. Limitations: execution is intentionally simplified (no partial fills, no market impact); default fill timing is same-bar close; margin/short-borrow not modeled. For quant, risk, or analytics roles, emphasize architecture, reproducibility, and data discipline; acknowledge execution and reporting simplifications as documented tradeoffs.

---

## If the owner only does one thing next, what should it be, and why?

**Ensure a quick-start path that works on a fresh clone.**

Reason: The project is already credible on architecture, execution modeling, and reporting. The remaining high-impact gap is onboarding — a reviewer who clones the repo and hits a catalog or path error will question whether the project is "real." Documenting which configs work with fixtures only and providing one guaranteed "run this first" command costs very little and materially improves first impression.
