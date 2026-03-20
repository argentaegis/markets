# Claude Code — Backtester Sub-project

See the root [CLAUDE.md](../CLAUDE.md) for all project-wide standards (code standards, workflow, test-first, secrets policy, etc.). This file covers backtester-specific context only.

## Backtester Architecture

Config-driven, deterministic backtesting engine for options and futures. Runs in-process with `strategizer/` — no HTTP service required.

```
src/        # engine source
tests/      # unit and integration tests
configs/    # example YAML configs (committed)
data/       # local market data (gitignored)
runs/       # backtest artifacts (gitignored, except runs/showcase/)
```

## Running Backtests

```bash
# From repo root:
make backtester-run BACKTESTER_CONFIG=backtester/configs/tactical_asset_allocation_example.yaml

# From backtester/:
python -m src.runner configs/buy_and_hold_example.yaml
```

Artifacts appear in repo-root `runs/<timestamp>_*/`.

## Test Locations

Tests live in `backtester/tests/`, mirroring `src/` structure.

```bash
make test-backtester
```

## Manual Verification for Backtester

After any engine change, run a full backtest and verify output artifacts:

```bash
make backtester-run BACKTESTER_CONFIG=backtester/configs/buy_and_hold_example.yaml
# Check that runs/<timestamp>_*/ contains expected CSV/JSON/HTML artifacts
```
