# ADR-001: Thin Shell Integration for Observer + Backtester

## Status

Accepted

## Context

The markets repo has two major capabilities—Observer (live observation) and Backtester (historical simulation)—that should be usable from a single frontend without merging their internals. A thin unified shell is needed to simplify clone/build/run while keeping domain engines separate.

## Decision

### Root `runs/` location for backtest artifacts

All backtest output is written to a **repo-root `runs/`** directory. This replaces `backtester/runs/` as the default output location. Naming convention for run directories: `runs/{timestamp}_{config_stem}/` (e.g. `runs/20260316_123456_tactical_asset_allocation_example/`).

### Unified backend entry point

The **observer backend** serves as the single API entry point. All HTTP routes—existing observer routes and new backtester routes—are exposed from this process. There is no separate backtester API server.

### Two-tab frontend

The frontend uses a **tabbed layout** with two tabs:

- **Observer** — existing observer UI, behavior unchanged
- **Backtester** — config dropdown, run button, result panel (success/failure, run dir, report path)

### V1 Backtester API contract

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/backtester/configs` | Returns list of runnable config files from `backtester/configs/` |
| POST | `/api/backtester/runs` | Launches a backtest for the selected config |

**GET /api/backtester/configs** response shape:

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

**POST /api/backtester/runs** request:

```json
{
  "config_path": "backtester/configs/tactical_asset_allocation_example.yaml"
}
```

**POST /api/backtester/runs** response (success):

```json
{
  "ok": true,
  "config_path": "backtester/configs/tactical_asset_allocation_example.yaml",
  "run_dir": "runs/20260316_123456_tactical_asset_allocation_example",
  "report_path": "runs/20260316_123456_tactical_asset_allocation_example/report.html",
  "summary_path": "runs/20260316_123456_tactical_asset_allocation_example/summary.json"
}
```

### What is NOT unified

| Area | Decision |
|------|----------|
| **Domain engines** | Observer and backtester logic remain separate. Do not merge internals. |
| **Execution model** | Observer stays live/streaming; backtester stays deterministic and historical. |
| **Strategy integration** | Strategizer HTTP/library model is unchanged. Backtester uses strategizer in-process. |
| **Artifact storage** | Artifacts remain file-based. No DB-backed run storage in V1. |

### Config path validation

The POST `/api/backtester/runs` endpoint accepts **only** config paths under `backtester/configs/`. Paths must be validated to:

- Resolve within `backtester/configs/`
- Reject path traversal (e.g. `../` outside that directory)
- Match one of the configs enumerated by `GET /api/backtester/configs`

Arbitrary filesystem paths are not accepted.

## Consequences

- Single `make run` starts the unified app
- Backtest output is visible at repo-root `runs/`
- Backtester CLI (`make backtester-run`) remains supported
- V1 scope is intentionally limited; config editing, run history browser, and artifact explorer are deferred
