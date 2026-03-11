---
name: 080 Backtester DataProvider Futures
overview: "Extend DataProvider to load futures bars and ContractSpec. LocalFileDataProvider supports futures data layout. Resolve open decision on format."
todos: []
isProject: false
---

# 080: Backtester DataProvider Futures

Conforms to [000_strategizer_mvp_plan.md](000_strategizer_mvp_plan.md) §5.2. Resolves deferred decision on futures data format.

---

## Objective

Extend the backtester DataProvider to:
1. Load futures bars (OHLCV) for symbols like ESH26, NQH26
2. Return FuturesContractSpec for a given symbol
3. Build MarketSnapshot for futures runs (underlying_bar = futures bar, option_quotes = None)

---

## Existing Foundation

- DataProvider: get_underlying_bars, get_option_chain, get_option_quotes, get_contract_metadata
- LocalFileDataProvider: parquet for underlying, CSV for options
- Step 070: FuturesContractSpec, engine expects get_futures_contract_spec

---

## Data Format Decision

**Options:**
1. Reuse underlying path: same parquet schema, symbol column distinguishes ES vs SPY
2. Separate path: futures_path in config, e.g. futures/bars/
3. Unified: DataProvider infers from symbol pattern (ESH26 → future) or config

**Recommendation:** Config `futures_path` (or `futures_bars_path`). Same parquet schema as underlying (symbol, ts, open, high, low, close, volume). Metadata file for FuturesContractSpec per symbol (tick_size, point_value, session).

Format:
- `futures_path/` contains parquet: ESH26.parquet, NQH26.parquet (or single file with symbol column)
- `futures_path/metadata/` or `futures_specs.yaml`: symbol -> tick_size, point_value, timezone, session hours

---

## DataProvider Interface Extension

```python
def get_futures_bars(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> Bars: ...
def get_futures_contract_spec(self, symbol: str) -> FuturesContractSpec: ...
```

Or: generalize get_underlying_bars — when instrument_type=future, read from futures path. Same Bars/BarRow structure.

**Simpler:** Single method `get_bars(symbol, timeframe, start, end)` with config specifying data path per instrument type. For MVP, add explicit `get_futures_bars` and `get_futures_contract_spec`.

---

## LocalFileDataProvider

- DataProviderConfig: futures_path, futures_metadata_path (or inline in config)
- get_futures_bars: load parquet from futures_path, filter by symbol, return Bars
- get_futures_contract_spec: load metadata (YAML or JSON), return FuturesContractSpec for symbol

---

## Engine Integration

When BacktestConfig.instrument_type == "future":
- Engine calls get_futures_bars instead of get_underlying_bars
- Engine calls get_futures_contract_spec for multiplier/spec
- MarketSnapshot: underlying_bar = futures bar, option_quotes = None

---

## Implementation Phases

### Phase 0: Config and interface

| Stage | Tasks |
|-------|-------|
| Extend | DataProviderConfig: futures_path |
| Extend | DataProvider ABC: get_futures_bars, get_futures_contract_spec |
| Stub | LocalFileDataProvider: raise NotImplementedError or return mock |

### Phase 1: File layout and loader

| Stage | Tasks |
|-------|-------|
| Define | Parquet schema for futures bars (match Bars/BarRow) |
| Define | Metadata format (YAML per symbol or single file) |
| Implement | load_futures_bars, load_futures_metadata |

### Phase 2: LocalFileDataProvider implementation

| Stage | Tasks |
|-------|-------|
| Implement | get_futures_bars using parquet |
| Implement | get_futures_contract_spec using metadata |
| Test | Integration test with sample data |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Futures path | Separate config key | Clear separation; options/equity unchanged |
| Parquet schema | Same as underlying bars | BarRow: ts, open, high, low, close, volume; add symbol in loader |
| Metadata | YAML or JSON | Human-editable; tick_size, point_value, session for ES/NQ |
| Timeframes | Reuse 1d, 1h, 1m | Add 5m when needed for ORB |

---

## Acceptance Criteria

- [ ] get_futures_bars returns Bars
- [ ] get_futures_contract_spec returns FuturesContractSpec
- [ ] Sample ESH26 5m data loads correctly
- [ ] Engine can build MarketSnapshot for futures run

---

## Out of Scope

- Live futures data source
- Options and futures in same run
- Tick data
