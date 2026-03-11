# Markets

Deterministic backtesting and strategy-evaluation demo project for options and futures research.

This repo is built to demonstrate clean trading-system design: typed configs, reproducible runs, shared strategy logic, shared portfolio/accounting, and artifact generation. It is **not** a production trading platform.

## Architecture

The backtester flow is:

`config -> data -> signal -> execution -> portfolio -> report`

- `config`: YAML/JSON run definition parsed by `backtester/src/runner.py`
- `data`: local file data provider loading underlying bars and option quotes
- `signal`: strategies from `strategizer/`
- `execution`: broker + fill model apply simplified fills and fees
- `portfolio`: shared accounting in `portfolio/`
- `report`: CSV, JSON, and HTML run artifacts in `backtester/runs/`

## Strategizer Modes

`strategizer/` is used in two different ways in this repo:

- `backtester/` imports strategies **in-process** through `StrategizerStrategy`; no HTTP service is required
- `observer/` still talks to strategizer over **HTTP** through its backend adapter

That means startup order depends on what you are running:

- For `backtester/`: install dependencies and run a config directly
- For `observer/`: start strategizer first, then the observer backend and frontend

## Projects

| Dir | Purpose |
|-----|---------|
| `backtester/` | Deterministic backtesting engine for options and futures. Produces CSV/JSON/HTML artifacts from config-driven runs. |
| `strategizer/` | Shared strategy package used directly by the backtester and exposed over HTTP for the observer app. |
| `portfolio/` | Shared portfolio state and accounting package: fills, mark-to-market, settlement, and invariant checks. |
| `observer/` | Live market observer app. Its backend uses the strategizer HTTP service. |

## Common Commands

The repo root now includes a `Makefile` so you can run common tasks without changing directories first.

```bash
make venv
make install
make help
make build
make test
make check
make backtester-run BACKTESTER_CONFIG=configs/orb_5m_example.yaml
make observer-backend
make observer-frontend
```

The root `Makefile` uses a shared root `.venv` for all Python projects.

### Backtester

From `backtester/`:

| Command | Description |
|---------|-------------|
| `pip install -e .` | Install the backtester package |
| `python -m src.runner configs/buy_and_hold_example.yaml` | Option buy-and-hold example |
| `python -m src.runner configs/covered_call_example.yaml` | Covered-call example |
| `python -m src.runner configs/buy_and_hold_underlying_example.yaml` | Underlying buy-and-hold example |
| `python -m src.runner configs/orb_5m_example.yaml` | Futures ORB example using 1m bars |

See `backtester/README.md` for modeling assumptions, tracked example configs, and the current showcase run.

### Strategizer Service

From `strategizer/`:

| Command | Description |
|---------|-------------|
| `pip install -e .` | Install the strategy package |
| `python -m strategizer` | Start the HTTP service at `http://localhost:8001` |

This service is needed for `observer/`, not for `backtester/`.

### Observer

From `observer/`:

| Command | Description |
|---------|-------------|
| `make install` | Install backend + frontend dependencies |
| `make backend` | Start API server at `http://localhost:8000` |
| `make frontend` | Start dev server at `http://localhost:5173` |

Run `make backend` and `make frontend` in separate terminals. `observer/` still requires strategizer on port `8001`.
