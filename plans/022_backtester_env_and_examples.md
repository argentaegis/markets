# Step 022: env and env.example

## Goal

Add `.env` and `.env.example` for environment settings. `.env` is the king — the sole source of settings. Load it on startup; do not rely on shell/global env. No config overrides from env.

## Current State

- [src/marketdata/providers/polygon.py](src/marketdata/providers/polygon.py) reads `POLYGON_API_KEY` from `os.environ`
- [.gitignore](.gitignore) already ignores `.env`

## Implementation

### 1. Add python-dotenv

**[pyproject.toml](pyproject.toml)** — add `python-dotenv` to dependencies

### 2. Create .env.example

**`.env.example`** — template (no secrets):

```
# Market data — Polygon.io (required for fetch)
POLYGON_API_KEY=
```

Commit `.env.example`; do not add to `.gitignore`.

### 3. Load .env at startup (Option A)

Load in [src/marketdata/cli.py](src/marketdata/cli.py) at top of `main()`:

```python
from dotenv import load_dotenv
load_dotenv(override=True)
```

`override=True` ensures `.env` overrides any existing `os.environ` — .env is king.

### 4. Update README

**[README.md](README.md)** — Add env setup:

- Copy `.env.example` to `.env`
- Fill in `POLYGON_API_KEY`
- `.env` is gitignored; never commit secrets

## Files

| File | Action |
|------|--------|
| `.env.example` | Create |
| `pyproject.toml` | Add python-dotenv |
| `src/marketdata/cli.py` | Add `load_dotenv(override=True)` at start of main() |
| `README.md` | Document env setup |
