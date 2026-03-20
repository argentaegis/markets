# 045: Options Strike Range Filter

Add optional `strike_gte` and `strike_lte` parameters to options data fetching. The Polygon/Massive API supports `strike_price_gte` and `strike_price_lte` on `list_options_contracts` natively.

---

## Objective

- Thread strike range parameters through CLI → fetch → chain provider → API
- Preserve backward compatibility: when both are None, no strike filtering
- Target known-good contracts (e.g. strike 680 for SPY 2026-02-17) when doing minimal fetches

---

## Changes

### 1. Base interface

**src/marketdata/options/sources/base.py** — Extend `OptionsChainProvider.get_chain_raw` with optional strike params:

```python
def get_chain_raw(
    self,
    underlying: str,
    expiration_date_gte: date,
    expiration_date_lte: date,
    *,
    strike_price_gte: float | None = None,
    strike_price_lte: float | None = None,
    limit: int | None = None,
) -> Any:
```

### 2. Massive provider

**src/marketdata/options/sources/massive_options.py** — Pass strike range to `list_options_contracts`; omit when None.

### 3. Fetch module

**src/marketdata/options/fetch.py** — Add `strike_gte`, `strike_lte` to `fetch_options`; forward to chain provider as `strike_price_gte`, `strike_price_lte`.

### 4. CLI

**src/marketdata/cli.py** — Add `--strike-gte` and `--strike-lte` to fetch-options subparser; pass to `fetch_options`.

### 5. Validation (optional)

**validation/options/run.py** — When doing minimal fetch, consider `strike_gte=670, strike_lte=690` to target strike 680. Defer if not needed for core feature.

---

## Flow

```
CLI fetch-options --strike-gte 670 --strike-lte 690
  → fetch_options(strike_gte=670, strike_lte=690)
    → MassiveOptionsChainProvider.get_chain_raw(..., strike_price_gte=670, strike_price_lte=690)
      → Polygon list_options_contracts
```

---

## Backward compatibility

- `strike_gte` and `strike_lte` default to `None` everywhere
- When both are None, behavior unchanged (no strike filtering)
- Existing callers continue to work

---

## Success criteria

- [x] Base interface extended; Massive provider passes strike params to API
- [x] fetch_options accepts strike_gte, strike_lte
- [x] CLI --strike-gte and --strike-lte work
- [x] Tests pass; no regression when params omitted
