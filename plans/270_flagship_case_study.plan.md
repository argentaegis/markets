---
name: ""
overview: ""
todos: []
isProject: false
---

# 270 — Flagship Case Study (MINS Plan)

**Source:** Analysis of [markets_project_evaluation_for_cursor.md](markets_project_evaluation_for_cursor.md)  
**Type:** Packaging and documentation work package  
**Scope:** Make the repo lead with one strong quant-demo artifact; close "showcase too weak" and "story diluted" gaps

---

## 1. Goal of the next step

Create one flagship backtest case study and make the repo lead with it. Turn the hiring narrative from "there is a lot of promising infrastructure" into "this is a clear, disciplined backtesting demo with one strong, explainable flagship example and supporting architecture."

---

## 2. Exact repo areas likely affected


| Area                                                   | Change                                                                                                                                                                                                  |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [backtester/runs/showcase/](backtester/runs/showcase/) | Replace or restructure: add TAA flagship artifact set (summary.json, equity_curve.csv, trades.csv, report.html) with meaningful metrics; keep ORB as secondary mechanics example                        |
| [backtester/runs/showcase/](backtester/runs/showcase/) | Add short markdown case-study note (strategy, assumptions, key metrics, what the run demonstrates, known simplifications)                                                                               |
| [README.md](README.md) (root)                          | Reframe to lead with backtester as primary interview artifact; present strategizer and portfolio as support packages; demote observer to secondary; add top-level showcase section pointing to flagship |
| [backtester/README.md](backtester/README.md)           | Lead with TAA flagship; keep ORB as "mechanics / regression example"; ensure config table and showcase section reflect primary vs secondary runs                                                        |
| No strategy or engine code changes                     | Runner, engine, reporter, configs stay unchanged                                                                                                                                                        |


---

## 3. Acceptance criteria

- A flagship run exists with closed trades, non-null Sharpe and CAGR, and meaningful duration (TAA 2019–2026 or equivalent).
- Artifacts are committed: `summary.json`, `equity_curve.csv`, `trades.csv`, `report.html`, and a short case-study markdown.
- Root README opens with backtester as the main artifact and points directly to the flagship case study.
- Root README presents strategizer and portfolio as supporting packages, not co-equal products.
- Root README demotes observer to a secondary or "optional / experimental" section.
- Backtester README presents TAA showcase as primary; ORB remains as secondary mechanics example.
- Case-study note explains: strategy, assumptions, key metrics, what the run demonstrates, known simplifications.
- No new strategies, configs, or code beyond documentation and committed artifacts.

---

## 4. What "done" looks like for interview use

- A reviewer landing on the repo sees the backtester as the centerpiece and one flagship run with explainable results.
- The flagship `summary.json` shows non-null Sharpe, CAGR, turnover, closed trades, and drawdown.
- The owner can say: "The primary interview artifact is the TAA backtest; here are the committed results, assumptions, and what it demonstrates."
- ORB and trend-follow risk-sized remain available as secondary examples; they are clearly positioned as such.
- Root narrative is crisp: this repo's main hiring story is the deterministic backtester with one strong case study.

---

## 5. What should be deferred until later

- **Secondary next steps (Section 8):** Tighten public realism defaults (next_bar_open for visible examples); add one benchmark/comparison view (e.g. TAA vs buy-and-hold); narrow public scope statement.
- **Other gaps:** Options support framing ("basic simulation support"); observer demotion beyond README restructure.
- **What not to work on (Section 9):** Fancy UI, live trading, broker API, full Greeks, large strategy expansion, broad portfolio optimization, observer elaboration, polishing edge features.

---

## 6. Prerequisite / data note

The TAA config (`tactical_asset_allocation_example.yaml`) requires **catalog data** (6 ETFs, 2019–2026). To generate the flagship artifacts:

1. Ensure `backtester/data/catalog.yaml` and `backtester/data/exports/` exist for SPY, QQQ, IWM, TLT, GLD, USO.
2. Run: `make backtester-run BACKTESTER_CONFIG=configs/tactical_asset_allocation_example.yaml`
3. Copy the generated artifacts into `runs/showcase/` (or a subdirectory such as `showcase/taa/`).

If catalog data is not available, `trend_follow_risk_sized_example.yaml` is fixture-backed and can produce closed trades and metrics; it may serve as an alternative flagship with reduced scope (single-instrument, shorter run).