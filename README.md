# Markets

**Primary interview artifact:** a config-driven, deterministic backtesting engine that produces reproducible run artifacts (returns, drawdown, trades, Sharpe, CAGR, turnover). The backtester is the centerpiece of this repo.

This project demonstrates clean trading-system design: typed configs, reproducible runs, shared strategy logic, shared portfolio/accounting, and artifact generation. It is **not** a production trading platform.

## Flagship Showcase

The committed showcase in [`runs/showcase/`](runs/showcase/) includes:

- **Primary run:** `tactical_asset_allocation` — Faber-style TAA across 6 ETFs, closed trades, Sharpe, CAGR, turnover, and [case study](runs/showcase/CASE_STUDY.md) describing strategy, assumptions, and metrics.

Requires catalog data; run: `make backtester-run BACKTESTER_CONFIG=configs/tactical_asset_allocation_example.yaml`

## Architecture

The backtester flow is:

`config -> data -> signal -> execution -> portfolio -> report`

- `config`: YAML/JSON run definition parsed by `backtester/src/runner.py`
- `data`: local file data provider loading underlying bars and option quotes
- `signal`: strategies from `strategizer/`
- `execution`: broker + fill model apply simplified fills and fees
- `portfolio`: shared accounting in `portfolio/`
- `report`: CSV, JSON, and HTML run artifacts in `runs/`

## Strategizer Modes

`strategizer/` is used in two different ways in this repo:

- `backtester/` imports strategies **in-process** through `StrategizerStrategy`; no HTTP service is required
- `observer/` can use strategies via `HttpStrategizerAdapter`, which expects an HTTP service at `STRATEGIZER_URL` (default `http://localhost:8001`). **No HTTP service is included in this repo** — the strategizer package is a library only. For observer development, use `DummyStrategy` (see `backend/config.example.yaml`), or build and run a separate HTTP wrapper.

For `backtester/`: install dependencies and run a config directly. No strategizer service needed.

## Projects

| Dir | Role |
|-----|------|
| `backtester/` | **Primary.** Deterministic backtesting engine for options and futures. Produces CSV/JSON/HTML artifacts from config-driven runs. |
| `strategizer/` | **Support.** Shared strategy package (library only). Backtester imports it in-process. |
| `portfolio/` | **Support.** Shared portfolio state and accounting: fills, mark-to-market, settlement, invariant checks. |
| `observer/` | **Secondary.** Live market observer app. Optional; uses `DummyStrategy` or external strategizer HTTP service (not included). |

## Quick Start

```bash
make install
make build
make run
```

Then open http://localhost:5173 — one app with **Observer** and **Backtester** tabs.

## Common Commands

The repo root now includes a `Makefile` so you can run common tasks without changing directories first.

```bash
make venv
make install
make help
make build
make test
make check
make run
make backtester-run BACKTESTER_CONFIG=configs/buy_and_hold_example.yaml
make observer-backend
make observer-frontend
```

- **`make run`** — Start the unified app (backend + frontend). Observer and Backtester tabs in one UI.
- **`make backtester-run`** — Run a backtest from CLI. Output goes to repo-root `runs/`.

The root `Makefile` uses a shared root `.venv` for all Python projects.

### Backtester (primary artifact)

**Quick start (no data setup):** `make backtester-run BACKTESTER_CONFIG=configs/buy_and_hold_example.yaml` — runs on fresh clone. The flagship TAA showcase requires catalog data.

From `backtester/`:

| Command | Description |
|---------|-------------|
| `pip install -e .` | Install the backtester package |
| `python -m src.runner configs/tactical_asset_allocation_example.yaml` | Flagship TAA (requires catalog) |
| `python -m src.runner configs/buy_and_hold_example.yaml` | Option buy-and-hold (fixture-backed) |
| `python -m src.runner configs/orb_5m_example.yaml` | Futures ORB mechanics example (fixture-backed) |
| `python -m src.runner configs/tactical_asset_allocation_example.yaml` | TAA across 6 ETFs (requires catalog data) |

See `backtester/README.md` for fixture vs catalog configs, modeling assumptions, and showcase runs.

### Strategizer

From `strategizer/`:

| Command | Description |
|---------|-------------|
| `pip install -e .` | Install the strategy package (required by backtester; observer installs it via backend deps) |

The strategizer package is a library — it has no HTTP server or `__main__` entry point. The backtester imports it directly. The observer uses `DummyStrategy` by default; strategies with `source: strategizer` in config expect an external HTTP service (not included in this repo).

### Observer + Backtester (unified shell)

**`make run`** starts both backend and frontend. Open http://localhost:5173 and switch between:
- **Observer** — live market observation and trade recommendations
- **Backtester** — select a config, run a backtest, view results

### Observer (standalone)

From `observer/`:

| Command | Description |
|---------|-------------|
| `make install` | Install backend + frontend dependencies |
| `make backend` | Start API server at `http://localhost:8000` |
| `make frontend` | Start dev server at `http://localhost:5173` |

Run `make backend` and `make frontend` in separate terminals. Observer works with `DummyStrategy` out of the box; no separate strategizer service is required.
