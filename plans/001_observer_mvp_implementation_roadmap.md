---
name: 001 MVP Implementation Roadmap
overview: "Maps 000_observer_mvp_initial_plan.md into discrete, numbered implementation steps. Records locked decisions and dependency order."
todos: []
isProject: false
---

# 001: MVP Implementation Roadmap

This document reorganizes [000_observer_mvp_initial_plan.md](000_observer_mvp_initial_plan.md) into discrete implementation steps. Each step maps to one or more detailed plan files that can be enacted independently. All plans must conform to 000.

---

## Project Practice: Test-First (Red-Green-Refactor)

**Default for this project:** Write tests first, then make them pass, then refactor. Each implementation unit uses discrete stages:

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests that specify the expected behavior. Run tests; they fail. |
| **Green** | Implement minimal code to make the tests pass. Run tests; they pass. |
| **Refactor** | Clean up implementation while keeping tests green. |

Plans structure work as discrete Red -> Green -> Refactor cycles. No implementation code before tests.

---

## Coding Standards

See **`.cursor/rules/code-standards.mdc`** for the authoritative coding standards. That file defines line length, function length, descriptive names, reasoning in docstrings, imports, and type hints.

---

## Decisions Locked In

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Futures data provider (M2) | Schwab API via `schwab-py` | Streaming WebSocket for futures quotes + OHLCV charts; runs natively on macOS; covers equities/options for v2 |
| First strategy (M3) | ORB 5-minute (Opening Range Breakout) | Fast signal, well-defined entry/stop/target, testable with canned data |
| Frontend stack | React + Vite + TypeScript + Material UI | Matches existing preferences; MUI for rapid dashboard layout |
| Backend stack | Python 3.10+ + FastAPI | Fits strategy/backtester reuse and data work |
| Evaluation cadence | Bar close (default 5m) | Recommended by 000; avoids noise from tick-level evaluation |
| Tradovate provider | Parked as 102; do NOT implement unless explicitly requested | Schwab is primary; Tradovate available as future alternative |

---

## Objective (from 000 §Project intent)

Build a **manual algo / algorithm-augmented mechanical trading** tool that:

- Ingests live market data from pluggable providers
- Shows market state + recommendations on the same screen
- Lets user define/enable strategies that emit trade candidates (entry/exit), not orders

---

## Scope Summary

**In scope (V1):** Futures (ES/NQ), pluggable providers, canonical types, SimProvider, market state store, strategy engine, trade candidates with "why" + validity windows, split-view dashboard, bar-close evaluation, config-driven strategy enable/disable, scoring/ranking, journaling.

**Out of scope (V1):** Automated trade execution, AI prediction models, portfolio optimization across strategies, full options chain ingestion.

---

## Architecture Rules (000 — hard constraints)

| ID | Rule |
|----|------|
| P1 | Providers emit only canonical types; no vendor objects leak past the provider layer |
| P2 | Strategies are pure logic; no direct API calls; read from Context, emit TradeCandidate[] |
| P3 | Pipeline has strict boundaries: Provider -> Normalizer -> State Store -> Engine -> Recommendation Store -> UI |
| P4 | All prices normalized to tick size in core/ |
| P5 | Candidates are informational only (no order placement fields in V1) |
| P6 | Providers never throw raw exceptions to engine; wrap and report health |

---

## Discrete Implementation Steps

Steps are ordered per 000 milestones (M0-M5). Each has an associated plan file.

| Step | Name | Description | Plan | Milestone |
|------|------|-------------|------|-----------|
| **010** | Project skeleton + dev tooling | Folder structure, pyproject.toml, frontend scaffold, .gitignore, .env.example, README | [010_project_skeleton.md](010_project_skeleton.md) | M0 |
| **020** | Core canonical types | Instrument, FutureSymbol, ContractSpec, Quote, Bar, DataQuality, TradeCandidate, tick normalization | [020_core_canonical_types.md](020_core_canonical_types.md) | M0 |
| **030** | Provider interface + SimProvider | BaseProvider protocol, SimProvider (fake data), provider stubs | [030_provider_interface_simprovider.md](030_provider_interface_simprovider.md) | M0 |
| **040** | Market State Store | MarketState class, quote/bar tracking, read-only Context view | [040_market_state_store.md](040_market_state_store.md) | M0 |
| **050** | Strategy interface + DummyStrategy | BaseStrategy, Requirements, Context, DummyStrategy | [050_strategy_interface_dummy.md](050_strategy_interface_dummy.md) | M0 |
| **060** | Engine (scheduler + evaluator) | Bar-close scheduler, strategy runner, CandidateStore, validity/invalidation | [060_engine_scheduler_evaluator.md](060_engine_scheduler_evaluator.md) | M0 |
| **070** | Backend API | FastAPI, /ws WebSocket, /api/snapshot REST, wiring | [070_backend_api.md](070_backend_api.md) | M0 |
| **080** | Frontend UI | React + Vite + TS + MUI, split view, market pane, recs pane, details panel | [080_frontend_ui.md](080_frontend_ui.md) | M0 |
| **090** | State persistence + candidate lifecycle | SQLite persistence, candidate retention, invalidation sweep, UI debounce | [090_state_persistence_candidate_lifecycle.md](090_state_persistence_candidate_lifecycle.md) | M1 |
| **100** | Schwab provider integration | SchwabProvider via schwab-py, futures quotes + charts streaming, OAuth auth | [100_schwab_provider.md](100_schwab_provider.md) | M2 |
| **102** | Tradovate provider (PARKED) | Do NOT implement unless explicitly requested | — | — |
| **110** | ORB 5-minute strategy | Opening Range Breakout, entry/stop/target, why bullets, valid_until | [110_orb_5m_strategy.md](110_orb_5m_strategy.md) | M3 |
| **120** | Strategy registry + configuration | Dynamic registry, config.yaml, enable/disable | [120_strategy_registry_config.md](120_strategy_registry_config.md) | M4 |
| **130** | Ranking, throttling, journaling | Score normalization, top-N filtering, per-strategy throttles, SQLite journal | [130_ranking_throttling_journaling.md](130_ranking_throttling_journaling.md) | M5 |

---

## Required Canonical Types (000 §core/)

| Type | Key Fields |
|------|------------|
| Instrument | type (future/equity/option) |
| FutureSymbol | root, contract_code, front_month_alias |
| ContractSpec | tick_size, point_value, session |
| Quote | symbol, bid, ask, last, volume, timestamp, source, quality |
| Bar | symbol, timeframe, open, high, low, close, volume, timestamp |
| TradeCandidate | symbol, direction, entry, stop, targets, score, explain, valid_until, tags |
| DataQuality | STALE, MISSING, PARTIAL |

---

## Required Module Interfaces (000 §Canonical interfaces)

| Module | Core Responsibility | Key Method(s) |
|--------|---------------------|---------------|
| BaseProvider | Connect to data source, emit canonical events | connect, subscribe_quotes, subscribe_bars, disconnect, health |
| BaseStrategy | Read Context, emit candidates | name, requirements, evaluate(ctx) -> list[TradeCandidate] |
| MarketState | Current truth for strategies | update_quote, update_bar, get_context |
| Engine | Schedule evaluation, run strategies, manage candidates | evaluate_on_bar_close, run_strategies, CandidateStore |

---

## Dependency Order

```
010 (Skeleton) -> 020 (Core Types) -> 030 (Provider+Sim)  \
                                   -> 040 (State Store)     -> 060 (Engine) -> 070 (Backend API) -> 080 (Frontend UI)
                                   -> 050 (Strategy+Dummy) /

080 -> 090 (Persistence) -> 100 (Schwab) -> 110 (ORB) -> 120 (Registry) -> 130 (Ranking)
```

- Steps 030, 040, 050 can be developed in parallel after 020.
- Steps 070-080 require 060.
- Steps 100+ are sequential after M0 is working end-to-end.

---

## MVP Acceptance Criteria (000 §Milestones)

MVP (M0) complete when:

- Run one command for backend, one for UI
- See live updating numbers and a sample candidate
- Market + candidates displayed side-by-side

Full V1 (M0-M5) complete when:

- Live ES/NQ data from Schwab populates state store
- ORB 5m strategy produces candidates that make sense vs chart
- Strategies configurable via config.yaml without code changes
- Ranked candidates with no alert flood
- Journal records inspectable in SQLite
