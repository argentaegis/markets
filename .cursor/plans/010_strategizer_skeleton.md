---
name: 010 Strategizer Skeleton
overview: "Create strategizer package structure, pyproject.toml, .gitignore, and verify install. First buildable artifact. Types may exist from prior scaffolding; step 020 tests and refines them."
todos: []
isProject: false
---

# 010: Strategizer Skeleton

Conforms to [000_strategizer_mvp_plan.md](000_strategizer_mvp_plan.md) §6.

---

## Existing Foundation

- strategizer is a separate git repo (git initialized)
- Project may already be partially scaffolded from prior work
- This step verifies completeness, adds .gitignore, and confirms install works

---

## Objective

Establish the strategizer package skeleton so that subsequent steps have a stable home. After this step: the package installs, pytest runs, the module structure exists, and .gitignore covers build artifacts. Types and protocols may already exist (from prior scaffolding); step 020 tests and refines them. ORB remains a placeholder.

---

## Module Layout (from 000 §6)

```
strategizer/
├── .gitignore
├── pyproject.toml
├── README.md
├── .cursor/plans/               # shared planning documents
├── src/
│   └── strategizer/
│       ├── __init__.py
│       ├── types.py             # BarInput, PositionView, Signal
│       ├── protocol.py          # PortfolioView, ContractSpecView, Requirements
│       ├── base.py              # Strategy ABC
│       └── strategies/
│           ├── __init__.py
│           └── orb_5m.py        # placeholder (step 030)
└── tests/
    └── __init__.py
```

---

## Implementation Phases

### Phase 0: .gitignore (standalone repo)

| Task | Detail |
|------|--------|
| .gitignore | Python: `__pycache__/`, `.venv/`, `*.egg-info/`, `dist/`, `.pytest_cache/`. IDE: `.idea/`, `.vscode/`. |

### Phase 1: Verify pyproject.toml

| Task | Detail |
|------|--------|
| Project metadata | name, version, description, requires-python >= 3.10 |
| Build system | setuptools |
| Package discovery | `[tool.setuptools.packages.find] where = ["src"]` |
| Dev dependencies | pytest in optional-dependencies |
| Pytest config | testpaths = ["tests"] |

### Phase 2: Verify package structure

| Task | Detail |
|------|--------|
| Package layout | src/strategizer/ with __init__.py |
| Subpackages | strategies/ with __init__.py |
| Test directory | tests/ with __init__.py |

### Phase 3: Install and verify

| Task | Detail |
|------|--------|
| Install | `pip install -e .` succeeds from strategizer/ |
| Import | `from strategizer.types import BarInput` works |
| Pytest | `pytest` runs (0 or placeholder tests, no errors) |

---

## Acceptance Criteria

- [ ] `.gitignore` exists (Python, IDE artifacts)
- [ ] `strategizer/pyproject.toml` exists with setuptools build, Python >= 3.10
- [ ] `src/strategizer/` package exists with __init__.py
- [ ] `pip install -e .` succeeds from strategizer/
- [ ] `pytest` runs without errors
- [ ] README.md documents installation and local dev path dependency

---

## Out of Scope

- Type tests and refinements (step 020)
- ORB strategy logic (step 030)
