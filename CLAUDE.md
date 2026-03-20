# Claude Code — Markets Project

## Project Overview

Monorepo for a quantitative finance backtesting and live-observation platform, built as a career-transition portfolio project. The goal is to demonstrate trading logic, disciplined data flow, realistic execution assumptions, and credible performance analysis.

**Sub-projects:**
- `backtester/` — deterministic options/futures backtesting engine
- `strategizer/` — shared strategy library
- `portfolio/` — shared portfolio state and accounting
- `observer/` — optional live market observer (FastAPI backend + React/MUI frontend)
- `runs/` — backtest outputs (only `runs/showcase/` is committed)
- `plans/` — all planning documents (87+ files)

**Key commands** (always use the root `Makefile` via the shared `.venv`):
```
make install          # install all deps (Python + npm)
make test             # run all tests
make check            # build + test
make run              # start unified app at http://localhost:5173
make backtester-run BACKTESTER_CONFIG=configs/taa_example.yaml
make observer-backend # backend only
make observer-frontend # frontend only
```

---

## Workflow: Plan → Evaluate → Execute

**Never jump straight to implementation.** Every non-trivial change requires:

1. **Plan** — write or review the planning document with clear phases, acceptance criteria, and manual verification steps
2. **Evaluate** — think carefully about the plan; identify issues, gaps, edge cases
3. **Update** — incorporate evaluation feedback before proceeding
4. **Execute** — implement only after the plan is reviewed and approved by the user

Planning documents live in **`plans/`** and use naming convention `NNN_description.md` (e.g., `276_add_sharpe_ratio.md`). They must include:
- Numbered phases with Red/Green/Refactor stages
- Concrete acceptance criteria (checkboxes)
- Manual verification steps

The Claude Code `/plan` command (Plan mode) is the right tool for drafting new plans. Save them to `plans/`.

---

## Workflow: Evaluation

The project uses structured evaluations to assess current state before deciding next steps. See `plans/evaluation_instructions.md` for the full evaluation rubric and output format.

To run an evaluation:
1. Use the evaluation rubric to assess architecture, financial realism, risk/performance analysis, reproducibility, and interview usefulness
2. Write output to `plans/evaluation_output_YYYYMMDDHHMM.md`
3. Use `plans/evaulation_mins_create_action_plan.md` to convert the top finding into a concrete next plan item

---

## Code Standards

- **Python 3.10+**, type hints, dataclasses, no hidden globals
- **Imports at top of file** unless there is an overriding reason
- **Line length under 120 characters**
- **Functions under 40 lines**
- **Descriptive function names**

### Docstrings: Explain Reasoning

Include reasoning for modules, classes, and significant functions. Explain *why* the object exists, *what problem* it solves, and *how* it fits into the architecture.

```python
# ✅ Good
"""MarketSnapshot — ts, underlying_bar, option_quotes.

Single typed snapshot at bar-close time. Strategy receives snapshot, never raw DataFrames.
underlying_bar=None when no bar at ts; option_quotes=None when not requested.
"""

# ✅ Good class docstring
@dataclass
class Bars:
    """Time-ordered series of OHLCV bars. Timestamps must be monotonic increasing.

    Reasoning: DataProvider returns Bars not DataFrames. Monotonic ts required
    for as-of lookups and iteration.
    """
```

---

## Test-First (Red-Green-Refactor)

Every implementation phase follows this cycle:

| Stage | What to do |
|-------|-----------|
| **Red** | Write tests that specify expected behavior. Run them — they must fail. |
| **Green** | Write minimal code to make tests pass. Run them — they must pass. |
| **Refactor** | Clean up while keeping tests green. |

Never write implementation code without a failing test first.

Test locations mirror `src/` structure within each sub-project (e.g., `backtester/tests/`, `observer/backend/tests/`).

---

## Manual Verification Required

"Tests pass" is necessary but not sufficient. Every implementation step must include concrete manual verification:

```
# ✅ Good — concrete and verifiable
1. Start backend: make observer-backend
2. curl http://localhost:8000/api/health → status "ok"
3. Open http://localhost:5173 → verify specific UI element
4. Run backtest: make backtester-run BACKTESTER_CONFIG=configs/taa_example.yaml

# ❌ Bad — vague
1. Start the app
2. Verify it works
```

---

## Location Citations

When answering questions about where something is in the code, include file and line references. Use VSCode-compatible markdown links:

```
[file.py:42](backtester/src/loader/file_loader.py#L42)
```

Or for a range: `[file.py:57-74](backtester/src/loader/file_loader.py#L57-L74)`

---

## No Unapproved Dependencies

Never add a new third-party library without explicitly asking first. This is especially critical for libraries that handle credentials, external APIs, or network communication.

```
# ✅ Good — ask first
"I'd recommend using `some-lib` for this. It handles X and Y. Should I add it?"

# ❌ Bad — silently add to pyproject.toml / package.json
```

---

## No Proactive Cost Decisions

Never select options that incur financial cost (cloud billing, paid APIs, paid tiers) without explicit user approval. Always present cost implications and wait for approval.

---

## Secrets and Config — Never Committed

These files are gitignored and must stay that way:
- `.env` — API keys, credentials, ports
- `config.yaml` — user-specific strategy/engine config
- `schwab_token.json` — OAuth tokens
- `*.db` — SQLite databases

Only `.example` templates (`.env.example`, `config.example.yaml`) get committed. When creating new config or secret files, add to `.gitignore` and provide a committed example template.

---

## Prefer Library Components (Frontend)

The frontend uses **MUI / Material UI**. Always check its component catalog before building custom elements.

```tsx
// ✅ Good — use MUI LinearProgress
<LinearProgress variant="determinate" value={pct} sx={{ height: 4 }} />

// ❌ Bad — custom progress bar when MUI has one
<Box sx={{ height: 4, bgcolor: 'green', width: `${pct}%` }} />
```

---

## Planning Documents

All plans live in **`plans/`** — this directory is gitignored except for `runs/showcase/`. Plans are working artifacts for the development process and stay separate from product code.

When creating a new plan, find the highest existing `NNN_` number in `plans/` and increment by one.
