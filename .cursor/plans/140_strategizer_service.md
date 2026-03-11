---
name: 140 Strategizer Service
overview: Strategizer runs as a REST JSON service. All strategies live in strategizer; backtester and observer call via HTTP. Stateless, no Portfolio dependency.
todos: []
isProject: false
---

# 140: Strategizer as a Service

## Summary

Strategizer becomes a standalone REST service (like observer backend). Backtester and Observer remove the strategizer package dependency and call the service via HTTP. Strategies are stateless (step_index in request). Strategy params passed per request (Option A: `strategy_params` in body). No Portfolio dependency; strategies use entry-only or broker-managed exits.

## Prerequisite

Before starting: current backtester and observer must run successfully with in-process strategizer. All four strategies must pass golden and integration tests.

## Strategies (No Portfolio Required)

| Strategy | Type | Exit |
|----------|------|------|
| orb_5m | Entry only | Stop at entry |
| buy_and_hold | Entry only | Option expiry |
| buy_and_hold_underlying | Entry only | Hold to end |
| covered_call | Time-based | step_index == exit_step |

Trailing stops and trend_entry_trailing_stop: Plan 150.

## Key Decisions

- **API**: REST, JSON
- **State**: Stateless (step_index per request)
- **Strategy params**: `strategy_params` in request body (Option A)
- **Portfolio**: Future plan
- **Trailing stops**: Deferred to Plan 150
- **Types**: UTC internally; Central for UI (see types_and_standards.md)

## Full Plan

See `.cursor/plans/140_strategizer_service.plan.md` for implementation details.
