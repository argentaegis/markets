# 268 — Metrics Glossary (MINS Plan)

**Source:** Refinement of evaluation "Most important next step" (2026-03-16)  
**Type:** Documentation-only work package  
**Scope:** Smallest meaningful improvement in results-explanation credibility

---

## 1. Goal of the next step

Add one-sentence definitions for Sharpe, CAGR, and turnover so a reviewer can understand how the project evaluates performance. Closes the "reporting metrics are unexplained" credibility gap.

---

## 2. Exact repo areas likely affected

| Area | Change |
|------|--------|
| [backtester/README.md](backtester/README.md) | Add "Metrics" subsection with one-sentence definitions for Sharpe, CAGR, turnover; place in or immediately after "Analytics showcase (TAA)" section |
| No code changes | `summary.py`, `report.html`, and reporter logic stay unchanged |

---

## 3. Acceptance criteria

- [ ] `backtester/README.md` contains a "Metrics" (or equivalent) subsection.
- [ ] Sharpe has a one-sentence definition (annualized mean/std of step returns).
- [ ] CAGR has a one-sentence definition (compound annual growth rate).
- [ ] Turnover has a one-sentence definition (sum of |fill_notional| / mean equity).
- [ ] Definitions are factual and match implementation in `summary.py`.
- [ ] No new code, metrics, or formula derivations.

---

## 4. What "done" looks like for interview use

- A reviewer reading the backtester README sees how Sharpe, CAGR, and turnover are computed.
- In an interview, the owner can say: "The README documents how we compute Sharpe, CAGR, and turnover" and point to the definitions.
- Reduces the risk of "hand-waving" when discussing performance.

---

## 5. What should be deferred until later

- Adding Sortino or Calmar to the summary layer.
- Adding metric definitions to `report.html` (tooltips, sidebar).
- Documenting `next_bar_open` recommendation for trend strategies.
- Changing any reporting code or formulas.
