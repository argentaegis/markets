"""CLI entry: md fetch, md export, md fetch-options, md import-databento, md import-philippdubach.

Pre-backtest workflow: fetch caches raw → export validates and writes CSV for DataProvider.
fetch-options populates options chain + quotes (metadata index + per-contract CSVs).
import-databento ingests manually-downloaded Databento CSV.
import-philippdubach ingests philippdubach/options-dataset-hist Parquet into options layout.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from .config import CACHE_ROOT, PROJECT_ROOT
from .options.fetch import fetch_options
from .symbols import resolve
from .underlying.export import export_split, filter_range
from .underlying.sources.registry import get_converter, get_provider
from .underlying.storage import read_cache, write_cache
from .underlying.validate import ValidationError, validate_canonical
from .options.philippdubach_import import import_philippdubach

_SOURCE_LABELS: dict[str, str] = {"massive": "Massive REST", "databento": "Databento XNAS.ITCH"}

_DATABENTO_WARN = """Databento does not support programmatic fetch. Ingest a manually-downloaded file instead:
  md import-databento --file <path> --symbol <SPY|ESH1|ES> --interval 1m [--continuous] [--out data/exports/<symbol>]"""


def _parse_date(s: str) -> date:
    return date.fromisoformat(s.strip())


def cmd_fetch(args: argparse.Namespace) -> int:
    """Fetch underlying OHLCV from provider, convert to canonical, cache. Exit 1 if no data."""
    provider_name = args.provider
    if provider_name == "databento":
        print(_DATABENTO_WARN)
        return 1
    user_symbol = args.symbol.upper()
    provider_symbol = resolve(user_symbol, provider_name)
    interval = args.interval
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    provider = get_provider(provider_name)
    converter = get_converter(provider_name)
    raw = provider.get_ohlcv_raw(provider_symbol, start, end, interval)
    df = converter.to_canonical(raw)
    if df.empty:
        print("No data returned")
        return 1
    path = write_cache(
        df,
        provider=provider_name,
        user_symbol=user_symbol,
        provider_symbol=provider_symbol,
        interval=interval,
        start=start,
        end=end,
        source=_SOURCE_LABELS.get(provider_name, provider_name),
    )
    print(f"Cached {len(df)} bars to {path}")
    return 0


def _ensure_cached_or_fetch(
    provider_name: str,
    user_symbol: str,
    provider_symbol: str,
    interval: str,
    start: date,
    end: date,
    no_fetch: bool,
):
    """Return cached DataFrame or fetch and cache. Returns None if no data."""
    df = read_cache(provider_name, user_symbol, interval, start, end)
    if df is None and not no_fetch:
        if provider_name == "databento":
            print(_DATABENTO_WARN)
            return None
        provider = get_provider(provider_name)
        converter = get_converter(provider_name)
        raw = provider.get_ohlcv_raw(provider_symbol, start, end, interval)
        df = converter.to_canonical(raw)
        if not df.empty:
            write_cache(
                df,
                provider=provider_name,
                user_symbol=user_symbol,
                provider_symbol=provider_symbol,
                interval=interval,
                start=start,
                end=end,
                source=_SOURCE_LABELS.get(provider_name, provider_name),
            )
    return df


def cmd_export(args: argparse.Namespace) -> int:
    """Export cached underlying to CSV/Parquet. Validates canonical format; --no-fetch skips fetch if cache missing."""
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    user_symbol = args.symbol.upper()
    df = _ensure_cached_or_fetch(
        args.provider, user_symbol, resolve(user_symbol, args.provider),
        args.interval, start, end, args.no_fetch,
    )
    if df is None or df.empty:
        print("No data available. Run md fetch first or omit --no-fetch.")
        return 1
    filtered = filter_range(df, start, end)
    if filtered.empty:
        print("No data in requested range")
        return 1
    try:
        for w in validate_canonical(filtered):
            print(f"Warning: {w}")
    except ValidationError as e:
        print(f"Validation failed: {e}")
        return 1
    fmt = getattr(args, "format", "parquet")
    paths = export_split(filtered, Path(args.out), user_symbol, args.split, format=fmt)
    print(f"Exported {len(paths)} file(s) to {args.out}")
    for p in paths:
        print(f"  {p}")
    return 0


def cmd_import_databento(args: argparse.Namespace) -> int:
    """Ingest manually-downloaded Databento OHLCV CSV to export layout."""
    path = Path(args.file)
    if not path.exists():
        print(f"File not found: {path}")
        return 1
    symbol = args.symbol.upper()
    interval = args.interval
    continuous = getattr(args, "continuous", False)
    out_dir = Path(args.out) if args.out else PROJECT_ROOT / "data" / "exports" / symbol.lower()
    out_dir = out_dir.resolve()

    try:
        if path.suffix == ".zst" or str(path).endswith(".csv.zst"):
            try:
                import zstandard as zstd
            except ImportError:
                print("Reading .zst requires: pip install zstandard")
                return 1
            with zstd.open(path, "rt") as f:
                df = pd.read_csv(f)
        else:
            df = pd.read_csv(path)
    except Exception as e:
        print(f"Failed to read {path}: {e}")
        return 1

    if "ts_event" not in df.columns:
        print("CSV missing ts_event column. Expected Databento ohlcv format.")
        return 1

    if continuous:
        if "symbol" not in df.columns:
            print("CSV missing symbol column. Required for --continuous.")
            return 1
        from src.marketdata.underlying.sources.continuous_futures import build_continuous_series
        canonical = build_continuous_series(df, root=symbol)
        if canonical.empty:
            print(f"No continuous data for root {symbol}. Check CSV has {symbol}[HMUZ][0-9] contracts.")
            return 1
        out_name = f"{symbol}_{interval}.parquet"
    else:
        if "symbol" in df.columns:
            df = df[df["symbol"] == symbol].copy()
            if df.empty:
                print(f"No rows for symbol {symbol}. Check --symbol.")
                return 1
        converter = get_converter("databento")
        canonical = converter.to_canonical(df)
        if canonical.empty:
            print("No data after conversion")
            return 1
        out_name = f"{symbol}_{interval}.parquet"

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / out_name
    canonical.to_parquet(out_path, index=False)
    print(f"Imported {len(canonical)} bars to {out_path}")
    return 0


def cmd_import_philippdubach(args: argparse.Namespace) -> int:
    """Import philippdubach options Parquet into backtester options layout."""
    cache_dir = Path(args.cache_dir)
    if not cache_dir.exists():
        print(f"Cache dir not found: {cache_dir}")
        return 1
    out_dir = Path(args.out) if args.out else PROJECT_ROOT / "data" / "exports" / "options" / args.symbol.lower()
    out_dir = out_dir.resolve()
    result = import_philippdubach(
        cache_dir=cache_dir,
        out_dir=out_dir,
        symbol=args.symbol.upper(),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    print(f"Imported {result['metadata_count']} contracts, {result['quotes_rows']} quote rows → {result['out_dir']}")
    return 0


def cmd_fetch_options(args: argparse.Namespace) -> int:
    """Fetch options chain + quotes. Writes metadata index + per-contract quote CSVs for DataProvider."""
    provider_name = args.provider
    underlying = args.underlying
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    out_dir = Path(args.out) if args.out else None
    expiry_gte = _parse_date(args.expiry_gte) if args.expiry_gte else start
    expiry_lte = _parse_date(args.expiry_lte) if args.expiry_lte else end

    try:
        result = fetch_options(
            underlying, expiry_gte, expiry_lte,
            out_dir=out_dir,
            provider=provider_name,
            max_contracts=getattr(args, "max_contracts", None),
            max_quotes=getattr(args, "max_quotes", None),
            strike_gte=getattr(args, "strike_gte", None),
            strike_lte=getattr(args, "strike_lte", None),
        )
    except (KeyError, ValueError) as e:
        print(f"Unknown options provider: {provider_name}. {e}")
        return 1
    except RuntimeError as e:
        print(str(e))
        return 1
    except Exception:
        raise
    print(f"Fetched {result.metadata_count} contracts, wrote quotes for {result.quotes_written} → {result.out_dir}")
    return 0


def _add_fetch_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("fetch", help="Fetch data from provider and cache")
    p.add_argument("--provider", default="massive", help="Provider (default: massive)")
    p.add_argument("--symbol", required=True, help="Symbol (e.g. SPX)")
    p.add_argument("--interval", default="1d", help="Interval (default: 1d)")
    p.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    p.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    p.set_defaults(func=cmd_fetch)


def _add_export_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("export", help="Export cached data to Parquet or CSV")
    p.add_argument("--provider", default="massive", help="Provider (default: massive)")
    p.add_argument("--symbol", required=True, help="Symbol (e.g. SPX)")
    p.add_argument("--interval", default="1d", help="Interval (default: 1d)")
    p.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    p.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    p.add_argument("--split", choices=["none", "month", "quarter", "year"], default="month")
    p.add_argument("--format", choices=["parquet", "csv"], default="parquet", help="Output format (default: parquet)")
    p.add_argument("--out", required=True, help="Output directory")
    p.add_argument("--no-fetch", action="store_true", help="Do not fetch if cache missing")
    p.set_defaults(func=cmd_export)


def _add_import_philippdubach_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "import-philippdubach",
        help="Import philippdubach/options-dataset-hist Parquet into options layout",
    )
    p.add_argument(
        "--cache-dir",
        required=True,
        help="Dir with options_YYYY.parquet (e.g. data/cache/philippdubach/parquet_spy)",
    )
    p.add_argument("--symbol", default="SPY", help="Underlying symbol (default: SPY)")
    p.add_argument("--start-year", default="2021", help="First year (default: 2021)")
    p.add_argument("--end-year", default="2025", help="Last year (default: 2025)")
    p.add_argument("--out", default=None, help="Output dir (default: data/exports/options/{symbol})")
    p.set_defaults(func=cmd_import_philippdubach)


def _add_import_databento_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("import-databento", help="Ingest manually-downloaded Databento OHLCV CSV")
    p.add_argument("--file", required=True, help="Path to Databento CSV or .csv.zst")
    p.add_argument("--symbol", required=True, help="Symbol or root (e.g. SPY, ESH1, ES for continuous)")
    p.add_argument("--interval", default="1m", help="Interval for output filename (default: 1m)")
    p.add_argument("--continuous", action="store_true", help="Build front-month continuous series (futures only)")
    p.add_argument("--out", default=None, help="Output dir (default: data/exports/{symbol})")
    p.set_defaults(func=cmd_import_databento)


def _add_fetch_options_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("fetch-options", help="Fetch options chain + quotes from Massive")
    p.add_argument("--provider", default="massive", help="Provider (default: massive)")
    p.add_argument("--underlying", required=True, help="Underlying symbol (e.g. SPY)")
    p.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    p.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    p.add_argument("--out", default=None, help="Output dir (default: data/cache/massive/options/{underlying})")
    p.add_argument("--expiry-gte", help="Filter chain: expiry >= date")
    p.add_argument("--expiry-lte", help="Filter chain: expiry <= date")
    p.add_argument("--max-contracts", type=int, default=None, help="Limit chain size (free tier 5 req/min)")
    p.add_argument("--max-quotes", type=int, default=None, help="Limit quote fetches per contract (~13s each)")
    p.add_argument("--strike-gte", type=float, default=None, help="Filter chain: strike >= value")
    p.add_argument("--strike-lte", type=float, default=None, help="Filter chain: strike <= value")
    p.set_defaults(func=cmd_fetch_options)


def main() -> int:
    load_dotenv(override=True)
    parser = argparse.ArgumentParser(prog="md", description="Market data CLI: fetch and export OHLCV")
    sub = parser.add_subparsers(dest="cmd", required=True)
    _add_fetch_parser(sub)
    _add_export_parser(sub)
    _add_import_databento_parser(sub)
    _add_import_philippdubach_parser(sub)
    _add_fetch_options_parser(sub)
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
