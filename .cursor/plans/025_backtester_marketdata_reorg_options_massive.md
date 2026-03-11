# Step 025: Marketdata Reorg, Options from Massive, Polygon→Massive Rename

## Overview

Reorganize marketdata into underlying/ and options/ folders with common at root. Add Polygon/Massive options fetch using the same provider/converter architecture. Rename polygon → massive throughout. Normalize on Parquet as default.

---

## Folder Reorganization (Do First)

Split marketdata so each domain lives in its own folder; common stays at root.

### Target layout

```
src/marketdata/
  config.py              # common - CACHE_ROOT, paths
  cli.py                 # common - orchestrates fetch, export, fetch-options
  symbols.py             # common - user → provider symbol resolution
  symbols.yaml           # common

  underlying/
    providers/
      base.py            # MarketDataProvider
      massive.py         # MassiveProvider
    converters/
      base.py            # FormatConverter
      massive.py         # MassiveConverter
    storage.py
    export.py
    validate.py

  options/
    ticker.py
    providers/
      base.py            # OptionsChainProvider, OptionsQuotesProvider
      massive.py         # MassiveOptionsChainProvider, MassiveOptionsQuotesProvider
    converters/
      base.py            # OptionsChainConverter, OptionsQuotesConverter
      massive.py         # MassiveOptionsChainConverter, MassiveOptionsQuotesConverter
    storage.py
```

### Migration steps

1. Create `underlying/` and move: `providers/`, `converters/`, `storage.py`, `export.py`, `validate.py`. Keep `symbols.py`, `symbols.yaml` at marketdata root (common)
2. Update `config.py`: `SYMBOLS_CONFIG` path; `CACHE_ROOT` unchanged
3. Update `cli.py`: imports from `underlying.*`
4. Update `validation/marketdata.py`: imports from `src.marketdata.underlying.*`
5. Update tests: new import paths
6. Add `options/` package with `__init__.py`
7. **Polygon → Massive rename**: Rename polygon.py → massive.py; PolygonProvider/Converter → MassiveProvider/Converter; provider name `"polygon"` → `"massive"`; symbols.yaml; env vars; README
8. **Parquet default**: `DataProviderConfig.storage_backend` → `"parquet"`; `underlying/export` → write `.parquet` by default

### Import path changes

| Old                         | New                                    |
| --------------------------- | -------------------------------------- |
| `src.marketdata.providers`  | `src.marketdata.underlying.providers`  |
| `src.marketdata.converters` | `src.marketdata.underlying.converters` |
| `src.marketdata.storage`    | `src.marketdata.underlying.storage`    |
| `src.marketdata.export`     | `src.marketdata.underlying.export`     |
| `src.marketdata.validate`   | `src.marketdata.underlying.validate`   |
| `src.marketdata.symbols`    | (unchanged — common at root)           |

---

## Polygon → Massive Rename

Align codebase with Massive branding (Polygon.io rebranded Oct 2025).

### File renames

| Old | New |
|-----|-----|
| `underlying/providers/polygon.py` | `underlying/providers/massive.py` |
| `underlying/converters/polygon.py` | `underlying/converters/massive.py` |
| `options/providers/polygon.py` | `options/providers/massive.py` |
| `options/converters/polygon.py` | `options/converters/massive.py` |

### Class renames

| Old | New |
|-----|-----|
| `PolygonProvider` | `MassiveProvider` |
| `PolygonConverter` | `MassiveConverter` |
| `PolygonOptionsChainProvider` | `MassiveOptionsChainProvider` |
| `PolygonOptionsQuotesProvider` | `MassiveOptionsQuotesProvider` |
| `PolygonOptionsChainConverter` | `MassiveOptionsChainConverter` |
| `PolygonOptionsQuotesConverter` | `MassiveOptionsQuotesConverter` |

### Provider name (CLI and storage)

| Item | Old | New |
|------|-----|-----|
| CLI `--provider` default | `polygon` | `massive` |
| Cache path segment | `data/cache/polygon/` | `data/cache/massive/` |
| symbols.yaml key | `polygon:` | `massive:` |

### Environment variable

Support both: `MASSIVE_API_KEY` (preferred) or `POLYGON_API_KEY` for backwards compat.

### Code references to update

- `providers/__init__.py`, `converters/__init__.py` — export MassiveProvider, MassiveConverter
- `cli.py` — provider name `"massive"`, source string `"Massive REST"`
- `.env.example` — `MASSIVE_API_KEY=`
- `README.md` — "Polygon" → "Massive", `--provider massive`

### Ticker utilities (options)

- `polygon_ticker_to_contract_id` → `occ_ticker_to_contract_id`
- `contract_id_to_polygon_ticker` → `contract_id_to_occ_ticker`

---

## Parquet as Default

| Component                            | Change |
| ------------------------------------ | ------ |
| `DataProviderConfig.storage_backend` | Default `"csv"` → `"parquet"` |
| `underlying/export`                  | Default format = Parquet |
| `file_loader`                        | Deferred: Parquet support later |

---

## Massive Options API

- **Option Chain Snapshot** — `GET /v3/snapshot/options/{underlyingAsset}`
- **Historical Quotes** — `GET /v3/quotes/{optionsTicker}` (up to 50k/request)

**Plan requirement:** Options Advanced, Business, or Business+ Expansion.

### Official Python client

- `pip install -U massive`
- `list_snapshot_options_chain(ticker, params={...})` — chain with pagination
- `list_quotes(ticker=options_ticker, timestamp_gte=..., timestamp_lte=...)` — historical quotes

Add `massive>=1.12` to pyproject.toml.

---

## Options Architecture (Provider / Converter)

Same pattern as underlying: provider → raw → converter → canonical.

- **OptionsChainProvider** / **OptionsQuotesProvider** (ABCs)
- **OptionsChainConverter** / **OptionsQuotesConverter** (ABCs)
- Massive implementations use `massive.RESTClient`

### Ticker format

Canonical: `SPY|2026-01-17|C|480|100`  
OCC: `O:SPY250117C00480000`

---

## Implementation Plan

1. **Ticker conversion** — `options/ticker.py`: `occ_ticker_to_contract_id`, `contract_id_to_occ_ticker`
2. **Options provider base** — `options/providers/base.py`
3. **Massive options providers** — `options/providers/massive.py` via RESTClient
4. **Options converter base** — `options/converters/base.py`
5. **Massive options converters** — `options/converters/massive.py`
6. **Options storage** — Parquet cache; export to CSV for DataProvider (file_loader Parquet deferred)
7. **CLI** — `fetch-options` subcommand
8. **Validation** — `validation/options.py`

---

## Caveats

1. Chain snapshot is current (not historical)
2. Rate limits — many API calls for full chain
3. Options plan required for fetch

---

## File Summary

| Location | Purpose |
|----------|---------|
| `marketdata/config.py` | CACHE_ROOT, SYMBOLS_CONFIG |
| `marketdata/cli.py` | fetch, export, fetch-options |
| `marketdata/underlying/*` | MassiveProvider, MassiveConverter, storage, export, validate |
| `marketdata/options/ticker.py` | OCC ↔ contract_id |
| `marketdata/options/providers/massive.py` | MassiveOptionsChainProvider, MassiveOptionsQuotesProvider |
| `marketdata/options/converters/massive.py` | MassiveOptionsChainConverter, MassiveOptionsQuotesConverter |
| `marketdata/options/storage.py` | Parquet cache + export |
| `validation/options.py` | Validate via LocalFileDataProvider |
