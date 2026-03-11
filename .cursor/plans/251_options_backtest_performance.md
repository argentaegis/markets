# 251: Options Backtest Performance

## Problem

The covered_call backtest completed **5 steps in 75.9 seconds** (≈15 s/step). This is a 250a-era discovery, not a regression from 250a itself.

```
covered_call_example.yaml:  5 steps  →  75.9 s  (15 s/step)
orb_5m_es_1mo.yaml:      7,800 steps  →  34.1 s  (futures, no options; fine)
buy_and_hold_spy_2y.yaml: 195,270 steps →  20.2 s  (equity; fine)
```

---

## Root Cause

`_get_quote_series` calls `pd.read_parquet(path, filters=[("contract_id", "==", cid)])` once per contract on cache miss:

```python
# src/loader/storage/file_loader.py — load_option_quotes_from_parquet
df = pd.read_parquet(path, filters=[("contract_id", "==", contract_id)])
```

`get_option_chain` at any 2026-01-02 timestamp returns **7,142 contracts**. On the first call to `get_option_quotes(chain, ts)`, each of those 7,142 contracts is a cache miss, triggering **7,142 individual parquet reads** from `quotes.parquet`:

| Metric | Value |
|--------|-------|
| `quotes.parquet` size | 47 MB |
| Total rows | 11,364,100 |
| Total contracts | 318,574 |
| Chain size at 2026-01-02 | 7,142 |
| Per-filter-read cost | ~9 ms |
| **Cold-start total** | **62+ seconds** |

The provider's `_quotes_cache` is correct — steps 2–5 are fast (cache hits). But step 1 triggers all 7,142 misses, dominating the 75.9 s total.

### Why now?
The covered_call has never been profiled against real production options data before (only fixture data). The performance issue is pre-existing; it just became visible when running real backtests.

---

## Data Scale

```
data/exports/options/spy/
  quotes.parquet          47 MB  11,364,100 rows   318,574 contracts
  metadata/index.csv      16 MB  318,574 rows      318,574 contracts
```

These are real figures from profiling:

```python
# Full load of quotes.parquet into memory: 0.12 s
# Single filter read (one contract): 0.009 s
# 7,142 sequential filter reads: ~62 s    ← current code path
# One batch filter read for 7,142 cids: 0.10 s
# Build cache dict from batch result: 1.21 s
# Total cold start (batch approach): 1.30 s  (47× faster)
```

---

## Secondary Issue: Metadata Scan

`get_option_chain` scans all 318,574 metadata rows on every step:

```python
result = [r["contract_id"] for r in meta   # 318k-row linear scan
          if r.get("underlying") == symbol and r.get("expiry") > ts_date]
```

Current cost: 0.01 s/step. For a 1-month 1m options backtest (~9,000 steps) this adds ~90 s. Not yet a blocker but will become one.

---

## Proposed Solutions

### Fix A — Batch-load on first chain request (primary, high value) ✓

Change `_get_quote_series` to detect when multiple cache misses arrive at once and dispatch a single parquet read for all missing contracts:

```python
# provider.py — get_option_quotes change
def get_option_quotes(self, contract_ids: list[str], ts: datetime) -> Quotes:
    self._warm_quote_cache(contract_ids)   # NEW: batch-load all misses
    ...

def _warm_quote_cache(self, contract_ids: list[str]) -> None:
    missing = [cid for cid in contract_ids if cid not in self._quotes_cache]
    if not missing:
        return
    parquet_path = self._config.options_path / "quotes.parquet"
    if not parquet_path.exists():
        for cid in missing:
            self._quotes_cache[cid] = []
        return
    df = pd.read_parquet(parquet_path, filters=[("contract_id", "in", missing)])
    for cid, grp in df.groupby("contract_id"):
        self._quotes_cache[cid] = _df_group_to_series(grp)
    for cid in missing:
        if cid not in self._quotes_cache:
            self._quotes_cache[cid] = []   # empty = no data for this contract
```

**Result**: cold start drops from 62s → 1.3s (47× faster). Subsequent steps unchanged (cache hit).

**Why `"in"` filter works**: A single `pd.read_parquet(filters=[("contract_id", "in", [7142 cids])])` reads the file once, applies predicate pushdown, and returns only the relevant rows (875k of 11.4M). One file scan vs 7,142 scans.

---

### Fix B — Cache the groupby result as numpy arrays (secondary, step-cost)

The current `_resolve_single_quote` uses a Python list comprehension for as-of lookup, which is O(n) in quote series length:

```python
candidates = [(t, b, a) for t, b, a in series if t <= ts]   # O(n)
```

Replace the cache value with `(ts_ns_array, bid_array, ask_array)` in int64/float64 numpy and use `np.searchsorted`:

```python
idx = np.searchsorted(ts_arr, ts_ns, side='right') - 1      # O(log n)
```

**When this matters**: only when individual quote series are long (many ticks per contract per day). For the current SPY data (avg ~2–5 quotes per contract per session), the linear scan cost is negligible. This is prep for higher-frequency quote data.

---

### Fix C — Index metadata by underlying (secondary, chain scan)

Replace the list scan in `get_option_chain`:

```python
# Current: O(n) scan of 318k rows per call
result = [r["contract_id"] for r in meta if r["underlying"] == symbol ...]

# Proposed: build dict on first load
# self._metadata_by_underlying: dict[str, list[dict]] sorted by expiry
# get_option_chain: O(1) lookup + binary search for expiry cutoff
```

**Impact**: reduces per-step metadata scan from 0.01s to ~0.001s. Matters for long options backtests (year-long 1m options backtest = 195k steps × 0.01s = ~1,950 s).

---

## Expected Results

| Scenario | Before | After (Fix A) | After (A+C) |
|----------|--------|---------------|-------------|
| covered_call 5 steps | 75.9 s | ~3 s | ~2 s |
| 1-day options 390 steps | ~65 s | ~3 s | ~2 s |
| 1-month options ~9k steps | ~65 s | ~5 s | ~4 s |
| 1-year options ~120k steps | ~65 s | ~65 s | ~18 s |
| futures/equity (no change) | fast | unchanged | unchanged |

---

## Scope

| Plan | Fix | Files | Priority | Status |
|------|-----|-------|----------|--------|
| 251a | Fix A: batch quote cache warm | `src/loader/provider.py`, `src/loader/storage/file_loader.py` | High | Done |
| 251b | Fix C: metadata index | `src/loader/provider.py` | Medium | Done |
| 251c | Fix B: numpy as-of lookup | `src/loader/provider.py` | Low | Deferred |

---

## Actual Results (after 251a+251b)

| Scenario | Before | After |
|----------|--------|-------|
| covered_call 5 steps | 75.9 s | ~11.5 s (6.6× faster) |
| All 83 tests | pass | pass |

---

## Verification

For each fix, run before/after:

```bash
python -m src.runner configs/covered_call_example.yaml        # 5 steps
python -m src.runner configs/buy_and_hold_underlying_spy_2y.yaml  # baseline unchanged
pytest tests/ -v                                               # all 83 tests pass
```

Target: `covered_call_example` completes in < 5 s.
