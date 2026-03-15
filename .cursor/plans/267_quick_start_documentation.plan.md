---
name: ""
overview: ""
todos: []
isProject: false
---

# 267 — Quick Start Documentation (MINS Plan)

**Source:** Refinement of evaluation "Most important next step" (2026-03-14)  
**Type:** Documentation-only work package  
**Scope:** Smallest meaningful improvement in project credibility

---

## 1. Goal of the next step

Ensure a reviewer who clones the repo can run a backtest in under a minute without any data setup. Clarify which example configs work out-of-the-box vs which require catalog data.

---

## 2. Exact repo areas likely affected


| Area                                         | Change                                                                                                                             |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| [backtester/README.md](backtester/README.md) | Add "Quick start" section with one guaranteed command; add "Example configs" table distinguishing fixture-backed vs catalog-backed |
| [README.md](README.md) (root)                | Optionally add or adjust the backtester quick-start callout in Common Commands                                                     |
| No code changes                              | Runner, configs, and data provider logic stay unchanged                                                                            |


---

## 3. Acceptance criteria

- A new user can run `make backtester-run BACKTESTER_CONFIG=configs/buy_and_hold_example.yaml` (or `orb_5m_example`) from a fresh clone and get a successful run with output artifacts.
- `backtester/README.md` has a "Quick start" or "Run first" subsection that explicitly recommends one of the fixture-backed configs.
- `backtester/README.md` config table (or equivalent) indicates which configs are fixture-backed vs catalog-backed.
- No new configs, fixtures, or code changes beyond documentation.

---

## 4. What "done" looks like for interview use

- A reviewer cloning the repo and reading the README sees a clear "Run this first" path.
- Running that command produces `runs/<timestamp>_*/` with `summary.json`, `report.html`, etc.
- The reviewer can say "I ran it and it worked" without hitting catalog or path errors.
- In an interview, the owner can say: "The README tells you exactly which configs run without any data setup; TAA and covered call need the data catalog if you want to run those."

---

## 5. What should be deferred until later

- Adding a metrics glossary (Sharpe, CAGR, turnover) — secondary next step.
- Changing default fill timing or config behavior.
- Adding new fixture-backed configs or converting catalog-backed configs to fixtures.
- Any changes to the catalog, data layout, or runner logic.
- Sortino, Calmar, exposure metrics, or other reporting enhancements.

