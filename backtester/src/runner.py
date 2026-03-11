"""CLI runner — parse config, wire engine + reporter, produce run artifacts.

Reasoning: thin wrapper that provides a user-facing entry point for running
backtests. No logic beyond parsing and wiring. Supports YAML and JSON config.

Usage:
    python -m src.runner config.yaml [--output-dir runs/] [--silent]

    Progress is shown by default. Use --silent to suppress.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.broker.fee_model import FeeModelConfig
from src.domain.config import BacktestConfig
from src.engine.engine import run_backtest
from src.loader.provider import DataProviderConfig, LocalFileDataProvider
from src.reporter.reporter import generate_report
from src.strategies.strategizer_adapter import StrategizerStrategy

STRATEGY_NAMES = [
    "orb_5m",
    "buy_and_hold",
    "buy_and_hold_underlying",
    "covered_call",
    "trend_entry_trailing_stop",
    "trend_follow_risk_sized",
    "tactical_asset_allocation",
]


def _parse_config(config_path: Path) -> dict:
    """Load YAML or JSON config file. Raises FileNotFoundError or ValueError."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    text = config_path.read_text()
    if config_path.suffix in (".yaml", ".yml"):
        return yaml.safe_load(text)
    if config_path.suffix == ".json":
        return json.loads(text)
    raise ValueError(f"Unsupported config format: {config_path.suffix}. Use .yaml or .json")


def _build_strategy(
    strategy_config: dict,
    config: BacktestConfig | None = None,
    provider: "LocalFileDataProvider | None" = None,
):
    """Instantiate StrategizerStrategy from config. Runs strategizer in-process (no HTTP)."""
    if config is None:
        raise ValueError("Config required for StrategizerStrategy")
    name = strategy_config.get("name", "")
    if name not in STRATEGY_NAMES:
        raise ValueError(f"Unknown strategy: {name}. Available: {STRATEGY_NAMES}")

    params = dict(strategy_config.get("params") or {})
    for k, v in strategy_config.items():
        if k not in ("name", "params"):
            params[k] = v

    if name == "orb_5m" and config.futures_contract_spec is None:
        raise ValueError("orb_5m requires futures_contract_spec in config")

    return StrategizerStrategy(
        strategy_name=name,
        strategy_params=params,
        config=config,
    )


def _parse_futures_contract_spec(raw: dict | None) -> "FuturesContractSpec | None":
    """Parse futures_contract_spec from config dict."""
    if not raw or not isinstance(raw, dict):
        return None
    from datetime import time
    from src.domain.futures import FuturesContractSpec, TradingSession
    sess = raw.get("session") or {}
    session = TradingSession(
        name=str(sess.get("name", "RTH")),
        start_time=time.fromisoformat(str(sess.get("start_time", "09:30:00"))),
        end_time=time.fromisoformat(str(sess.get("end_time", "16:00:00"))),
        timezone=str(sess.get("timezone", "America/New_York")),
    )
    return FuturesContractSpec(
        symbol=str(raw.get("symbol", "")),
        tick_size=float(raw.get("tick_size", 0.25)),
        point_value=float(raw.get("point_value", 50.0)),
        session=session,
    )


_CATALOG_PATH = Path("data/catalog.yaml")


def _load_catalog(catalog_path: Path | None = None) -> dict:
    """Load the data catalog mapping symbols to their data locations."""
    path = catalog_path or _CATALOG_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Data catalog not found at {path}. "
            "Create data/catalog.yaml with symbol-to-path mappings."
        )
    return yaml.safe_load(path.read_text())


def _resolve_from_catalog(symbol: str, catalog: dict) -> tuple[str, str | None]:
    """Look up symbol in catalog. Returns (underlying_path, options_path).

    Raises ValueError if symbol not found — configs should never silently get empty data.
    """
    symbols = catalog.get("symbols", {})
    entry = symbols.get(symbol)
    if entry is None:
        available = ", ".join(sorted(symbols.keys())) or "(none)"
        raise ValueError(
            f"Symbol '{symbol}' not found in data catalog. "
            f"Available symbols: {available}. "
            f"Add an entry to {_CATALOG_PATH} to register this symbol's data."
        )
    underlying_path = entry.get("underlying_path")
    if not underlying_path:
        raise ValueError(
            f"Symbol '{symbol}' in catalog is missing 'underlying_path'."
        )
    return underlying_path, entry.get("options_path")


def _build_backtest_config(raw: dict, catalog: dict | None = None) -> BacktestConfig:
    """Build BacktestConfig from parsed YAML/JSON dict.

    Data paths resolved from catalog by symbol. The data_provider block in configs
    is an escape hatch for tests that need to point at fixture data.
    For multi-symbol (symbols: [...]), resolves each symbol from catalog into extra_underlying_paths.
    """
    symbol = raw.get("symbol", "SPY")
    symbols = raw.get("symbols") or []
    if not isinstance(symbols, list):
        symbols = []
    dp_raw = raw.get("data_provider", {})
    defaults = (catalog or {}).get("defaults", {})

    if dp_raw.get("underlying_path"):
        underlying_path = dp_raw["underlying_path"]
        options_path = dp_raw.get("options_path", "")
        extra_underlying_paths = {}
    else:
        if catalog is None:
            catalog = _load_catalog()
        underlying_path, options_path = _resolve_from_catalog(symbol, catalog)
        options_path = options_path or ""
        extra_underlying_paths = {}
        for sym in symbols:
            if sym != symbol:
                up, _ = _resolve_from_catalog(sym, catalog)
                extra_underlying_paths[sym] = Path(up)

    dp_config = DataProviderConfig(
        underlying_path=underlying_path,
        options_path=options_path,
        extra_underlying_paths=extra_underlying_paths,
        timeframes_supported=dp_raw.get(
            "timeframes_supported",
            defaults.get("timeframes_supported", ["1d", "1h", "1m"]),
        ),
        missing_data_policy=dp_raw.get(
            "missing_data_policy",
            defaults.get("missing_data_policy", "RETURN_PARTIAL"),
        ),
        max_quote_age=dp_raw.get("max_quote_age"),
    )

    start_str = raw.get("start", "")
    end_str = raw.get("end", "")
    start = datetime.fromisoformat(start_str) if start_str else datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime.fromisoformat(end_str) if end_str else datetime(2026, 1, 31, tzinfo=timezone.utc)

    fee_config = None
    fee_raw = raw.get("fee_config")
    if fee_raw:
        fee_config = FeeModelConfig(
            per_contract=float(fee_raw.get("per_contract", 0.0)),
            per_order=float(fee_raw.get("per_order", 0.0)),
        )

    fc_spec = _parse_futures_contract_spec(raw.get("futures_contract_spec"))
    instrument_type = str(raw.get("instrument_type", "option"))

    strategy_name = raw.get("strategy", {}).get("name", "")

    return BacktestConfig(
        symbol=raw.get("symbol", "SPY"),
        start=start,
        end=end,
        timeframe_base=raw.get("timeframe_base", "1m"),
        data_provider_config=dp_config,
        initial_cash=float(raw.get("initial_cash", 100_000.0)),
        seed=raw.get("seed"),
        fee_config=fee_config,
        instrument_type=instrument_type,
        futures_contract_spec=fc_spec,
        strategy_name=strategy_name,
        symbols=symbols,
    )


def run_backtest_cli(
    config_path: Path,
    output_dir: Path,
    *,
    progress: bool = True,
) -> Path:
    """Run a backtest from a config file and produce report artifacts.

    Reasoning: single entry point for CLI usage. Parses config, builds
    all components, runs engine, generates report. Returns path to run directory.
    """
    raw = _parse_config(config_path)
    catalog = _load_catalog() if not raw.get("data_provider", {}).get("underlying_path") else None
    config = _build_backtest_config(raw, catalog=catalog)
    provider = LocalFileDataProvider(config.data_provider_config)
    strategy = _build_strategy(raw.get("strategy", {}), config=config, provider=provider)

    on_progress = None
    if progress:

        def _print_progress(step_index: int, total_steps: int, ts: datetime) -> None:
            pct = 100.0 * step_index / total_steps if total_steps else 0
            ts_str = ts.strftime("%Y-%m-%d %H:%M UTC")
            print(f"\rStep {step_index}/{total_steps} ({pct:.1f}%) - {ts_str}", end="", flush=True)

        on_progress = _print_progress

    t0 = time.perf_counter()
    result = run_backtest(config, strategy, provider, on_progress=on_progress)
    elapsed_seconds = time.perf_counter() - t0
    if progress:
        print()
    run_timestamp = datetime.now(timezone.utc)
    run_dir = generate_report(
        result,
        output_dir / "runs",
        provider=provider,
        run_timestamp=run_timestamp,
        elapsed_seconds=elapsed_seconds,
    )
    return run_dir


def main() -> None:
    """CLI entry point: python -m src.runner config.yaml [--output-dir DIR] [--silent]."""
    if len(sys.argv) < 2:
        print("Usage: python -m src.runner <config.yaml> [--output-dir DIR] [--silent]")
        sys.exit(1)

    config_path = Path(sys.argv[1])
    output_dir = Path(".")
    if "--output-dir" in sys.argv:
        idx = sys.argv.index("--output-dir")
        if idx + 1 < len(sys.argv):
            output_dir = Path(sys.argv[idx + 1])

    progress = "--silent" not in sys.argv

    run_dir = run_backtest_cli(config_path, output_dir, progress=progress)
    print(f"Report written to: {run_dir}")


if __name__ == "__main__":
    main()
