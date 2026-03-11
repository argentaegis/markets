# 210: Portfolio Package Skeleton

Conforms to [200_portfolio_project_evaluation.md](200_portfolio_project_evaluation.md).

---

## Objective

Create the portfolio package directory structure, pyproject.toml, and empty modules. Installable with `pip install -e .` after this step.

---

## Deliverables

### Directory Structure

```
portfolio/
├── pyproject.toml
├── src/
│   └── portfolio/
│       ├── __init__.py
│       ├── domain.py
│       ├── protocols.py
│       └── accounting.py
└── tests/
    └── __init__.py
```

### pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "portfolio"
version = "0.1.0"
description = "Shared portfolio state and accounting for markets ecosystem"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Key points:
- Zero dependencies (stdlib + dataclasses only)
- Same build system as strategizer (setuptools)
- `src/` layout matching strategizer convention

### `__init__.py`

Re-export public API for convenience imports:

```python
from portfolio.domain import Position, PortfolioState
from portfolio.protocols import FillLike, OrderLike
from portfolio.accounting import (
    apply_fill,
    mark_to_market,
    settle_positions,
    assert_portfolio_invariants,
)
```

### Empty Modules

- `domain.py`: docstring only
- `protocols.py`: docstring only
- `accounting.py`: docstring only

---

## Verification

- `cd portfolio && pip install -e .` succeeds
- `python -c "import portfolio"` succeeds
- No linter errors

---

## Files

| File | Action |
|------|--------|
| portfolio/pyproject.toml | Create |
| portfolio/src/portfolio/__init__.py | Create |
| portfolio/src/portfolio/domain.py | Create (empty) |
| portfolio/src/portfolio/protocols.py | Create (empty) |
| portfolio/src/portfolio/accounting.py | Create (empty) |
| portfolio/tests/__init__.py | Create (empty) |
