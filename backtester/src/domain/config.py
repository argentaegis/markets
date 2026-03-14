"""BacktestConfig — run parameters: symbol, dates, timeframe, data, broker, fills.

All runs driven by typed BacktestConfig. to_dict/from_dict for run_manifest.json
and reproducibility. data_provider_config wires DataProvider without hardcoding paths.
initial_cash, broker (fee schedule), fill_config drive the engine loop (A4: configuration-first).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from typing import TYPE_CHECKING

from src.domain.futures import FuturesContractSpec
from src.loader.config import DataProviderConfig

if TYPE_CHECKING:
    from src.broker.fill_model import FillModelConfig


def _parse_max_quote_age(val: int | float | None, key_present: bool) -> int | None:
    """Parse max_quote_age from dict: None if explicitly null, else int (default 60)."""
    if key_present and val is None:
        return None
    return int(val) if val is not None else 60


def _fill_config_to_dict(cfg: FillModelConfig | None) -> dict | None:
    """Serialize FillModelConfig for JSON, or None."""
    if cfg is None:
        return None
    return {"synthetic_spread_bps": cfg.synthetic_spread_bps}


def _fill_config_from_dict(d: dict | None) -> FillModelConfig | None:
    """Restore FillModelConfig from dict, or None.

    Reasoning: Lazy import breaks circular dependency (domain -> broker -> domain).
    """
    if not d:
        return None
    from src.broker.fill_model import FillModelConfig as _FillModelConfig

    return _FillModelConfig(
        synthetic_spread_bps=float(d.get("synthetic_spread_bps", 50.0)),
    )


@dataclass
class BacktestConfig:
    """Backtest run config. Serializable for run_manifest.json.

    Reasoning: A4 configuration-first. broker selects fee schedule; fill_config
    for spread model. broker is required.
    """

    symbol: str
    start: datetime
    end: datetime
    timeframe_base: str
    data_provider_config: DataProviderConfig
    broker: str
    seed: int | None = None
    initial_cash: float = 100_000.0
    fill_config: FillModelConfig | None = None
    instrument_type: str = "option"  # "equity" | "option" | "future"
    futures_contract_spec: FuturesContractSpec | None = None
    strategy_name: str = ""  # For report title and metadata (e.g. buy_and_hold_underlying)
    symbols: list[str] = field(default_factory=list)  # Multi-symbol universe; empty = single-symbol (use symbol)
    fill_timing: str = "same_bar_close"  # "same_bar_close" (default) | "next_bar_open"
    option_contract_ids: list[str] | None = None  # Explicit contracts; skips get_option_chain when set
    option_chain_sigma_limit: float | None = 2.0  # ±Nσ ATM filter for chain; None = no filter
    option_chain_vol_default: float = 0.20  # Annual vol for σ filter when no bar history
    assignment_model: str = "cash"  # "cash" | "physical" — physical for covered call (Plan 267)

    def to_dict(self) -> dict:
        """Serialize for JSON. Paths and datetimes become strings.

        Reasoning: run_manifest.json stores config for reproducibility and reporting.
        """
        dp = self.data_provider_config
        dp_dict = dp.to_dict() if isinstance(dp, DataProviderConfig) else {}
        fill_dict = _fill_config_to_dict(self.fill_config)
        fc = self.futures_contract_spec
        fc_dict: dict | None = None
        if fc is not None:
            fc_dict = {
                "symbol": fc.symbol,
                "tick_size": fc.tick_size,
                "point_value": fc.point_value,
                "session": {
                    "name": fc.session.name,
                    "start_time": fc.session.start_time.isoformat(),
                    "end_time": fc.session.end_time.isoformat(),
                    "timezone": fc.session.timezone,
                },
            }
        return {
            "symbol": self.symbol,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "timeframe_base": self.timeframe_base,
            "data_provider_config": dp_dict,
            "seed": self.seed,
            "initial_cash": self.initial_cash,
            "broker": self.broker,
            "fill_config": fill_dict,
            "instrument_type": self.instrument_type,
            "futures_contract_spec": fc_dict,
            "strategy_name": self.strategy_name,
            "symbols": list(self.symbols),
            "fill_timing": self.fill_timing,
            "option_contract_ids": list(self.option_contract_ids) if self.option_contract_ids else None,
            "option_chain_sigma_limit": self.option_chain_sigma_limit,
            "option_chain_vol_default": self.option_chain_vol_default,
            "assignment_model": self.assignment_model,
        }

    @classmethod
    def from_dict(cls, d: dict) -> BacktestConfig:
        """Restore from dict (e.g. run_manifest). Round-trip with to_dict.

        Reasoning: Enables loading saved runs; isoformat datetimes round-trip correctly.
        """
        dp_d = d.get("data_provider_config") or {}
        if isinstance(dp_d, dict):
            extra = dp_d.get("extra_underlying_paths") or {}
            dp_config = DataProviderConfig(
                underlying_path=dp_d.get("underlying_path", ""),
                options_path=dp_d.get("options_path", ""),
                timeframes_supported=dp_d.get("timeframes_supported", ["1d", "1h", "1m"]),
                storage_backend=dp_d.get("storage_backend", "parquet"),
                missing_data_policy=dp_d.get("missing_data_policy", "RAISE"),
                max_quote_age=_parse_max_quote_age(dp_d.get("max_quote_age"), "max_quote_age" in dp_d),
                default_multiplier=float(dp_d.get("default_multiplier", 100.0)),
                extra_underlying_paths=dict(extra),
            )
        else:
            dp_config = dp_d

        start_s = d.get("start", "")
        end_s = d.get("end", "")
        start = (
            datetime.fromisoformat(start_s.replace("Z", "+00:00")) if start_s
            else datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        end = (
            datetime.fromisoformat(end_s.replace("Z", "+00:00")) if end_s
            else datetime(2026, 1, 31, tzinfo=timezone.utc)
        )

        fc_dict = d.get("futures_contract_spec")
        fc: FuturesContractSpec | None = None
        if fc_dict and isinstance(fc_dict, dict):
            from src.domain.futures import TradingSession
            sess = fc_dict.get("session") or {}
            fc = FuturesContractSpec(
                symbol=str(fc_dict.get("symbol", "")),
                tick_size=float(fc_dict.get("tick_size", 0.25)),
                point_value=float(fc_dict.get("point_value", 50.0)),
                session=TradingSession(
                    name=str(sess.get("name", "")),
                    start_time=time.fromisoformat(str(sess.get("start_time", "09:30:00"))),
                    end_time=time.fromisoformat(str(sess.get("end_time", "16:00:00"))),
                    timezone=str(sess.get("timezone", "America/New_York")),
                ),
            )
        return cls(
            symbol=str(d.get("symbol", "")),
            start=start,
            end=end,
            timeframe_base=str(d.get("timeframe_base", "1d")),
            data_provider_config=dp_config,
            seed=d.get("seed"),
            initial_cash=float(d.get("initial_cash", 100_000.0)),
            broker=str(d.get("broker", "zero")),
            fill_config=_fill_config_from_dict(d.get("fill_config")),
            instrument_type=str(d.get("instrument_type", "option")),
            futures_contract_spec=fc,
            strategy_name=str(d.get("strategy_name", "")),
            symbols=list(d.get("symbols", []) or []),
            fill_timing=str(d.get("fill_timing", "same_bar_close")),
            option_contract_ids=d.get("option_contract_ids"),
            option_chain_sigma_limit=d["option_chain_sigma_limit"]
            if "option_chain_sigma_limit" in d
            else 2.0,
            option_chain_vol_default=float(d.get("option_chain_vol_default", 0.20)),
            assignment_model=str(d.get("assignment_model", "cash")),
        )
