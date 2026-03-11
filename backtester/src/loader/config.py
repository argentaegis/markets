"""DataProviderConfig — no domain imports. Breaks circular dependency with domain.config."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Literal

MissingDataPolicy = Literal["RAISE", "RETURN_EMPTY", "RETURN_PARTIAL"]


@dataclass
class DataProviderConfig:
    """DataProvider configuration. Serializable for run manifest.

    Reasoning: BacktestConfig embeds this; to_dict enables run_manifest.json.
    missing_data_policy, max_quote_age, default_multiplier control graceful degradation.
    """

    underlying_path: Path | str
    options_path: Path | str
    timeframes_supported: list[str] = field(default_factory=lambda: ["1d", "1h", "1m"])
    storage_backend: Literal["csv", "parquet"] = "parquet"
    missing_data_policy: MissingDataPolicy = "RAISE"
    max_quote_age: timedelta | int | None = 60  # seconds; None = no staleness check (historical)
    default_multiplier: float = 100.0

    def __post_init__(self) -> None:
        self.underlying_path = Path(self.underlying_path)
        self.options_path = Path(self.options_path)

    def get_max_quote_age_seconds(self) -> float | None:
        """Return max age in seconds, or None to disable staleness check (historical backtesting)."""
        if self.max_quote_age is None:
            return None
        if isinstance(self.max_quote_age, timedelta):
            return self.max_quote_age.total_seconds()
        return float(self.max_quote_age)

    def to_dict(self) -> dict:
        age = self.get_max_quote_age_seconds()
        return {
            "underlying_path": str(self.underlying_path),
            "options_path": str(self.options_path),
            "timeframes_supported": self.timeframes_supported,
            "storage_backend": self.storage_backend,
            "missing_data_policy": self.missing_data_policy,
            "max_quote_age": age,
            "default_multiplier": self.default_multiplier,
        }
