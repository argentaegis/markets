# Project Evaluation — Markets Backtester

**Date:** 2026-03-16  
**Evaluator:** Senior reviewer per `.cursor/rules/evaluation_instructions.md`  
**Scope:** Quantitative finance demonstration project for career transition

---

## 1. Executive assessment

- **Current maturity:** Solid portfolio-project level: monorepo, shared packages (strategizer, portfolio), config-driven backtester, reporter artifacts, committed showcase run, and a clear quick-start path.
- **Credibility as quant demo:** **Credible but incomplete.** Strong enough to show system design, reproducible research, and zero-friction onboarding; not yet strong enough for a deep quant/risk discussion.
- **Strongest parts:** Architecture (config → data → signal → execution → portfolio → report); quick start that works on fresh clone; fixture vs catalog documentation; portfolio accounting and invariants; broker fee schedules and fill timing; risk-adjusted metrics (Sharpe, CAGR, turnover); physical assignment for options.
- **Weakest parts:** Reporting metrics lack explicit definitions (Sharpe, CAGR, turnover computed but not explained); no Sortino, Calmar, or exposure breakdown; execution remains simplified; default fill timing is same-bar close.
- **Verdict:** **Credible but incomplete** — usable for interviews; quick-start gap closed (Plan 267).
- **Scope:** Appropriate for a career-transition project.

---

## 2. Current-state evidence table

| Area | Status | Evidence found | Why it matters |
|------|--------|----------------|----------------|
| Architecture and code organization | Strong | `engine.py` separates provider, strategy, broker, portfolio, reporting; `strategizer_adapter.py`; `portfolio/accounting.py`; `OptionFetchSpec` | Clear separation; extensible |
| Repo/documentation coherence | Strong | Root and backtester README; Quick start section; fixture vs catalog table; Modeling Assumptions | Docs match runtime; onboarding clear |
| Data ingestion / normalization | Strong | `provider.py`: as-of quotes, sigma-filtered chain, cache, stale policies; `data_provider` override | Disciplined data handling |
| Execution simulation | Partial | Bid/ask option fills, synthetic spread, stop orders, fees; `next_bar_open` for TAA | Real modeling but simplified |
| Portfolio / position tracking | Strong | `accounting.py`: apply_fill, mark_to_market, settle_expirations, settle_physical_assignment | Core quant infra is robust |
| Avoidance of backtesting mistakes | Partial | As-of quotes; `next_bar_open` opt-in; invariants; golden tests | Several pitfalls avoided |
| Risk and performance analysis | Partial | `summary.py`: return, drawdown, win rate, Sharpe, CAGR, turnover; `report.html` | Baseline + risk-adjusted; no formula notes |
| Strategy support | Strong | 7 strategies; `STRATEGY_REGISTRY`; variety without bloat | Breadth without bloat |
| Reproducibility | Strong | Config YAML; `run_manifest.json` with git hash; fixture-backed quick start; Makefile | Easy to rerun |
| Tests and validation | Strong | 383+ backtester, 68 strategizer, 28 portfolio, 412 observer | Good confidence |
| Sample outputs | Partial | `runs/showcase/`; config table clarifies fixture vs catalog | Showcase exists; catalog configs documented |
| Interview usefulness | Partial | Quick start, modeling assumptions, honest limitations | Discussable; metrics need explanation |
| Scope control | Strong | Focused on backtesting, strategies, portfolio; observer sidecar | Appropriately bounded |

---

## 3. Gap analysis

| Gap | Severity | Why it is a gap | Suggested remedy | Priority |
|-----|----------|-----------------|------------------|----------|
| Reporting metrics lack explicit definitions | Medium | Sharpe, CAGR, turnover are computed but not explained; a reviewer may wonder how they are defined | Add a short "Metrics" subsection to `backtester/README.md` with one-sentence definitions | Now |
| Reporting depth thin for quant roles | Medium | No Sortino, Calmar, exposure-by-instrument, benchmark | Add one more defensible metric (e.g., Sortino) if minimal effort | Next |
| Default fill timing is same-bar close | Low | Lookahead-sensitive strategies could overstate performance | Document `next_bar_open` as recommended for trend/breakout; keep as opt-in | Later |

---

## 4. Top 3 risks to project credibility

1. **Reporting metrics are unexplained**
   - **Why risky:** A quant reviewer will want to know how Sharpe, CAGR, turnover are computed; absence of definitions can suggest hand-waving.
   - **Evidence:** `summary.py` has `_compute_sharpe`, `_compute_cagr`, `_compute_turnover`; README Analytics showcase mentions them but does not define formulas.
   - **Mitigation:** Add a brief "Metrics" subsection (e.g., Sharpe = annualized mean/std of step returns; CAGR = compound annual growth rate; turnover = sum(|fill_notional|)/mean(equity)).

2. **Execution realism remains visibly simplified**
   - **Why risky:** Same-bar close default, no partial fills, no market impact can make results look optimistic to an experienced quant.
   - **Evidence:** `fill_model.py` uses bar close + synthetic spread; README "Still simplified" lists these.
   - **Mitigation:** Keep "Still simplified" prominent; emphasize TAA with `next_bar_open` and `ibkr_equity_spread` as the realistic showcase.

3. **Catalog configs still require data setup**
   - **Why risky:** A reviewer who runs TAA or covered_call without data may hit catalog errors.
   - **Evidence:** README now documents fixture vs catalog; quick start points to fixture configs.
   - **Mitigation:** Already addressed; continue to surface fixture-backed configs as the default path.

---

## 5. Most important next step

**Recommendation:** Add a short "Metrics" subsection to `backtester/README.md` explaining Sharpe, CAGR, and turnover in one sentence each.

- **Why highest leverage:** The quick-start gap is closed. The next credibility gap is "how do you evaluate results?" Unexplained metrics undermine interview discussion. A brief glossary is low-effort and directly supports quant/risk conversation.
- **What it should include:**
  - One-sentence definitions for Sharpe (annualized), CAGR, turnover.
  - Placement in or near the "Analytics showcase (TAA)" section.
- **What it should avoid:**
  - New code or metrics.
  - Long derivations or footnotes.
- **Interview impact:** The owner can say "the README documents how we compute Sharpe, CAGR, and turnover" and point to definitions.

---

## 6. Secondary next steps

1. **Add Sortino or Calmar** — One additional risk-adjusted metric if the summary layer can absorb it with minimal code.
2. **Document `next_bar_open` recommendation** — In config comments or README: recommend for trend/breakout strategies to reduce lookahead risk.
3. **Surface metrics in report.html** — Optional tooltip or sidebar in the HTML report linking to metric definitions.

---

## 7. What not to work on yet

- Live trading or broker API integration.
- Full options Greeks or volatility surface.
- Benchmark comparison or factor attribution.
- Additional strategies beyond the current seven.
- Richer observer UI.

---

## 8. Interview positioning note

Describe this as a modular backtesting and strategy-evaluation codebase with a live observer sidecar. The strongest pitch: it demonstrates clear flow from config → data → strategy → execution → portfolio → report, a quick start that works on fresh clone, shared strategy and accounting layers, disciplined data handling, broker fee schedules, configurable fill timing, and risk-adjusted metrics (Sharpe, CAGR, turnover). It supports options (including covered call with physical assignment), futures (ORB), and multi-ETF tactical allocation. Limitations: execution is intentionally simplified (no partial fills, no market impact); default fill timing is same-bar close; margin/short-borrow not modeled. For quant, risk, or analytics roles, emphasize architecture, reproducibility, data discipline, and the quick-start path; acknowledge execution and reporting simplifications as documented tradeoffs.

---

## If the owner only does one thing next, what should it be, and why?

**Add a short metrics glossary to `backtester/README.md`.**

Reason: The quick-start gap is closed. The next credibility gap is explanation of results. Sharpe, CAGR, and turnover are computed but not defined in the repo. A one-sentence definition for each costs very little and materially improves the owner's ability to discuss performance in an interview.
