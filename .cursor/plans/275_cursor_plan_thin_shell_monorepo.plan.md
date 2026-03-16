---
name: ""
overview: ""
todos: []
isProject: false
---

# Cursor Plan: Thin Unified Shell for Observer + Backtester

## Objective

Create **one thin application shell** over the existing project so both **Observer** and **Backtester** can be used from a single frontend, while keeping the current engines largely intact.

This is **not** a platform rewrite.

The goal is to:

- make the project easier to build and run from a fresh clone
- expose both major capabilities behind one UI
- move the backtest output directory to a visible repo-root `runs/` folder
- shift the repo toward a light monorepo shape without overhauling the underlying engines

## Guiding constraints

- Keep the UI thin
- Do not merge observer and backtester internals into one engine
- Do not redesign strategizer architecture right now
- Do not replace the backtester CLI workflow; keep it working
- Do not build a full job system, queue, or orchestrator
- Do not add broad config editing yet
- V1 backtester UI should only:
  - list current configs
  - allow one to be selected
  - run it

## Current-state assumptions

- `observer/` already contains the user-facing app pieces and should become the shell base
- `backtester/` should remain a config-driven engine called by a thin API wrapper
- `strategizer/` and `portfolio/` remain shared packages
- current backtester artifacts should move from `backtester/runs/` to repo-root `runs/`
- anything beyond listing configs and launching runs remains CLI-only for now

## Intended end state

A fresh user should be able to:

1. clone the repo
2. run one install/build flow
3. run one app-start command
4. open one frontend
5. switch between two tabs:
  - **Observer**
  - **Backtester**

The shell should unify access, not force deep internal convergence.

---

# Product decisions for V1

## What exact screens exist in the single UI?

Use a **tabbed layout**.

### 1. Observer tab

- Keep the existing observer UI behavior as close to current as possible
- No major redesign in this work
- The requirement is integration into the common shell, not observer feature expansion

### 2. Backtester tab

Minimal controls only:

- **Config dropdown** listing current available backtester configs
- **Run button**
- **Run result area** showing:
  - success/failure
  - selected config name
  - created run directory path
  - link to report artifact if available
  - link or reference to the root `runs/` output location

### Optional minimal additions if cheap

Only include if implementation is trivial:

- last run summary snippet
- run start/end timestamp

Do **not** add in V1:

- full config editor
- parameter forms
- run history browser
- artifact explorer UI
- charting UI beyond what already exists in generated artifacts
- job queue dashboard

---

## What backtester operations must be available via API in V1?

Only these:

### `GET /api/backtester/configs`

Returns the list of runnable config files.

Suggested response shape:

```json
{
  "configs": [
    {
      "name": "tactical_asset_allocation_example",
      "path": "backtester/configs/tactical_asset_allocation_example.yaml",
      "label": "tactical_asset_allocation_example.yaml"
    }
  ]
}
```

### `POST /api/backtester/runs`

Launch a backtest for the selected config.

Suggested request:

```json
{
  "config_path": "backtester/configs/tactical_asset_allocation_example.yaml"
}
```

Suggested response:

```json
{
  "ok": true,
  "config_path": "backtester/configs/tactical_asset_allocation_example.yaml",
  "run_dir": "runs/20260316_123456_tactical_asset_allocation_example",
  "report_path": "runs/20260316_123456_tactical_asset_allocation_example/report.html",
  "summary_path": "runs/20260316_123456_tactical_asset_allocation_example/summary.json"
}
```

### Behavior notes

- For V1, synchronous execution is acceptable if the current runtime is tolerable
- If needed, a very thin background-thread wrapper is acceptable, but avoid introducing a queueing system
- The API should call the existing backtester runner rather than reimplementing engine logic

---

## What remains CLI-only for now?

Everything else.

That includes:

- creating or editing configs
- passing arbitrary runner arguments
- advanced artifact inspection
- benchmark selection
- strategy parameter editing
- multi-run comparison
- run-history management
- data catalog management
- observer/backend internals
- any strategizer HTTP work

---

## What root commands should a fresh user run?

Target the following root-level experience:

### Install/build

```bash
make install
make build
```

### Run everything

```bash
make run
```

### Optional developer commands

Keep or clean up as needed:

```bash
make test
make check
make observer-backend
make observer-frontend
make backtester-run BACKTESTER_CONFIG=backtester/configs/tactical_asset_allocation_example.yaml
```

## Makefile direction

Keep the root `Makefile` as the primary entry point and simplify it around these ideas:

### Must-have targets

- `make install` — install all Python + frontend dependencies
- `make build` — build all packages and frontend
- `make test` — run all tests/lint
- `make run` — start the unified API + frontend flow
- `make check` — build + test

### Keep but de-emphasize

- `make observer-backend`
- `make observer-frontend`
- `make backtester-run`

### `make run` behavior

V1 should start:

- the unified backend/API process
- the unified frontend dev server

If one-command process supervision is awkward, acceptable implementations include:

- shell backgrounding plus `wait`
- a small Python launcher script
- `concurrently`/similar lightweight frontend tooling if already compatible

Avoid:

- Docker-compose-only dev startup
- adding heavy orchestration just to satisfy `make run`

---

## What pieces are being unified at the shell level vs intentionally kept separate?

## Unified at the shell level

### Frontend shell

- one app shell
- one navigation layout
- two tabs: Observer / Backtester

### Backend entry point

- one top-level API entry point for the shell
- observer routes remain available
- new backtester routes are added alongside them

### Dev/build workflow

- one install flow
- one build flow
- one run flow

### Output visibility

- one repo-root `runs/` directory for generated backtest artifacts

## Intentionally kept separate

### Domain engines

- observer logic remains observer logic
- backtester remains a config-driven runner/engine

### Execution model

- observer stays oriented to current/live observation
- backtester stays deterministic and historical

### Strategy integration mode

- do not solve the strategizer HTTP/library mismatch in this task
- backtester keeps using strategizer in-process
- observer can keep current behavior

### Artifact model

- generated backtest artifacts stay file-based
- do not move to DB storage in V1

---

# Recommended architecture for V1

## Preferred approach

Use the **existing observer app as the shell base**, then add a thin backtester API surface.

### Why

- lowest disruption
- fastest path to a single UI
- preserves current backtester architecture
- avoids a fake-clean rewrite that would consume time without increasing capability

## Suggested structure direction

Do not force a full re-layout immediately, but move toward this shape:

```text
markets/
  backtester/
  observer/
    backend/
    frontend/
  portfolio/
  strategizer/
  runs/
  Makefile
```

If later desired, this can evolve further toward:

```text
markets/
  apps/
    api/
    web/
  packages/
    backtester/
    observer_core/
    portfolio/
    strategizer/
  runs/
```

But that is **not** required for this task.

---

# Work plan

## Phase 1: Define the thin integration boundary

### Goal

Create a small, explicit contract for the unified shell.

### Tasks

- decide where the unified backend entry point will live
- decide whether the existing observer frontend becomes the main app shell
- define the two-tab layout
- define the two V1 backtester endpoints
- define the response payload for launched runs
- define the root `runs/` location and naming convention

### Deliverable

A short integration note or ADR committed to the repo.

### Acceptance criteria

- there is a written statement of what is unified vs not unified
- there is a fixed V1 API contract
- there is a clear decision on root `runs/`

---

## Phase 2: Move backtest artifacts to repo-root `runs/`

### Goal

Make generated output more visible and consistent across shell usage.

### Tasks

- update backtester default output path from `backtester/runs/` to root `runs/`
- update any README references
- update any Makefile/help text references
- update any committed showcase references if needed
- verify existing artifact generation still works
- ensure paths are resolved robustly whether command is run from repo root or subdirectory

### Important implementation note

Avoid fragile relative-path behavior.

Use a repo-root-aware path strategy instead of assuming the current working directory is always the same.

### Acceptance criteria

- running a backtest from the standard root workflow writes to `runs/`
- generated artifacts remain unchanged in content
- docs consistently reference the root `runs/` directory

### Risk

This step can break README links, showcase references, or any code assuming `backtester/runs/`.

---

## Phase 3: Add thin backtester API endpoints

### Goal

Expose the minimum backtester operations needed for the UI.

### Tasks

- add `GET /api/backtester/configs`
- add `POST /api/backtester/runs`
- enumerate runnable config files from `backtester/configs/`
- validate selected config path against that directory
- invoke the existing backtester runner
- return run directory and artifact paths in the response

### Guardrails

- do not duplicate runner logic in API code
- do not parse and execute arbitrary filesystem paths without validation
- do not add generic command execution interfaces

### Acceptance criteria

- API lists available configs
- API launches a selected config successfully
- output lands in root `runs/`
- invalid config selections are rejected cleanly

### Security note

The config-run endpoint must only allow known configs from the intended config directory. Do not accept arbitrary path traversal.

---

## Phase 4: Create the unified frontend shell

### Goal

Expose observer and backtester behind one frontend.

### Tasks

- add a top-level tabbed layout
- preserve existing observer content under the Observer tab
- add a Backtester tab with:
  - config dropdown
  - run button
  - run-result panel
- call the new API routes
- display returned run/report paths cleanly

### Acceptance criteria

- the user can launch the app from one frontend
- switching tabs does not break observer
- user can run a backtest from the UI
- success/failure is visible without opening terminal logs

### UX rule

Keep this sparse and functional. No fancy dashboarding.

---

## Phase 5: Clean up root developer workflow

### Goal

Make fresh-clone usage simpler.

### Tasks

- update root `Makefile`
- add a `make run` target
- ensure `make build` builds all components
- ensure `make install` handles Python + frontend deps
- verify one-command startup behavior
- document the minimal root workflow in the root README

### Acceptance criteria

- a fresh user can follow root README only
- install/build/run is possible from the repo root
- shell startup is simpler than today

---

# Suggested implementation order

1. define the integration boundary in writing
2. move `runs/` to the repo root
3. add thin backtester API endpoints
4. add Backtester tab to the existing frontend shell
5. clean up root `Makefile` and README

This order minimizes the chance of UI work getting blocked by path confusion.

---

# API and UI contracts

## Backtester config list contract

Each config entry should provide at least:

- `name`
- `path`
- `label`

Optional if cheap:

- `strategy_name`
- `data_type` (`fixture` or `catalog`)
- `description`

If metadata is not easy to derive safely, skip it in V1.

## Backtester run response contract

Must provide:

- `ok`
- `config_path`
- `run_dir`
- `summary_path` if present
- `report_path` if present
- error message if failed

Do not overdesign this.

---

# Non-goals

Do not do these in this project step:

- rewrite observer as a generic platform
- convert the repo fully into `apps/` and `packages/` immediately
- move all code to a shared web/backend framework
- build config authoring UI
- build artifact explorer UI
- add user auth
- add persistent DB-backed run storage
- introduce Celery, Redis, Kafka, or similar infrastructure
- redesign strategizer transport model
- remove CLI workflows

---

# Risks and mitigations

## Risk 1: Over-scoping the shell work

This can easily become a broad platform rewrite.

### Mitigation

Keep V1 to:

- two tabs
- two new API endpoints
- root `runs/`
- one root `make run`

## Risk 2: Breaking the backtester artifact story

Moving `runs/` can break showcase references, tests, scripts, and README links.

### Mitigation

Treat the root `runs/` move as a first-class step with explicit verification.

## Risk 3: Weak path handling

Running commands from different directories may break file resolution.

### Mitigation

Standardize on repo-root-aware path resolution.

## Risk 4: Expanding UI requirements too early

Once a Backtester tab exists, it becomes tempting to add parameter editing and charts.

### Mitigation

Hold the line: dropdown + run button + result panel only.

---

# Done definition for V1

This work is done when all of the following are true:

- one frontend exposes **Observer** and **Backtester** tabs
- observer still works
- backtester tab lists current configs
- backtester tab can launch a selected config
- backtester output goes to repo-root `runs/`
- the API surface for V1 is limited and thin
- the backtester CLI still works
- `make install`, `make build`, and `make run` are documented and functional from repo root
- the repo is easier to clone, build, and demo than before

---

# Cursor execution instructions

Implement this in small, reviewable steps.

## Working rules

- preserve existing behavior where possible
- prefer adapters and wrappers over rewrites
- do not merge unlike systems prematurely
- keep the UI minimal
- keep the backtester runner authoritative
- keep the CLI path functional
- update docs as part of the work, not afterward

## Deliver changes in this order

1. integration note / ADR
2. root `runs/` path migration
3. backtester API routes
4. Backtester tab UI
5. Makefile + README cleanup

## For each step, provide

- files changed
- why each change was needed
- what remains intentionally deferred
- any follow-up risks or TODOs

---

# Most important next step

Start by writing the thin integration note and locking down the **root `runs/` decision** before touching UI code.

That is the highest-leverage first move because it stabilizes:

- path assumptions
- API design
- shell boundaries
- what this change is **not** trying to do

