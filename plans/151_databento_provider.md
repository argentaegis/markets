# Plan 151: Databento Data Provider

## Scope

Convert manually-downloaded Databento OHLCV files to the backtester canonical format. **No API calls** — user downloads data from the Databento portal. We provide a converter and import command to ingest files into the backtest data layout.

**Behavior:** When Databento data is requested but not available, **warn** (do not fetch) and instruct the user to ingest a file with `md import-databento`.

Phase 1: ohlcv-1m CSV for SPY (XNAS.ITCH) and ES futures (GLBX.MDP3). No options.

---

## Databento CSV Format (observed)

**Same structure for XNAS and GLBX.** Both use:

```
ts_event,rtype,publisher_id,instrument_id,open,high,low,close,volume,symbol
```

**XNAS (equities)** — `xnas-itch-20210228-20260227.ohlcv-1m.csv`:
- Single symbol (SPY) or few symbols per file
- `--symbol` optional if only one symbol

**GLBX (futures)** — `glbx-mdp3-20210301-20260301.ohlcv-1m.csv`:
- Multiple symbols per timestamp: ESH1, ESM1, ESH1-ESM1 (spreads), etc.
- `--symbol ESH1` — extract single contract (~19 days)
- `--symbol ES --continuous` — build front-month continuous series (roll on 3rd Friday)
- Spreading symbols (ESH1-ESM1) filtered out; single contracts only

- `ts_event` — ISO timestamp with Z (UTC)
- `open`, `high`, `low`, `close`, `volume` — already match canonical names
- `symbol` — filter to desired contract/symbol
- Drop: `rtype`, `publisher_id`, `instrument_id`

---

## Verification

**XNAS (SPY):**
```bash
python -m src.marketdata.cli import-databento \
  --file data/cache/databento/xnas-itch-20210228-20260227.ohlcv-1m.csv \
  --symbol SPY \
  --interval 1m \
  --out data/exports/spy
```
Expected: `data/exports/spy/SPY_1m.parquet`

**GLBX (ES single contract):**
```bash
python -m src.marketdata.cli import-databento \
  --file data/cache/databento/glbx-mdp3-20210301-20260301.ohlcv-1m.csv \
  --symbol ESH1 \
  --interval 1m \
  --out data/exports/esh1
```
Expected: `data/exports/esh1/ESH1_1m.parquet` (~19k bars)

**GLBX (ES continuous):**
```bash
python -m src.marketdata.cli import-databento \
  --file data/cache/databento/glbx-mdp3-20210301-20260301.ohlcv-1m.csv \
  --symbol ES \
  --interval 1m \
  --continuous \
  --out data/exports/es
```
Expected: `data/exports/es/ES_1m.parquet` (~1.77M bars, 2021-03 to 2026-02)
