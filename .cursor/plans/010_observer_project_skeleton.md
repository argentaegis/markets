---
name: 010 Project Skeleton
overview: "Initialize git repo, create folder structure, backend pyproject.toml with hatchling + pytest config, frontend scaffold (React+Vite+TS+MUI), virtual environment, .gitignore, .env.example, and README. First buildable artifact."
todos: []
isProject: false
---

# 010: Project Skeleton + Dev Tooling

Conforms to [000_observer_mvp_initial_plan.md](000_observer_mvp_initial_plan.md).

---

## Note on Red-Green-Refactor

This step is pure scaffolding — there is no testable logic yet. Red-Green-Refactor applies from step 020 onward where there are real domain types and behavior to test. This step uses a **Create + Verify** approach instead.

---

## Objective

Create the project skeleton so that all subsequent steps have a stable home. After this step: the git repo is initialized, the backend installs and pytest runs, and the frontend dev server starts. No real application content yet.

---

## Existing Foundation

- `planning/` directory with 000 and 001 documents
- `.cursor/rules/` with code-standards.mdc and location-citations.mdc

---

## Module Layout

```
observer/
  .git/                          # initialized in Phase 0
  .gitignore
  .env.example
  README.md
  planning/                      # planning docs (already exists)
  backend/
    pyproject.toml               # Python package config (hatchling + pytest config)
    .venv/                       # virtual environment (gitignored)
    src/
      __init__.py
      core/                      # canonical types (step 020)
        __init__.py
      providers/                 # data providers (step 030)
        __init__.py
      state/                     # market state store (step 040)
        __init__.py
      strategies/                # user strategies (step 050)
        __init__.py
      engine/                    # scheduler + evaluator (step 060)
        __init__.py
      api/                       # FastAPI app (step 070)
        __init__.py
    tests/                       # project-level integration tests (step 070+)
      __init__.py
      integration/
        __init__.py
  frontend/
    package.json
    tsconfig.json
    vite.config.ts
    index.html
    src/
      main.tsx
      App.tsx
```

---

## Implementation Phases

### Phase 0: Git initialization + project-level files

| Task | Detail |
|------|--------|
| `git init` | Initialize the repository |
| `.gitignore` | Python: `__pycache__/`, `.venv/`, `*.egg-info/`, `dist/`, `.pytest_cache/`. Node: `node_modules/`, `dist/`. Env: `.env`, `*.db`. IDE: `.idea/`, `.vscode/` (keep `.cursor/`). |
| `.env.example` | M0-relevant only: `OBSERVER_PROVIDER=sim`, `OBSERVER_LOG_LEVEL=INFO`. Schwab keys added by step 100 when actually needed. |
| `README.md` | Project overview, architecture summary, quickstart (backend + frontend commands). |

### Phase 1: Backend scaffold

| Task | Detail |
|------|--------|
| Virtual environment | `cd backend && python -m venv .venv && source .venv/bin/activate` |
| `pyproject.toml` | See **pyproject.toml specification** below. |
| Package directories | Create `backend/src/__init__.py` and empty subpackage `__init__.py` files for core, providers, state, strategies, engine, api. Create `backend/tests/__init__.py` and `backend/tests/integration/__init__.py`. |
| Install + verify | `pip install -e .` succeeds. `pytest` runs (0 tests collected, no errors). |

### Phase 2: Frontend scaffold

| Task | Detail |
|------|--------|
| Scaffold | `npm create vite@latest frontend -- --template react-ts` (or equivalent manual setup in `frontend/`). |
| Install MUI | `npm install @mui/material @emotion/react @emotion/styled @fontsource/roboto` |
| Minimal App | `App.tsx` renders an MUI `<Container>` with placeholder text ("Observer — Market Observer + Trade Recommender"). Import Roboto font in `main.tsx`. |
| Verify | `npm install && npm run dev` starts Vite dev server. Page loads in browser at `http://localhost:5173`. |

### Phase 3: Initial commit

| Task | Detail |
|------|--------|
| Stage and commit | `git add . && git commit -m "010: project skeleton"` |

---

## pyproject.toml Specification

Must match backtester conventions. Key sections:

```toml
[project]
name = "observer-backend"
version = "0.1.0"
description = "Market Observer + Trade Recommender backend"
requires-python = ">=3.10"
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "websockets",
    "pydantic",
    "pyyaml",
    "python-dotenv",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests/integration"]
pythonpath = ["src"]
markers = [
    "network: tests that call external APIs (skip with -m 'not network')",
    "integration: project-level integration tests",
]
```

`testpaths` starts with `tests/integration` only. Each subsequent step (020, 030, etc.) appends its module's test directory (e.g., `src/core/tests`).

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend package manager | hatchling (PEP 517) | Matches backtester; modern Python packaging |
| Python version | >=3.10 | Matches backtester; required by schwab-py |
| hatch packages | `packages = ["src"]` | Required for hatchling to find source; matches backtester |
| pytest pythonpath | `["src"]` | Allows `from core.instrument import ...` in tests; matches backtester |
| Frontend build tool | Vite | Fast HMR, TypeScript support out of the box |
| UI library | Material UI + Roboto font | Rapid dashboard layout, good table/grid components |
| Monorepo layout | `backend/` + `frontend/` at top level | Clear separation; each has own package manager |
| .env.example scope | M0-relevant keys only | Avoid documenting Schwab keys before step 100; prevents confusion about what's required |

---

## Acceptance Criteria

- [ ] Git repo initialized (`git log` shows initial commit)
- [ ] `backend/pyproject.toml` exists with hatchling build, `packages = ["src"]`, and `[tool.pytest.ini_options]` with `pythonpath = ["src"]`
- [ ] Virtual environment exists at `backend/.venv/`
- [ ] `pip install -e .` succeeds from `backend/` (with venv active)
- [ ] `pytest` runs from `backend/` (0 tests, no errors, correct pythonpath)
- [ ] All subpackage directories exist with `__init__.py`: core, providers, state, strategies, engine, api
- [ ] `backend/tests/integration/` directory exists with `__init__.py`
- [ ] `frontend/package.json` exists with React, Vite, TS, MUI, Roboto dependencies
- [ ] `npm install && npm run dev` starts from `frontend/` without errors
- [ ] `.gitignore` covers Python, Node, .env, .venv, *.db artifacts
- [ ] `.env.example` documents M0 variables only (OBSERVER_PROVIDER, OBSERVER_LOG_LEVEL)
- [ ] `README.md` has project overview and quickstart (backend + frontend)

---

## Out of Scope

- Any actual application code (types, providers, API endpoints)
- Database setup
- Docker/deployment configuration
- CI/CD
