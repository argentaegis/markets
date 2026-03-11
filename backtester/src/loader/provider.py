"""DataProvider ABC and LocalFileDataProvider.

Interface returns domain objects (Bars, Quotes, ContractSpec) — no DataFrames.
LocalFileDataProvider implements file-based storage: parquet underlying bars
(storage_backend, default), metadata index + per-contract quote CSVs.
Caches underlying bars and option quotes for efficiency.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..domain.bars import Bars, create_bars
from ..domain.contract import ContractSpec
from ..domain.contract_id import parse_contract_id
from ..domain.futures import FuturesContractSpec
from ..domain.quotes import Quote, QuoteError, QuoteStatus, Quotes
from .config import DataProviderConfig, MissingDataPolicy
from .storage.file_loader import (
    _df_to_barrows,
    load_metadata_index,
    load_option_quotes_batch_from_parquet,
    load_option_quotes_from_parquet,
    load_option_quotes_series,
    load_underlying_bars_df,
)

__all__ = [
    "DataProvider",
    "DataProviderConfig",
    "LocalFileDataProvider",
    "MissingContractMetadata",
    "MissingDataError",
    "MissingDataPolicy",
]

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MissingContractMetadata(Exception):
    def __init__(self, contract_id: str) -> None:
        self.contract_id = contract_id
        super().__init__(f"Contract metadata not found: {contract_id}")


class MissingDataError(Exception):
    pass


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------


class DataProvider(ABC):
    """Abstract DataProvider. Return types are domain objects, not DataFrames.

    Reasoning: Domain objects across module boundaries. ABC allows swapping
    LocalFileDataProvider for live/API provider in future.
    """

    @abstractmethod
    def get_underlying_bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> Bars:
        """OHLCV bars for underlying. Inclusive start <= ts <= end; ts = bar close, UTC."""
        ...

    @abstractmethod
    def get_option_chain(self, symbol: str, ts: datetime) -> list[str]:
        """Contract IDs not expired at ts. Sorted for determinism."""
        ...

    @abstractmethod
    def get_option_quotes(self, contract_ids: list[str], ts: datetime) -> Quotes:
        """As-of lookup: last quote with quote_ts <= ts. Entry for every contract_id."""
        ...

    @abstractmethod
    def get_contract_metadata(self, contract_id: str) -> ContractSpec | None:
        """Metadata from index first; if not found, apply missing_data_policy."""
        ...

    @abstractmethod
    def get_futures_contract_spec(self, symbol: str) -> FuturesContractSpec | None:
        """Futures contract spec for symbol, if available. None for non-futures providers."""
        ...


# ---------------------------------------------------------------------------
# LocalFileDataProvider
# ---------------------------------------------------------------------------


class LocalFileDataProvider(DataProvider):
    """File-based DataProvider. Option B storage + metadata index. Caches underlying and option quotes.

    Reasoning: Caches avoid repeated file I/O during backtest. get_option_quotes uses
    as-of lookup (last quote_ts <= ts). RETURN_PARTIAL populates ContractSpec from
    parse when not in index; metadata_missing=True for diagnostics.
    """

    def __init__(self, config: DataProviderConfig) -> None:
        self._config = config
        self._underlying_df_cache: dict[tuple[str, str], pd.DataFrame | None] = {}
        self._quotes_cache: dict[str, list[tuple[datetime, float, float]]] = {}
        self._metadata: list[dict] | None = None
        self._metadata_by_underlying: dict[str, list[dict]] | None = None
        self._metadata_by_contract_id: dict[str, dict] | None = None
        self._crossed_quotes_sanitized: int = 0
        self._run_diagnostics: dict[str, object] = {}

    def _ensure_metadata(self) -> list[dict]:
        if self._metadata is None:
            meta_path = self._config.options_path / "metadata" / "index.csv"
            self._metadata = load_metadata_index(meta_path)
            self._build_metadata_indexes()
        return self._metadata

    def _build_metadata_indexes(self) -> None:
        """Build indexes for O(1) get_contract_metadata and fast get_option_chain (Plan 251b)."""
        by_underlying: dict[str, list[dict]] = {}
        by_contract_id: dict[str, dict] = {}
        for r in self._metadata or []:
            cid = r.get("contract_id")
            if cid:
                by_contract_id[cid] = r
            sym = r.get("underlying")
            if sym:
                by_underlying.setdefault(sym, []).append(r)
        for rows in by_underlying.values():
            rows.sort(key=lambda x: (x.get("expiry"), x.get("contract_id", "")))
        self._metadata_by_underlying = by_underlying
        self._metadata_by_contract_id = by_contract_id

    def _get_underlying_df(self, symbol: str, timeframe: str) -> pd.DataFrame | None:
        """Load and cache underlying bars as a DatetimeIndex DataFrame."""
        key = (symbol, timeframe)
        if key in self._underlying_df_cache:
            return self._underlying_df_cache[key]
        if timeframe not in self._config.timeframes_supported:
            if self._config.missing_data_policy == "RAISE":
                raise MissingDataError(f"Unsupported timeframe: {timeframe}")
            self._underlying_df_cache[key] = None
            return None
        ext = "parquet" if self._config.storage_backend == "parquet" else "csv"
        path = self._config.underlying_path / f"{symbol}_{timeframe}.{ext}"
        df = load_underlying_bars_df(path)
        self._underlying_df_cache[key] = df
        if df is not None and not df.empty:
            key_str = f"{symbol}|{timeframe}"
            if "data_ranges" not in self._run_diagnostics:
                self._run_diagnostics["data_ranges"] = {}
            self._run_diagnostics["data_ranges"][key_str] = {
                "min_ts": df.index.min().to_pydatetime(),
                "max_ts": df.index.max().to_pydatetime(),
            }
        return df

    def _warm_quote_cache(self, contract_ids: list[str]) -> None:
        """Batch-load missing contracts from parquet in one read (Plan 251a)."""
        parquet_path = self._config.options_path / "quotes.parquet"
        if not parquet_path.exists():
            return  # CSV storage: let _get_quote_series load per-contract
        missing = [cid for cid in contract_ids if cid not in self._quotes_cache]
        if not missing:
            return
        batch = load_option_quotes_batch_from_parquet(parquet_path, missing)
        for cid, series in batch.items():
            self._quotes_cache[cid] = series
        for cid in missing:
            if cid not in self._quotes_cache:
                self._quotes_cache[cid] = []

    def _get_quote_series(self, contract_id: str) -> list[tuple[datetime, float, float]]:
        if contract_id in self._quotes_cache:
            return self._quotes_cache[contract_id]
        parquet_path = self._config.options_path / "quotes.parquet"
        if parquet_path.exists():
            series = load_option_quotes_from_parquet(parquet_path, contract_id)
        else:
            path = self._config.options_path / "quotes" / f"{contract_id}.csv"
            series = load_option_quotes_series(path)
        self._quotes_cache[contract_id] = series
        return series

    def get_underlying_bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> Bars:
        df = self._get_underlying_df(symbol, timeframe)
        if df is None or df.empty:
            if self._config.missing_data_policy == "RAISE":
                raise MissingDataError(f"No data for {symbol} {timeframe}")
            return create_bars(symbol, timeframe, start, end, [])

        if timeframe == "1d":
            start_date = start.date() if hasattr(start, "date") else start
            end_date = end.date() if hasattr(end, "date") else end
            mask = (df.index.date >= start_date) & (df.index.date <= end_date)
            sliced = df[mask]
        else:
            sliced = df.loc[start:end]

        if sliced.empty:
            if self._config.missing_data_policy == "RAISE":
                raise MissingDataError(
                    f"No bars for {symbol} {timeframe} in [{start}, {end}]"
                )
            return create_bars(symbol, timeframe, start, end, [])

        rows = _df_to_barrows(sliced)
        return Bars(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            timezone="UTC",
            rows=rows,
        )

    def get_option_chain(self, symbol: str, ts: datetime) -> list[str]:
        self._ensure_metadata()
        ts_date = ts.date() if hasattr(ts, "date") else ts
        meta_list = (self._metadata_by_underlying or {}).get(symbol, [])
        result = [r["contract_id"] for r in meta_list if r.get("expiry", ts_date) > ts_date]
        return sorted(result)

    def _append_quote_missingness(self, cid: str, reason: str, ts: datetime) -> None:
        """Append to quote_missingness diagnostics for run manifest."""
        if "quote_missingness" not in self._run_diagnostics:
            self._run_diagnostics["quote_missingness"] = []
        self._run_diagnostics["quote_missingness"].append(
            {"contract_id": cid, "reason": reason, "ts": ts.isoformat()}
        )

    def _resolve_single_quote(
        self,
        cid: str,
        series: list[tuple[datetime, float, float]],
        ts: datetime,
        max_age: int | None,
    ) -> Quote | QuoteStatus:
        """Resolve as-of quote for one contract. Raises MissingDataError on RAISE policy."""
        candidates = [(t, b, a) for t, b, a in series if t <= ts]
        if not candidates:
            self._append_quote_missingness(cid, "MISSING", ts)
            return QuoteStatus.MISSING
        t, bid, ask = candidates[-1]
        age = (ts - t).total_seconds()
        if max_age is not None and age > max_age:
            if self._config.missing_data_policy == "RAISE":
                raise MissingDataError(
                    f"Quote for {cid} flagged stale: age={age:.0f}s > max_quote_age ({max_age}s). "
                    "For historical backtesting, use max_quote_age=None."
                )
            self._append_quote_missingness(cid, "STALE", ts)
            return QuoteStatus.STALE
        quote = Quote.from_raw(bid=bid, ask=ask)
        if quote.crossed_market:
            self._crossed_quotes_sanitized += 1
        return quote

    def get_option_quotes(self, contract_ids: list[str], ts: datetime) -> Quotes:
        self._warm_quote_cache(contract_ids)
        mapping: dict[str, Quote | QuoteStatus | None] = {}
        errors: list[QuoteError] = []
        max_age = self._config.get_max_quote_age_seconds()

        for cid in contract_ids:
            series = self._get_quote_series(cid)
            try:
                result = self._resolve_single_quote(cid, series, ts, max_age)
            except MissingDataError:
                raise
            if result is QuoteStatus.MISSING:
                mapping[cid] = QuoteStatus.MISSING
                errors.append(QuoteError(
                    cid, "MISSING",
                    "No quote with quote_ts <= ts. Check data coverage for this contract.",
                ))
            elif result is QuoteStatus.STALE:
                mapping[cid] = QuoteStatus.STALE
                errors.append(QuoteError(
                    cid, "STALE",
                    f"Quote age > max_quote_age ({max_age}s). Use max_quote_age=None for historical.",
                ))
            else:
                mapping[cid] = result

        return Quotes(ts=ts, quotes=mapping, errors=errors)

    def get_contract_metadata(self, contract_id: str) -> ContractSpec | None:
        self._ensure_metadata()
        r = (self._metadata_by_contract_id or {}).get(contract_id)
        if r is not None:
            return ContractSpec(
                contract_id=r["contract_id"],
                underlying_symbol=r["underlying"],
                strike=float(r["strike"]),
                expiry=r["expiry"],
                right=r["right"],
                multiplier=float(r["multiplier"]),
            )
        # Not in index: parse and apply policy
        try:
            parsed = parse_contract_id(contract_id)
        except ValueError:
            if self._config.missing_data_policy == "RAISE":
                raise MissingContractMetadata(contract_id)
            return None
        if self._config.missing_data_policy == "RAISE":
            raise MissingContractMetadata(contract_id)
        if self._config.missing_data_policy == "RETURN_EMPTY":
            return None
        # RETURN_PARTIAL: multiplier from config default, not from parse
        return ContractSpec(
            contract_id=contract_id,
            underlying_symbol=parsed.underlying,
            strike=parsed.strike,
            expiry=parsed.expiry,
            right=parsed.right,
            multiplier=self._config.default_multiplier,
            metadata_missing=True,
        )

    def get_futures_contract_spec(self, symbol: str) -> FuturesContractSpec | None:
        """Stub: LocalFileDataProvider is option-centric; futures not implemented."""
        raise NotImplementedError("get_futures_contract_spec not implemented for LocalFileDataProvider")

    def get_run_manifest_data(self) -> dict:
        """Return config + diagnostics for run manifest (reproducibility)."""
        data: dict = {"config": self._config.to_dict()}
        if self._run_diagnostics:
            data["diagnostics"] = {
                **self._run_diagnostics,
                "crossed_quotes_sanitized": self._crossed_quotes_sanitized,
            }
        else:
            data["diagnostics"] = {"crossed_quotes_sanitized": self._crossed_quotes_sanitized}
        return data
