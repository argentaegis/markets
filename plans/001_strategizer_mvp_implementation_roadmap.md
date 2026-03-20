---
name: 001 Strategizer MVP Implementation Roadmap
overview: "Maps 000_strategizer_mvp_plan.md into discrete, numbered implementation steps. Records dependency order and links to detailed plans."
todos: []
isProject: false
---

# 001: Strategizer MVP Implementation Roadmap

This document reorganizes [000_strategizer_mvp_plan.md](000_strategizer_mvp_plan.md) into discrete implementation steps. Each step maps to a detailed plan file. All plans must conform to 000.

---

## Project Practice: Test-First (Red-Green-Refactor)

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests that specify the expected behavior. Run tests; they fail. |
| **Green** | Implement minimal code to make the tests pass. Run tests; they pass. |
| **Refactor** | Clean up implementation while keeping tests green. |

Plans structure work as discrete Red → Green → Refactor cycles where applicable.

---

## Objective (from 000 §0)

Create a shared **strategizer** project so that the same strategies serve both observer and backtester. Scope includes:

1. Strategizer package (shared types, Strategy interface, ORB 5m)
2. Observer portfolio awareness + adapter
3. Backtester futures support + adapter

---

## Scope Summary

**In scope:** Strategizer package, shared types (BarInput, Signal, PortfolioView, ContractSpecView), ORB strategy, observer portfolio (mock) + adapter, backtester futures domain + DataProvider + fill model + adapter, golden test, end-to-end validation.

**Out of scope:** Additional strategies, options in observer, multi-strategy portfolio optimization.

---

## Architecture Rules (000 §11)

| ID | Rule |
|----|------|
| S1 | Strategizer has no dependency on observer or backtester |
| S2 | Strategies are pure: read (bars, specs, portfolio), emit Signal[]; no side effects |
| S3 | Adapters live in consumer projects; strategizer knows nothing about TradeCandidate or Order |
| S4 | PortfolioView and ContractSpecView are protocols; consumers implement them |
| S5 | BarInput is the only bar type strategizer accepts; consumers adapt their native bars |
| S6 | Same strategy code runs in both tools; differences are adapter and output formatting |

---

## Discrete Implementation Steps

| Step | Name | Project | Plan |
|------|------|---------|------|
| **010** | Strategizer skeleton | strategizer | [010_strategizer_skeleton.md](010_strategizer_skeleton.md) |
| **020** | Shared types | strategizer | [020_shared_types.md](020_shared_types.md) |
| **030** | ORB in strategizer | strategizer | [030_orb_in_strategizer.md](030_orb_in_strategizer.md) |
| **040** | Observer portfolio state | observer | [040_observer_portfolio_state.md](040_observer_portfolio_state.md) |
| **050** | Observer strategizer adapter | observer | [050_observer_strategizer_adapter.md](050_observer_strategizer_adapter.md) |
| **060** | Observer ORB from strategizer | observer | [060_observer_orb_from_strategizer.md](060_observer_orb_from_strategizer.md) |
| **070** | Backtester futures domain | backtester | [070_backtester_futures_domain.md](070_backtester_futures_domain.md) |
| **080** | Backtester DataProvider futures | backtester | [080_backtester_dataprovider_futures.md](080_backtester_dataprovider_futures.md) |
| **090** | Backtester fill model futures | backtester | [090_backtester_fill_model_futures.md](090_backtester_fill_model_futures.md) |
| **100** | Backtester strategizer adapter | backtester | [100_backtester_strategizer_adapter.md](100_backtester_strategizer_adapter.md) |
| **110** | Backtester ORB strategy | backtester | [110_backtester_orb_strategy.md](110_backtester_orb_strategy.md) |
| **120** | Golden test | backtester | [120_golden_test.md](120_golden_test.md) |
| **130** | End-to-end validation | cross-project | [130_end_to_end_validation.md](130_end_to_end_validation.md) |

---

## Dependency Order

```
010 (Skeleton) -> 020 (Shared types) -> 030 (ORB in strategizer)
                    |
                    +-> 040 (Observer portfolio) -> 050 (Observer adapter) -> 060 (Observer ORB)
                    |
                    +-> 070 (Backtester futures domain) -> 080 (DataProvider) + 090 (Fill model)
                                    -> 100 (Backtester adapter) -> 110 (Backtester ORB) -> 120 (Golden test)
                                    -> 130 (E2E validation)
```

- 040 and 070 can proceed in parallel after 030
- 050 and 100 depend on 030
- 080 and 090 depend on 070

---

## Decisions (from 000 §13)

| Decision | Choice |
|----------|--------|
| Strategizer distribution | Package (path dependency for MVP) |
| Observer portfolio source | Mock (replace when portfolio-aware) |
| Backtester futures data format | Deferred to step 080 |
| Position sizing | Configurable, default 1 |

---

## MVP Acceptance Criteria (from 000 §9)

- Strategizer: Package installable; ORB produces `list[Signal]`; unit tests pass
- Observer: Engine passes portfolio to strategies; ORB from strategizer; no regression
- Backtester: Futures (ES/NQ) with ContractSpec; DataProvider; tick-aligned fills; ORB produces orders; golden test passes
- Integration: Same ORB logic in both tools; consistent outputs
