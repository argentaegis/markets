# M1 DataProvider — Test Plan

This document defines the **test plan** to validate implementation of `010_m1_dataprovider_execution_plan.md`. Tests are organized by phase and map to acceptance criteria. Implement tests alongside each phase; the full suite must pass before M1 is complete.

---

## Test Infrastructure

### Setup
- **Framework:** pytest
- **Fixtures location:** `src/data/tests/fixtures/` (tests live inside the data module)
- **Conventions:**
  - Use `conftest.py` for shared fixtures (config, temp data dirs).
  - Fixtures must be deterministic and version-controlled.
  - No production data; synthetic fixtures only for MVP.

### Fixture Categories
| Fixture Set | Purpose |
|-------------|---------|
| `fixtures/underlying/` | Sample OHLCV CSV/parquet for `SPY_1d`, `SPY_1h`, `SPY_1m` with known timestamps |
| `fixtures/options/metadata/` | Metadata index with known contract_ids and multipliers |
| `fixtures/options/quotes/` | Per-contract quote time series (Option B format) with edge cases |

---

## Phase 1: Domain Types

### 1.1 `test_bars.py` — Bars and BarRow

| ID | Test | Expected |
|----|------|----------|
| B1 | Create `BarRow` with ts, o/h/l/c, volume; all required fields present | No NaN; types correct |
| B2 | Create `Bars` with symbol, timeframe, start, end, timezone, rows | Fields populated |
| B3 | **Invariant: monotonic timestamps** — bars out of order raise or are rejected | Error or sorted result |
| B4 | Empty `Bars` (no rows) — valid for empty range | `rows` empty; start/end preserved |
| B5 | Timezone field is set (e.g. `"UTC"`) | `timezone == "UTC"` |
| B6 | BarRow with NaN in required field raises or is rejected | Validation error |

### 1.2 `test_quotes.py` — Quote, QuoteStatus, Quotes

| ID | Test | Expected |
|----|------|----------|
| Q1 | Create `Quote` with bid, ask; optional mid, bid_size, ask_size, etc. | Optional fields can be None |
| Q2 | Create `Quotes` with ts and mapping contract_id → Quote \| QuoteStatus \| None | Mapping contains all requested keys |
| Q3 | **No silent omission** — Quotes includes entry for every requested contract_id | len(mapping) == len(requested_ids) |
| Q4 | Missing contract: mapping has None or QuoteStatus.MISSING; errors/missing list includes reason | Machine-readable reason present |
| Q5 | Stale contract: QuoteStatus.STALE or reason in errors | Staleness flagged |
| Q6 | **Crossed market sanitize** — bid > ask → sanitized so bid <= ask; crossed_market=True | bid <= ask; flag set |
| Q7 | **Crossed market Option B** — mid preserved; bid/ask adjusted around mid; crossed_market=True | mid unchanged; bid <= ask |
| Q8 | Quote with bid == ask — no crossed flag | crossed_market False or absent |

### 1.3 `test_contract.py` — ContractSpec

| ID | Test | Expected |
|----|------|----------|
| C1 | Create `ContractSpec` with contract_id, underlying_symbol, strike, expiry, right, multiplier | Immutable; all fields set |
| C2 | ContractSpec is immutable | Assignment to field raises |

### 1.4 `test_contract_id.py` — parse / format

| ID | Test | Expected |
|----|------|----------|
| CI1 | `format_contract_id("SPY", date(2026,3,20), "C", 450, 100)` → canonical string | e.g. `SPY\|2026-03-20\|C\|450\|100` |
| CI2 | `parse_contract_id(canonical)` → dict/struct with underlying, expiry, right, strike | Fields extracted; multiplier not inferred from format |
| CI3 | Round-trip: `parse_contract_id(format_contract_id(...))` → consistent | No loss of info for parsed fields |
| CI4 | Invalid format (malformed string) raises or returns error | Validation; no silent bad parse |
| CI5 | Parser does **not** guess multiplier from format | multiplier from metadata only; parse extracts only format-defined fields |

---

## Phase 2: DataProvider Interface and Config

### 2.1 `test_provider_abc.py` — DataProvider ABC

| ID | Test | Expected |
|----|------|----------|
| A1 | DataProvider defines `get_underlying_bars`, `get_option_chain`, `get_option_quotes`, `get_contract_metadata` | Abstract methods present |
| A2 | Concrete implementation can be instantiated and called | No TypeError on abstract |

### 2.2 `test_provider_config.py` — DataProviderConfig

| ID | Test | Expected |
|----|------|----------|
| CF1 | Config has data_path / underlying_path, options_path | Paths configurable |
| CF2 | Config has `missing_data_policy`: RAISE \| RETURN_EMPTY \| RETURN_PARTIAL | Default RAISE |
| CF3 | Config has `max_quote_age` (timedelta or seconds) | e.g. 60 for 1m |
| CF4 | Config has `timeframes_supported` | e.g. ["1d", "1h", "1m"] |
| CF5 | Config is serializable for run manifest | Can be saved/loaded |

---

## Phase 3: Storage Conventions

### 3.1 `test_file_loader.py` — File loader (internal)

| ID | Test | Expected |
|----|------|----------|
| FL1 | Load underlying CSV: columns ts, open, high, low, close, volume | Structured data (not DataFrame in public API) |
| FL2 | Load underlying parquet (if supported) | Same structure as CSV |
| FL3 | Load metadata index: (underlying, expiry, strike, right) → contract_id, multiplier | Index structure correct |
| FL4 | Load per-contract quote series (Option B) | Time series with quote_ts, bid, ask (or mid) |
| FL5 | Raw load returns no DataFrame across module boundary | Domain objects only at provider boundary |

---

## Phase 4: LocalFileDataProvider Implementation

### 4.1 `test_get_underlying_bars.py`

| ID | Test | Expected |
|----|------|----------|
| UB1 | Load bars for symbol, timeframe, [start, end]; range **inclusive** | All bars with start <= ts <= end |
| UB2 | **start == end** — exactly one bar if bar exists at that close ts | 1 bar |
| UB3 | **start == end** — no bar at that ts | 0 bars |
| UB4 | Bar ts = **bar close time** (end of interval), UTC | ts is bar close |
| UB5 | **Monotonic** — returned bars ordered by ts ascending | Strictly increasing ts |
| UB6 | Unsupported timeframe raises or returns empty per config | Documented behavior |
| UB7 | **Caching** — second call for same (symbol, timeframe) returns same data without re-read | Verify via mock or side-effect |
| UB8 | **No DataFrame** — return type is Bars (domain object) | isinstance(result, Bars) |
| UB9 | **No NaN** in returned bars for in-range data | Validation |

### 4.2 `test_get_option_chain.py`

| ID | Test | Expected |
|----|------|----------|
| OC1 | Returns contract_ids not expired at ts | expiry > ts.date() (or equivalent) |
| OC2 | Results **sorted** for determinism | Same order on repeated calls |
| OC3 | Unknown symbol returns empty or per missing_data_policy | Documented |
| OC4 | Uses metadata index for filtering | Correct contracts for symbol |

### 4.3 `test_get_option_quotes.py`

| ID | Test | Expected |
|----|------|----------|
| OQ1 | **As-of lookup:** quote_at(ts) = last quote with quote_ts <= ts | Correct quote for ts |
| OQ2 | **max_quote_age:** if quote older than max_quote_age, strict mode raises | Configurable; RAISE when strict |
| OQ3 | **max_quote_age:** non-strict returns STALE or reason in Quotes.errors | Errors list populated |
| OQ4 | **All keys present** — Quotes mapping has entry for every requested contract_id | No silent omission |
| OQ5 | Missing contract: None or QuoteStatus.MISSING + reason in errors | Documented |
| OQ6 | **Crossed market** — sanitized and flagged; no raise | bid <= ask; crossed_market or errors entry |
| OQ7 | **Caching** — per-contract cache on first use | Second request for same contract_id uses cache |
| OQ8 | **No DataFrame** — return type is Quotes | isinstance(result, Quotes) |

### 4.4 `test_get_contract_metadata.py`

| ID | Test | Expected |
|----|------|----------|
| CM1 | **Index first** — contract_id in metadata index → return full record including multiplier | Multiplier from index |
| CM2 | **Not in index:** parse contract_id for partial spec; apply missing_data_policy | RAISE: exception; RETURN_PARTIAL: metadata_missing=True; RETURN_EMPTY: None |
| CM3 | **Do not guess multiplier** — when not in index, multiplier is default/None, not inferred from format | No silent multiplier from contract_id string |
| CM4 | RAISE policy: MissingContractMetadata(contract_id) raised | Specific exception type |

### 4.5 `test_provider_determinism.py`

| ID | Test | Expected |
|----|------|----------|
| D1 | Same config + same requests → **identical results** | Byte-identical or logically equal |
| D2 | Sorted iteration where order matters (e.g. option_chain) | Deterministic order |

---

## Phase 5: MarketSnapshot Integration

### 5.1 `test_marketsnapshot_build.py` (contract/documentation)

| ID | Test | Expected |
|----|------|----------|
| MS1 | MarketSnapshot can be built from Bars (one bar) + Quotes + ts | No DataFrame in build |
| MS2 | DataProvider output types (Bars, Quotes, ContractSpec) sufficient for MarketSnapshot | Interface contract satisfied |

---

## Phase 6: Error Handling and Invariants

### 6.1 `test_missing_data_policy.py`

| ID | Test | Expected |
|----|------|----------|
| MD1 | RAISE: missing underlying bars in range → exception | Fail fast |
| MD2 | RAISE: missing quote for requested contract → exception (when policy applies) | Or STALE in Quotes.errors per spec |
| MD3 | RETURN_EMPTY: missing data → empty Bars / None for metadata | No exception |
| MD4 | RETURN_PARTIAL: partial data returned with flags | metadata_missing, STALE, etc. |
| MD5 | Policy applied **uniformly** across get_underlying_bars, get_option_quotes, get_contract_metadata | Consistent behavior |

### 6.2 `test_invariants.py`

| ID | Test | Expected |
|----|------|----------|
| I1 | No NaN in Bars for in-range bars | Validation |
| I2 | Raw NaN in source → drop or fail (no silent NaN propagation) | Documented |
| I3 | Log data range (min/max ts) for run manifest | Observable |
| I4 | Log missingness when RETURN_PARTIAL or quotes STALE | Observable |

---

## Phase 7: Golden Run and Integration

### 7.1 `test_golden_run.py`

| ID | Test | Expected |
|----|------|----------|
| G1 | Golden fixture run produces deterministic output | Same config + fixtures → same results |
| G2 | Golden output can be captured and diffed | Regression detection |

### 7.2 `test_run_manifest.py`

| ID | Test | Expected |
|----|------|----------|
| RM1 | DataProvider config saved in run manifest when used | Reproducibility |
| RM2 | Config includes data_path, timeframes, missing_data_policy, max_quote_age | Key params captured |

---

## Acceptance Criteria Mapping

| Acceptance Criterion (§10) | Test IDs |
|----------------------------|----------|
| DataProvider ABC with Bars, Quotes, ContractSpec (no DataFrames) | A1, A2, UB8, OQ8, FL5 |
| Concrete impl supports 1d/1h/1m + option chain/quotes/metadata | UB1–UB9, OC1–OC4, OQ1–OQ8, CM1–CM4 |
| Config in run manifest | CF5, RM1, RM2 |
| MarketSnapshot from DataProvider without DataFrames | MS1, MS2 |
| Unit tests + determinism | All Phase 1–4, D1, D2 |
| Missing data fails fast or configurable | MD1–MD5, CF2 |
| File/storage convention documented | FL1–FL5 (validates Option B + index) |
| Timestamp semantics (UTC, bar close, inclusive, as-of, max_quote_age) | UB1–UB5, OQ1–OQ3 |
| contract_id format + metadata authoritative for multiplier | CI1–CI5, CM1–CM4 |
| Crossed markets sanitized and flagged | Q6, Q7, OQ6 |
| MVP caching without API change | UB7, OQ7 |

---

## Test Execution Order

1. **Phase 1 first** — domain tests have no external deps; run before any provider.
2. **Phase 2** — ABC and config; can use mocks.
3. **Phases 3–4** — require fixtures; build fixtures per §3 of execution plan.
4. **Phases 5–6** — integration; run after provider impl.
5. **Phase 7** — golden run last; validates full stack.

---

## Fixture Requirements Summary

Paths relative to `src/data/tests/`:

### Underlying bars fixture
```
fixtures/underlying/
  SPY_1d.csv   # ts (UTC bar close), open, high, low, close, volume
  SPY_1h.csv
  SPY_1m.csv
```
- Include edge cases: exactly one bar at a timestamp; gaps; contiguous range.
- Document min/max ts in fixture README.

### Options metadata fixture
```
fixtures/options/metadata/
  index.csv    # underlying, expiry, strike, right, contract_id, multiplier
```
- Multiple contracts; different multipliers (e.g. 100, 10) to validate no guessing.
- At least one contract expiring before fixture ts, one after.

### Options quotes fixture (Option B)
```
fixtures/options/quotes/
  {contract_id}.csv   # quote_ts, bid, ask (or mid)
```
- Include crossed market (bid > ask) for sanitize test.
- Include gap in quotes for as-of and max_quote_age tests.
- Stale quote: last quote much older than request ts.

---

## Out of Scope for M1 Tests

- Tick data, level2
- Remote/live API
- Corporate actions
- Advanced caching beyond MVP (LRU per-contract)
