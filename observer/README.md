# Observer — Market Observer + Trade Recommender

A **manual algo / algorithm-augmented mechanical trading** tool that ingests live market data from pluggable providers, shows market state and recommendations on the same screen, and lets you define strategies that emit trade candidates (entry/exit), not orders.

## V1 Focus

- **Asset class:** Futures (ES/NQ)
- **Data source:** Pluggable providers (SimProvider for dev, Schwab for live)
- **Output:** Trade candidates with "why" bullets, ranked, with validity windows
- **No auto execution** — observation and recommendation only

## Architecture

```
Provider Adapter → Normalizer → Market State Store → Strategy Engine → Recommendation Store → UI
```

| Module | Responsibility |
|--------|----------------|
| `core/` | Canonical types (Instrument, Quote, Bar, TradeCandidate, etc.) |
| `providers/` | Pluggable data ingestion (SimProvider, SchwabProvider) |
| `state/` | Current market truth (latest quotes, rolling bar windows) |
| `strategies/` | User-defined strategies that emit TradeCandidate[] |
| `engine/` | Evaluation scheduler, candidate store, ranking |
| `api/` | FastAPI backend (WebSocket + REST) |
| `frontend/` | React + TypeScript + MUI dashboard |

## Prerequisites

- Python 3.10+
- Node.js 18+
- GNU Make

## Setup

### 1. Environment variables

```bash
cp .env.example .env
```

Edit `.env` to configure your provider. Use `OBSERVER_PROVIDER=sim` for development (no API keys needed) or `OBSERVER_PROVIDER=schwab` for live data (requires Schwab API credentials).

### 2. Strategy config

```bash
cp backend/config.example.yaml backend/config.yaml
```

Edit `backend/config.yaml` to enable/disable strategies and configure watchlists. Without this file, defaults apply (DummyStrategy enabled, SimProvider).

### 3. Install dependencies

```bash
make install
```

Or manually:

```bash
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
cd frontend && npm install
```

## Starting the Application

### Start backend

```bash
make backend
```

The API server starts at `http://localhost:8000` (configurable via `BACKEND_PORT` in `.env`).

### Start frontend

```bash
make frontend
```

The dashboard opens at `http://localhost:5173` (configurable via `FRONTEND_PORT` in `.env`). It proxies API requests to the backend automatically.

## Other Commands

```bash
make help       # Show all available commands
make test       # Run backend tests
make test-v     # Run backend tests (verbose)
make lint       # Lint frontend code
make install    # Install all dependencies (backend + frontend)
```

### Skip network-dependent tests

```bash
cd backend && python -m pytest -m "not network"
```

### Start backend with SQLite persistence

Set `OBSERVER_DB_PATH=observer.db` in `.env`, then `make backend`.

### Frontend production build

```bash
cd frontend
npm run build
npm run preview
```

## Configuration Reference

### `.env` — environment / secrets (gitignored)

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_PORT` | `8000` | Port for the backend API server |
| `FRONTEND_PORT` | `5173` | Port for the frontend dev server |
| `OBSERVER_PROVIDER` | `sim` | Data provider: `sim` or `schwab` |
| `OBSERVER_DB_PATH` | *(unset)* | SQLite path for state persistence; unset = disabled |
| `OBSERVER_CONFIG` | `config.yaml` | Path to strategy/engine config file |
| `SCHWAB_API_KEY` | — | Schwab API key (required for schwab provider) |
| `SCHWAB_APP_SECRET` | — | Schwab app secret (required for schwab provider) |
| `SCHWAB_CALLBACK_URL` | — | OAuth callback URL |
| `SCHWAB_TOKEN_PATH` | `./schwab_token.json` | Path to cached OAuth token |
| `SCHWAB_ACCOUNT_ID` | — | Schwab account ID |

### `backend/config.yaml` — strategy / engine config (gitignored)

See `backend/config.example.yaml` for a documented template. Controls which strategies are enabled, watchlist symbols, and engine parameters.
