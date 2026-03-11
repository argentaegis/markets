# M1 DataProvider — Detailed Execution Plan

This document is the **execution plan** for implementing the M1 DataProvider module. It conforms to `000_options_backtester_mvp.md` and must keep the external interface stable regardless of internal storage (csv/parquet/duckdb).

**Refined per review:** Options storage convention, timestamp semantics, missing-data policy, contract_id format, and MVP caching are now fixed before coding to avoid churn and silent correctness bugs.

---

## 1) Objectives (from MVP)

- **Load underlying bars** for timeframes `1d`, `1h`, `1m`.
- **Provide option quotes** at each timestamp for contracts needed by the strategy (bid/ask or mid).
- **Provide contract metadata**: strike, expiry, right, multiplier.
- **Interface-only contract**: internal storage is an implementation detail; callers receive domain-friendly types, not raw DataFrames (A2).

---

## 2) Interface Contract (stable API)

### 2.1 Abstract interface

The DataProvider is an **abstract interface** with the following required methods:

| Method | Signature | Returns | Purpose |
|--------|-----------|---------|--------|
| Underlying bars | `get_underlying_bars(symbol: str, timeframe: str, start: datetime, end: datetime) -> Bars` | `Bars` | OHLCV bars for the underlying in the given timeframe and range. |
| Option chain or quotes | Either `get_option_chain(symbol: str, ts: datetime) -> list[str]` **or** `get_option_quotes(contract_ids: list[str], ts: datetime) -> Quotes` | `list[contract_id]` or `Quotes` | List contract IDs available at `ts`, and/or fetch bid/ask (or mid) for given contracts at `ts`. |
| Contract metadata | `get_contract_metadata(contract_id: str) -> ContractSpec` | `ContractSpec` | Strike, expiry, right, multiplier for a contract. |

**Design choice:** Support both patterns:
- `get_option_chain(symbol, ts)` for “what options exist at this time?”
- `get_option_quotes(contract_ids, ts)` for “what are the quotes for these contracts at this time?”

Implementations may derive one from the other internally (e.g. chain from metadata index, quotes from time-series store).

### 2.2 Return types (domain objects, not DataFrames)

Define these in the domain layer; DataProvider **returns** them, never raw pandas across the boundary.

- **`Bars`**
  - Represents a time-ordered series of OHLCV bars.
  - Fields: `symbol`, `timeframe`, `start`, `end`, `timezone` (e.g. `"UTC"`), and a sequence of bar rows.
  - **Invariant:** timestamps are **monotonic increasing**.
  - Each row: `ts`, `open`, `high`, `low`, `close`, `volume` (all typed; no NaN for required fields in range).
  - Implementation: dataclass holding a list of bar rows; **not** a raw `pd.DataFrame` in the public API.

- **`Quotes`**
  - Per-contract quote at a single timestamp. **Never silently omit requested contracts.**
  - Fields: `ts`, a mapping `contract_id -> Quote | QuoteStatus | None` (one entry per requested `contract_id`), and an `errors` or `missing` list (e.g. reason per contract when missing/stale).
  - `Quote`: at least `bid`, `ask`, optional `mid`; optional (can be `None`) `bid_size`, `ask_size`, `last`, `open_interest`, `iv`, `greeks`.
  - If only mid is stored: return mid, document bid/ask absent (FillModel uses synthetic spread).
  - **Crossed markets are sanitized and flagged by default** (do not raise). See §3a below.

- **`ContractSpec`**
  - Immutable metadata for one option contract.
  - Fields: `contract_id` (canonical string, see §2.3), `underlying_symbol`, `strike`, `expiry` (date), `right` (call/put), `multiplier`.

All IDs (symbols, contract_id) must be **stable strings** (MVP §3).

### 2.3 Contract ID format (canonical)

- **Decision:** Use a single canonical format to prevent refactors. Either OCC-style (if US equity options) or a defined format, e.g. `{underlying}|{expiry}|{right}|{strike}|{multiplier}` → `SPY|2026-03-20|C|450|100`.
- **Module:** `domain/contract_id.py` with:
  - Parser: `parse_contract_id(contract_id: str) -> dict` or structured type (for format validation and extracting expiry, strike, right).
  - Formatter: `format_contract_id(underlying, expiry, right, strike, multiplier) -> str`.
- **Metadata index is the authoritative source for multiplier** (and underlying_symbol and other static fields). Contract_id parsing validates and extracts fields but **does not guess multiplier**; multipliers can differ (index options, minis, adjusted contracts). Guessing multiplier silently breaks P&L.

---

## 3) Timestamp and lookup semantics (fixed)

- **Timezone:** All timestamps at the DataProvider boundary are **UTC**. Store and pass datetimes as timezone-aware UTC.
- **Underlying bars:**
  - Bar `ts` = **bar close time** (end of the bar interval), UTC.
  - **Bar range filtering is inclusive:** `start <= ts <= end`. Return only bars whose timestamp satisfies that condition. Results must be monotonically increasing by `ts`.
  - **Constraint:** Callers should align `end` to a bar-close timestamp for the timeframe to avoid off-by-one surprises.
  - **Test expectations:** If `start == end`, return 1 bar if a bar exists at exactly that close timestamp, otherwise 0 bars.
- **Option quotes (as-of lookup):**
  - `quote_at(ts) = last quote with quote_ts <= ts`.
  - **Staleness:** Config `max_quote_age` (e.g. 60s for 1m bars, 10m for 1h). If age of the found quote exceeds this: in **strict** mode raise; otherwise return missing with a flag/reason in `Quotes.errors`/missing list.
- Document these rules in code and in the run manifest so backtest results are interpretable.

### 3a) Crossed markets: sanitize and flag

- **Decision:** Sanitize and flag (do not raise by default). Continue execution unless `missing_data_policy` or a separate strictness flag requires otherwise.
- If a quote is crossed (`bid > ask`):
  1. Sanitize so that `bid <= ask`.
  2. Record a flag/error entry in the returned `Quotes` result (machine-readable, e.g. `crossed_market=True` on the quote or an entry in `Quotes.errors`).
- **Recommended sanitize rule (pick one and document):**
  - **Option A (simple):** swap `bid` and `ask`; set `crossed_market=True`.
  - **Option B (stable mid, preferred if mids are used):** `mid = (bid + ask) / 2`; set `bid = min(bid, mid)`, `ask = max(ask, mid)`; set `crossed_market=True`.
- **Reporter/diagnostics:** Track and report counts of crossed quotes sanitized per run (e.g. in summary or run manifest).

---

## 4) Configuration Surface

- **DataProvider config** (subset of `BacktestConfig` or passed where needed):
  - `data_path` or `underlying_path` and `options_path` (or single root with convention).
  - `timeframes_supported`: e.g. `["1d", "1h", "1m"]`.
  - Optional: `storage_backend`: `"csv"` | `"parquet"` | `"duckdb"` (default for MVP: file-based).
  - **`missing_data_policy`:** `"RAISE"` | `"RETURN_EMPTY"` | `"RETURN_PARTIAL"` — uniform behavior across methods; default `RAISE` (fail fast).
  - **`max_quote_age`:** timedelta or seconds; if as-of quote is older than this, treat as missing (strict: raise; otherwise return with reason in `Quotes`). Example: 60s for 1m, 600s for 1h.
- Config must be **saved in run manifest** for reproducibility (A4).

---

## 5) File and Module Layout

```
backtester/
  src/
    domain/
      bars.py         # Bars, BarRow (timezone, monotonic ts)
      quotes.py       # Quotes, Quote, QuoteStatus
      contract.py     # ContractSpec
      contract_id.py  # parse_contract_id, format_contract_id (canonical format)
    data/
      provider.py     # DataProvider ABC + LocalFileDataProvider
      storage/
        file_loader.py
      tests/          # DataProvider module tests (self-contained)
        conftest.py
        fixtures/
        test_*.py
  data/
    underlying/       # {symbol}_{timeframe}.csv or .parquet
    options/
      metadata/       # metadata index: (underlying, expiry, strike, right) -> contract_id + multiplier
      quotes/         # one time series per contract_id (or partitioned parquet)
```

- **Domain objects** in `domain/`; **DataProvider** in `data/provider.py` (ABC + concrete). Options storage: **Option B** (per-contract time series) + **metadata index** (§6).

---

## 6) Options storage convention (decided)

- **Choice: Option B** — one time series per `contract_id` (or parquet partitioned by underlying/expiry/strike/right).
  - Best for `get_option_quotes(contract_ids, ts)` with as-of semantics.
- **Metadata index** (single table/file): maps `(underlying, expiry, strike, right)` → `contract_id`, plus **multiplier** and other static fields. The metadata index is the **authoritative source for multiplier** (and underlying_symbol); contract_id parsing does not invent multiplier unless explicitly configured.
  - Enables `get_option_chain(symbol, ts)` by filtering metadata for contracts not expired at `ts`.
- Rationale: quote lookup is the hot path; per-contract series keeps lookup simple and avoids awkward chain-by-date quote resolution.

### 6a) get_contract_metadata behavior (metadata source of truth)

- **Metadata index is authoritative** for multiplier, underlying_symbol, and any future static fields. Contract_id parsing is used for format validation and extracting expiry/strike/right only; do not guess multiplier.
- `get_contract_metadata(contract_id)` behavior:
  1. Look up `contract_id` in the metadata index.
  2. If found: return the metadata record (including multiplier).
  3. If not found: parse `contract_id` into `(underlying, expiry, right, strike)` for a partial spec, then apply **missing_data_policy**:
     - **RAISE:** raise `MissingContractMetadata(contract_id)`.
     - **RETURN_PARTIAL:** return parsed spec with `metadata_missing=True` (multiplier may be a configured default or None; document).
     - **RETURN_EMPTY:** return `None`.

---

## 7) Missing-data policy (uniform)

- **Single config:** `missing_data_policy = "RAISE" | "RETURN_EMPTY" | "RETURN_PARTIAL"`.
- **Quotes:** Always return a `Quotes` object with an entry for **every** requested `contract_id`. Missing or stale contracts get `None` or a `QuoteStatus` (e.g. `MISSING`, `STALE`), and a machine-readable reason in `Quotes.errors` / `missing` list.
- **No silent omission:** Do not drop missing contracts from the mapping; callers can detect and log. Default to fail-fast (`RAISE`) so backtests do not look unrealistically good.

---

## 8) MVP caching (no API change)

- **Underlying bars:** Load once per `(symbol, timeframe)` per run; keep in memory.
- **Option quotes:** Load per contract on first use; cache in memory (e.g. LRU cap). Implementation detail inside `LocalFileDataProvider`; public API unchanged.
- Prevents re-reading files every bar and keeps MVP performant without exposing cache in the interface.

---

## 9) Implementation Phases

### Phase 1: Domain types used by DataProvider

- [ ] **1.1** Add `domain/bars.py`: `BarRow` (ts, open, high, low, close, volume), `Bars` (symbol, timeframe, start, end, timezone, rows). Guarantee monotonic increasing timestamps.
- [ ] **1.2** Add `domain/quotes.py`: `Quote` (bid, ask, optional mid; optional None: bid_size, ask_size, last, open_interest, iv, greeks; optional `crossed_market` flag). Crossed-market: **sanitize and flag** per §3a (do not raise by default). `QuoteStatus` (e.g. MISSING, STALE). `Quotes`: ts, mapping for every requested contract_id → Quote | QuoteStatus | None, plus errors/missing list.
- [ ] **1.3** Add `domain/contract.py`: `ContractSpec` (contract_id, underlying_symbol, strike, expiry, right, multiplier).
- [ ] **1.4** Add `domain/contract_id.py`: canonical format (e.g. `SPY|2026-03-20|C|450|100` or OCC); `parse_contract_id`, `format_contract_id`.
- [ ] **1.5** Type hints throughout; serializable or easily logged (e.g. dataclasses).

### Phase 2: DataProvider interface and config

- [ ] **2.1** Add `DataProvider` ABC in `data/provider.py` with:
  - `get_underlying_bars(symbol, timeframe, start, end) -> Bars`
  - `get_option_chain(symbol, ts) -> list[str]`
  - `get_option_quotes(contract_ids, ts) -> Quotes`
  - `get_contract_metadata(contract_id) -> ContractSpec`
- [ ] **2.2** Define `DataProviderConfig`: paths, timeframes_supported, storage_backend, **missing_data_policy** (RAISE | RETURN_EMPTY | RETURN_PARTIAL), **max_quote_age** (timedelta or seconds).
- [ ] **2.3** Document valid timeframes (`1d`, `1h`, `1m`) and range semantics (inclusive [start, end], bar ts = bar close).

### Phase 3: Internal storage and file conventions (Option B + index)

- [ ] **3.1** Underlying bars: one file per (symbol, timeframe), e.g. `{symbol}_{timeframe}.csv` or `.parquet`, columns [ts, open, high, low, close, volume]; ts = bar close, UTC.
- [ ] **3.2** Options: **Option B** — one time series per contract_id under `options/quotes/` (or partitioned parquet). Metadata index under `options/metadata/`: (underlying, expiry, strike, right) → contract_id + multiplier; used for `get_option_chain` and `get_contract_metadata`.
- [ ] **3.3** File loader in `data/storage/file_loader.py`: read csv/parquet, return structured data; conversion to `Bars`/`Quotes`/`ContractSpec` inside provider; no pandas in public API.

### Phase 4: Concrete DataProvider implementation

- [ ] **4.1** Implement `LocalFileDataProvider`: constructor accepts `DataProviderConfig`. **Caching:** load underlying bars once per (symbol, timeframe) per run; load option quotes per contract on first use, cache (e.g. LRU). No API change.
- [ ] **4.2** `get_underlying_bars`: load (from cache), filter inclusive `start <= ts <= end`, build `Bars` with timezone and monotonic ts; apply missing_data_policy. If start == end, return 1 bar if bar exists at that close ts else 0.
- [ ] **4.3** `get_option_chain(symbol, ts)`: from metadata index, return contract_ids not expired at `ts`; sorted for determinism.
- [ ] **4.4** `get_option_quotes(contract_ids, ts)`: as-of lookup (last quote with quote_ts <= ts); enforce max_quote_age (strict raise or mark STALE in Quotes.errors). Return `Quotes` with entry for every contract_id (Quote, QuoteStatus, or None + errors list). Apply missing_data_policy.
- [ ] **4.5** `get_contract_metadata(contract_id)`: lookup in metadata index first; if found return record (incl. multiplier). If not found, parse via `domain/contract_id.py` for partial spec then apply missing_data_policy (RAISE / RETURN_PARTIAL with metadata_missing=True / RETURN_EMPTY → None). Do not guess multiplier from contract_id.
- [ ] **4.6** Determinism: same config + same requests → identical results; sorted iteration where order matters.

### Phase 5: Integration with MarketSnapshot builder

- [ ] **5.1** Document engine usage: at clock `ts`, get underlying bar with bar close <= ts (or last known); get option chain(s); get option quotes for requested contract_ids with as-of ts and max_quote_age.

- [ ] **5.2** Define MarketSnapshot (domain) and population from Bars (one bar → underlying_bar), Quotes → option_quotes, ts, metadata.
- [ ] **5.3** DataProvider API suffices for MarketSnapshot without DataFrames across boundary.

### Phase 6: Error handling and invariants

- [ ] **6.1** Apply **missing_data_policy** uniformly; no silent omission of requested contract_ids in Quotes.
- [ ] **6.2** No NaNs in returned Bars for in-range bars; drop or fail on raw NaN.
- [ ] **6.3** Log data range loaded (min/max ts) for run manifest. Log missingness when RETURN_PARTIAL or when quotes are STALE.

### Phase 7: Testing

- [ ] **7.1** Unit tests for domain types: Bars (timezone, monotonic), Quote/Quotes (missing representation, crossed market), ContractSpec, contract_id parse/format.
- [ ] **7.2** DataProvider tests with fixtures: get_underlying_bars (inclusive range, start==end → 1 or 0 bars, monotonic), get_option_chain (sorted, not expired), get_option_quotes (as-of, max_quote_age, all keys present, errors list, crossed-market sanitize+flag), get_contract_metadata (index first; not-found + missing_data_policy).
- [ ] **7.3** Determinism test: same config + requests → identical results.
- [ ] **7.4** Golden run from fixtures (deterministic).

---

## 10) Acceptance Criteria (Definition of Done for M1)

- [ ] `DataProvider` ABC is defined with the three method groups above; return types are `Bars`, `Quotes`, `ContractSpec` (no raw DataFrames in public API).
- [ ] At least one concrete implementation (e.g. local file) supports `1d`, `1h`, `1m` underlying bars and option chain + quotes + metadata.
- [ ] Config for data paths and timeframes is explicit and included in run manifest when used.
- [ ] MarketSnapshot can be built from DataProvider output without crossing A2 (no DataFrames across module boundary).
- [ ] Unit tests cover domain types and DataProvider with fixture data; determinism test passes.
- [ ] Missing critical data fails fast or is configurable and documented.
- [ ] Documented file/storage convention (Option B + metadata index) so that future backends can be swapped behind the same interface.
- [ ] Timestamp semantics (UTC, bar close, inclusive `start <= ts <= end`, as-of, max_quote_age) and missing-data policy documented and implemented.
- [ ] Canonical contract_id format and parser/formatter in place; metadata index authoritative for multiplier; get_contract_metadata behavior (index first, then parse + missing_data_policy) implemented.
- [ ] Crossed markets sanitized and flagged by default; reporter tracks counts of crossed quotes sanitized per run.
- [ ] MVP caching (underlying once, options per-contract LRU) without API change.

---

## 11) Top risks and mitigations

| Risk | Mitigation |
|------|------------|
| Ambiguous time alignment → wrong fills | Lock UTC, bar close timestamps, as-of quote lookup, and max_quote_age in config and code. |
| Storage choice forces rewrite | Option B + metadata index chosen and implemented from the start. |
| Silent missing quotes → optimistic backtests | Explicit missing_data_policy; Quotes always include all requested contract_ids with None/QuoteStatus + errors; default RAISE; log missingness. |

---

## 12) Out of Scope for M1

- Tick data or level2.
- Live or remote API data sources (only local file-based in MVP).
- Corporate actions handling (do not break; no special handling in M1).
- Advanced caching (beyond MVP in-memory per-symbol and per-contract); API stays unchanged if added later.

---

## 13) Dependency Order

1. Domain objects (`Bars`, `Quote`/`Quotes`, `ContractSpec`, `contract_id` parse/format) — no dependency on data layer.
2. `DataProvider` ABC and `DataProviderConfig`.
3. File conventions and loader (internal to data module).
4. Concrete `LocalFileDataProvider` (or equivalent).
5. MarketSnapshot builder contract (documentation + domain type only; implementation in engine step).
6. Tests and golden fixture.

---

## 14) Summary Checklist for Implementation

| # | Task | Phase |
|---|------|--------|
| 1 | Domain: BarRow, Bars (timezone, monotonic) | 1 |
| 2 | Domain: Quote, QuoteStatus, Quotes (all keys, errors list); optional fields; crossed market sanitize+flag (§3a) | 1 |
| 3 | Domain: ContractSpec | 1 |
| 4 | Domain: contract_id format, parse_contract_id, format_contract_id | 1 |
| 5 | DataProvider ABC + DataProviderConfig (missing_data_policy, max_quote_age) | 2 |
| 6 | File conventions: underlying bars + Option B quotes + metadata index | 3 |
| 7 | File loader (no DataFrame in API) | 3 |
| 8 | LocalFileDataProvider: get_underlying_bars + caching | 4 |
| 9 | get_option_chain, get_option_quotes (as-of, max_quote_age, full mapping, crossed sanitize+flag), get_contract_metadata (index first, then parse+policy); option cache | 4 |
| 10 | MarketSnapshot build contract (doc) | 5 |
| 11 | Missing-data policy and logging | 6 |
| 12 | Unit tests, determinism test, golden fixtures | 7 |

---

## 15) Pre-coding checklist (from review)

Before implementation, confirm:

- [ ] Option B storage (contract time series) + metadata index chosen and reflected in plan.
- [ ] UTC and bar-close timestamp conventions defined (§3).
- [ ] As-of quote lookup and max_quote_age defined and in config (§3, §4).
- [ ] Canonical contract_id format and parser/formatter specified; metadata index authoritative for multiplier (§2.3, §6a).
- [ ] Missing-data policy and quote-missing representation standardized (§7, Phase 6).
- [ ] Crossed markets: sanitize and flag by default (§3a); reporter tracks sanitized count.
- [ ] Minimal in-memory caching (underlying once, options per-contract) added to plan (§8, Phase 4.1).

This plan is the single source of truth for implementing M1 DataProvider in line with `000_options_backtester_mvp.md`.
