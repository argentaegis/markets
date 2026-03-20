# 261: Repo Narrative and Showcase Work Package

Refines the "Most important next step" from [evaluation_output_20260311.md](evaluation_output_20260311.md) into the smallest concrete work package that improves project credibility for interviews.

---

## 1. Goal of the next step

Make the repo understandable and credible to a finance/quant reviewer in the first 5 minutes.

This work package should:
- Replace the outdated repo-level story with the **current architecture**
- Make the project's **scope and realism assumptions explicit**
- Provide **one representative run artifact** that demonstrates the backtester working as intended

This is not a feature build. It is a targeted credibility and communication fix.

---

## 2. Exact repo areas affected

### Primary docs
- `README.md` — full rewrite
- `backtester/README.md` — update strategy table, add modeling-assumptions section, add showcase writeup
- `strategizer/README.md` — add missing `trend_follow_risk_sized` to strategies table
- `portfolio/README.md` — create (does not exist today)

### Gitignore carve-outs
- `backtester/.gitignore` — un-ignore `configs/*_example.yaml` and `runs/showcase/` so reviewers see them

### Showcase artifact
- `backtester/runs/showcase/` — one committed run directory with full artifacts
- Showcase writeup in `backtester/README.md` explaining the run

### Evidence that should drive the rewrite
- `backtester/src/runner.py`
- `backtester/src/engine/engine.py`
- `backtester/src/strategies/strategizer_adapter.py`
- `backtester/src/broker/fill_model.py`
- `backtester/src/broker/broker.py`
- `portfolio/src/portfolio/accounting.py`
- `backtester/src/reporter/reporter.py`
- `backtester/src/reporter/summary.py`

---

## 3. Acceptance criteria

### Repo narrative
- Root `README.md` correctly describes both strategizer modes:
  - **In-process** for backtester (direct import, no HTTP)
  - **HTTP service** for observer (still uses `http_strategizer.py`)
- Root `README.md` Projects table includes `portfolio/` alongside `backtester/`, `strategizer/`, and `observer/`
- Root docs clearly explain the roles of:
  - `backtester`
  - `strategizer`
  - `portfolio`
- Root docs include a concise architecture summary:
  - config -> data -> signal -> execution -> portfolio -> report
- Repo-facing docs state clearly that this is a **deterministic backtesting / strategy-evaluation demo project**, not a production trading platform

### Modeling assumptions (in `backtester/README.md`)
- A short, explicit section on what is modeled today:
  - bid/ask option fills
  - synthetic spread fallback
  - futures tick normalization
  - fees
  - portfolio/accounting and mark-to-market
- A short, explicit section on what is still simplified:
  - same-bar underlying fill assumptions
  - limited limit-order realism
  - no partial fills / market impact
  - no broker-grade margin or borrow treatment

### Showcase artifact
- `backtester/runs/showcase/` contains one current representative run (summary, trades, equity curve, manifest, report)
- The run is not stale and not based on removed assumptions (no 5m references)
- `backtester/README.md` includes a short human explanation of the showcase run:
  - what strategy was run
  - what period/instrument was used
  - why trades did or did not occur
  - what the result demonstrates

### Gitignore / trackability
- Example configs (`configs/*_example.yaml`) are tracked in git so a reviewer can see how to invoke the backtester
- The showcase run directory (`runs/showcase/`) is tracked in git
- Other `runs/` and `configs/` remain gitignored

---

## 4. Deliverables (execution order)

### Step 1: Gitignore carve-outs
- Edit `backtester/.gitignore`:
  - Add `!configs/*_example.yaml` after `/configs/`
  - Add `!runs/showcase/` after `runs/`

### Step 2: Generate the showcase run
- Pick strategy: `buy_and_hold_underlying` with fixture data (reproducible without API keys, produces trades, simple to explain)
- Run the backtest, copy output to `backtester/runs/showcase/`
- Delete the stale `backtester/runs/202603030221_ES_5m_20260102_20260131/` directory

### Step 3: Rewrite root `README.md`
- Project description: deterministic backtesting / strategy-evaluation codebase
- Architecture summary: config -> data -> signal -> execution -> portfolio -> report
- Projects table: add `portfolio/`, fix `strategizer/` description (shared module, imported in-process by backtester; served via HTTP for observer)
- Commands section: update backtester section (no HTTP dependency), keep observer section (still needs HTTP strategizer)

### Step 4: Update `backtester/README.md`
- Update strategy table (ensure names/descriptions match current state)
- Add **Modeling Assumptions** section (modeled today / still simplified)
- Add **Showcase Run** section explaining the committed run artifact
- Remove any stale references to 5m or HTTP strategizer

### Step 5: Update `strategizer/README.md`
- Add `trend_follow_risk_sized` to the strategies table
- Verify existing content still accurate

### Step 6: Create `portfolio/README.md`
- Minimal: purpose (shared position/accounting package), install, public API surface (`PortfolioState`, `Position`, `apply_fill`, `mark_to_market`, `settle_positions`, `assert_portfolio_invariants`)

### Step 7: Verify
- `pytest` passes in `backtester/`, `strategizer/`, `portfolio/`
- `git status` shows the new/modified files are trackable
- A fresh reader of root `README.md` can understand the project without prior context

---

## 5. Design decisions

### Showcase strategy choice: `buy_and_hold_underlying`
- Produces guaranteed trades (buys on first bar)
- Uses equity/ETF data available as fixtures — reproducible without API keys
- Simple enough to explain in two sentences
- Alternative considered: `trend_follow_risk_sized` (demonstrates portfolio-awareness but may produce zero trades depending on data, harder to explain quickly)
- If fixture data for `buy_and_hold_underlying` does not produce a compelling result, fall back to `orb_5m` with fixture data

### Modeling assumptions location: `backtester/README.md`
- These are backtester-specific implementation details, not repo-level concerns
- Root README links to `backtester/README.md` for details
- Keeps root README concise

### Observer / HTTP strategizer nuance
- Observer still uses HTTP strategizer — this is correct and should remain documented
- Root README should explain that strategizer serves two modes rather than removing all HTTP language
- The "startup order" section should clarify: only needed if running observer

---

## 6. What "done" looks like for interview use

Done means a reviewer can:
1. Open the root repo and understand what the project is in under 2 minutes
2. Follow the current architecture without being misled by outdated service-language
3. See one representative backtest result and understand what it proves
4. Hear an honest explanation of modeling assumptions without the repo overclaiming realism

In practical interview terms, "done" means the owner can answer:
- What did you build?
- How does data flow through it?
- What is realistic vs simplified?
- Show me one run and explain it.

without needing to apologize for stale docs or unclear project boundaries.

---

## 7. What should be deferred until later

Defer these until after the narrative/showcase package is complete:
- New strategies
- Risk-adjusted metrics expansion (Sharpe, CAGR, exposure, turnover)
- Execution-model upgrades beyond small documentation-aligned fixes
- UI improvements
- Live trading or broker integration
- Broader portfolio optimization or research workflow tooling

---

## Why this should be next

This is the smallest meaningful improvement in project credibility because the implementation is already reasonably strong, but the repo currently **undersells and partly misdescribes itself**.

The next win is not more breadth. It is making the current work legible, accurate, and interview-ready.
