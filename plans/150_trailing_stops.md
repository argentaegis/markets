---
name: 150 Trailing Stops
overview: Add trailing stop support to backtester and trend_entry_trailing_stop strategy. Depends on Plan 140.
todos: []
isProject: false
---

# 150: Trailing Stops and Trend Entry Strategy

## Summary

Add broker-managed trailing stop support to the backtester and implement the trend_entry_trailing_stop strategy in the strategizer service. Depends on Plan 140 (Strategizer as a service).

## Scope

- **Backtester**: Order.trailing_stop_ticks; TrailingStopManager (high-water for longs, low-water for shorts; synthetic Fill+Order; trigger at tick-aligned price)
- **Strategizer**: trend_entry_trailing_stop — first-cross MA entry (LONG or SHORT) + trailing stop
- **Signal**: trailing_stop_ticks field

## Full Plan

See `.cursor/plans/150_trailing_stops.plan.md` for implementation details.
