"""StrategizerStrategy — runs strategizer strategies in-process (no HTTP)."""

from __future__ import annotations

from datetime import time

from strategizer.strategies import STRATEGY_REGISTRY
from strategizer.types import BarInput, PositionView, Signal

from src.domain.bars import BarRow
from src.domain.config import BacktestConfig
from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.snapshot import MarketSnapshot
from src.engine.strategy import Strategy


def _bar_row_to_bar_input(row: BarRow) -> BarInput:
    return BarInput(
        ts=row.ts,
        open=row.open,
        high=row.high,
        low=row.low,
        close=row.close,
        volume=row.volume,
    )


class _BacktesterPortfolioView:
    """Adapts PortfolioState to strategizer PortfolioView."""

    def __init__(self, state: PortfolioState) -> None:
        self._state = state

    def get_positions(self) -> dict[str, PositionView]:
        return {
            pid: PositionView(
                instrument_id=p.instrument_id,
                qty=p.qty,
                avg_price=p.avg_price,
            )
            for pid, p in self._state.positions.items()
        }

    def get_cash(self) -> float:
        return self._state.cash

    def get_equity(self) -> float:
        return self._state.equity


class _MinimalSpec:
    """Default spec for equity when no futures_contract_spec."""

    tick_size = 0.01
    point_value = 1.0
    timezone = "America/New_York"
    start_time = time(9, 30, 0)
    end_time = time(16, 0, 0)


def _signal_to_order(signal: Signal, ts, config: BacktestConfig) -> Order:
    direction = signal.direction
    side = "BUY" if direction == "LONG" else "SELL"
    entry_type = signal.entry_type
    ot_map = {"MARKET": "market", "LIMIT": "limit", "STOP": "stop"}
    order_type = ot_map.get(entry_type, "market")
    entry_price = signal.entry_price
    limit_price = entry_price if order_type in ("limit", "stop") else None

    instrument_id = signal.instrument_id or signal.symbol or config.symbol
    qty = signal.qty
    oid = f"strat-{instrument_id}-{direction}-{ts.isoformat()}"
    trailing_stop_ticks = signal.trailing_stop_ticks

    return Order(
        id=oid,
        ts=ts,
        instrument_id=instrument_id,
        side=side,
        qty=qty,
        order_type=order_type,
        limit_price=limit_price,
        tif="GTC",
        trailing_stop_ticks=trailing_stop_ticks,
    )


class StrategizerStrategy(Strategy):
    """Strategy that runs strategizer in-process. No HTTP."""

    def __init__(
        self,
        strategy_name: str,
        strategy_params: dict,
        config: BacktestConfig,
    ) -> None:
        self._strategy_name = strategy_name
        self._strategy_params = dict(strategy_params)
        self._config = config

        # Merge symbol/symbols and timeframe from config
        if "symbols" not in self._strategy_params and "symbol" not in self._strategy_params:
            self._strategy_params["symbols"] = [config.symbol]
        if "symbol" not in self._strategy_params and strategy_name == "buy_and_hold_underlying":
            self._strategy_params["symbol"] = config.symbol
        if "timeframe" not in self._strategy_params:
            self._strategy_params["timeframe"] = config.timeframe_base

        cls = STRATEGY_REGISTRY.get(strategy_name)
        if cls is None:
            raise ValueError(f"Unknown strategizer strategy: {strategy_name}")

        init_kwargs: dict = {}
        if strategy_name == "orb_5m":
            init_kwargs = {
                "symbols": [config.symbol],
                "min_range_ticks": self._strategy_params.get("min_range_ticks", 4),
                "max_range_ticks": self._strategy_params.get("max_range_ticks", 40),
                "qty": self._strategy_params.get("qty", 1),
            }
        elif strategy_name == "trend_entry_trailing_stop":
            init_kwargs = {
                "symbols": [config.symbol],
                "ma_period": self._strategy_params.get("ma_period", 125),
                "trailing_stop_ticks": self._strategy_params.get("trailing_stop_ticks", 50),
                "qty": self._strategy_params.get("qty", 1),
                "direction": self._strategy_params.get("direction", "LONG"),
                "timeframe": config.timeframe_base,
            }
        elif strategy_name == "trend_follow_risk_sized":
            init_kwargs = {
                "symbols": [config.symbol],
                "ma_period": self._strategy_params.get("ma_period", 20),
                "trailing_stop_ticks": self._strategy_params.get("trailing_stop_ticks", 10),
                "direction": self._strategy_params.get("direction", "LONG"),
                "timeframe": config.timeframe_base,
                "risk_pct": self._strategy_params.get("risk_pct", 0.01),
                "max_qty": self._strategy_params.get("max_qty", 10),
            }
        self._strategy = cls(**init_kwargs)

    def on_step(
        self,
        snapshot: MarketSnapshot,
        state_view: PortfolioState,
        step_index: int = 1,
    ) -> list[Order]:
        if not self._config:
            return []

        symbol = self._config.symbol
        timeframe = self._config.timeframe_base

        # Build bars_by_symbol from futures_bars or underlying_bar
        lookback = 500
        req = getattr(self._strategy, "requirements", None)
        if req is not None:
            lookback = req().lookback

        bars_by_symbol: dict[str, dict[str, list[BarInput]]] = {}
        bar_list: list[BarRow] = []
        if self._config.instrument_type == "future" and snapshot.futures_bars:
            bar_list = list(snapshot.futures_bars)[-lookback:]
        elif snapshot.underlying_bar:
            bar_list = [snapshot.underlying_bar]

        bars_by_symbol[symbol] = {timeframe: [_bar_row_to_bar_input(b) for b in bar_list]}

        # Build specs: futures_contract_spec or minimal for equity
        specs: dict = {}
        if self._config.futures_contract_spec:
            specs[symbol] = self._config.futures_contract_spec
        else:
            specs[symbol] = _MinimalSpec()

        portfolio = _BacktesterPortfolioView(state_view)

        signals = self._strategy.evaluate(
            ts=snapshot.ts,
            bars_by_symbol=bars_by_symbol,
            specs=specs,
            portfolio=portfolio,
            step_index=step_index,
            strategy_params=self._strategy_params,
        )

        return [_signal_to_order(s, snapshot.ts, self._config) for s in signals]
