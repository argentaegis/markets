"""CoveredCall — hold shares, sell calls; physical assignment at expiry (Plan 267)."""

from __future__ import annotations

from datetime import date, timedelta

from strategizer.base import Strategy
from strategizer.protocol import ContractSpecView, OptionFetchSpec, PortfolioView, Requirements
from strategizer.types import BarInput, Signal


def _parse_expiry_strike(contract_id: str) -> tuple[date, float] | None:
    """Parse contract_id (SYMBOL|YYYY-MM-DD|C|strike|mult), return (expiry, strike) or None."""
    parts = contract_id.split("|")
    if len(parts) != 5:
        return None
    try:
        expiry = date.fromisoformat(parts[1])
        strike = float(parts[3])
        if parts[2].upper() != "C":
            return None
        return (expiry, strike)
    except (ValueError, IndexError):
        return None


def _pick_next_call(
    option_chain: list[str],
    symbol: str,
    bars_by_symbol: dict[str, dict[str, list[BarInput]]],
    ts: date,
    dte_target: int,
    strike_rule: str,
) -> str | None:
    """Pick ATM call with ~dte_target DTE. Returns contract_id or None."""
    spot = 0.0
    timeframe = "1d"
    for tf in ("1d", "1m", "1h"):
        sym_bars = bars_by_symbol.get(symbol, {}).get(tf, [])
        if sym_bars:
            spot = sym_bars[-1].close
            timeframe = tf
            break
    if spot <= 0:
        return None

    if hasattr(ts, "date"):
        ts_date = ts.date()
    elif isinstance(ts, date):
        ts_date = ts
    else:
        ts_date = date.today()

    dte_min = max(1, dte_target - 15)
    dte_max = dte_target + 15
    candidates: list[tuple[str, date, float]] = []

    for cid in option_chain:
        parsed = _parse_expiry_strike(cid)
        if parsed is None:
            continue
        expiry, strike = parsed
        if not cid.startswith(symbol + "|"):
            continue
        dte = (expiry - ts_date).days
        if dte_min <= dte <= dte_max:
            candidates.append((cid, expiry, strike))

    if not candidates:
        return None

    if strike_rule == "atm":
        best = min(candidates, key=lambda x: abs(x[2] - spot))
    else:
        best = min(candidates, key=lambda x: x[1])  # nearest expiry
    return best[0]


class CoveredCallStrategy(Strategy):
    """True covered call: hold shares, sell calls; at expiry sell next call (Plan 267).

    Flow: buy shares, sell call; when call expires (OTM or ITM/assigned), sell next call.
    Engine handles physical assignment when short call is ITM.
    """

    @property
    def name(self) -> str:
        return "covered_call"

    def requirements(self) -> Requirements:
        return Requirements(symbols=[], timeframes=[], lookback=0, needs_quotes=False)

    def option_fetch_spec(
        self,
        ts,
        portfolio: PortfolioView,
        underlying_close: float | None,
        step_index: int,
        strategy_params: dict,
    ) -> OptionFetchSpec | None:
        params = strategy_params or {}
        symbol = str(params.get("symbol", "SPY"))
        positions = portfolio.get_positions()
        short_call_contract: str | None = None
        for pid, pv in positions.items():
            if pid != symbol and pv.qty < 0 and "|" in pid:
                short_call_contract = pid
                break
        if short_call_contract is not None:
            return OptionFetchSpec(contract_ids=[short_call_contract])
        return OptionFetchSpec(sigma_limit=2.0)

    def evaluate(
        self,
        ts,
        bars_by_symbol: dict[str, dict[str, list[BarInput]]],
        specs: dict[str, ContractSpecView],
        portfolio: PortfolioView,
        *,
        step_index: int | None = None,
        strategy_params: dict | None = None,
        option_chain: list[str] | None = None,
    ) -> list[Signal]:
        params = strategy_params or {}
        symbol = str(params.get("symbol", "SPY"))
        shares_per_contract = int(params.get("shares_per_contract", 100))
        strike_rule = str(params.get("strike_rule", "atm"))
        dte_target = int(params.get("dte_target", 30))

        positions = portfolio.get_positions()
        share_qty = 0
        if symbol in positions:
            share_qty = positions[symbol].qty

        short_call_contract: str | None = None
        for pid, pv in positions.items():
            if pid != symbol and pv.qty < 0 and "|" in pid:
                short_call_contract = pid
                break

        if share_qty < shares_per_contract:
            buy_qty = shares_per_contract - share_qty
            return [
                Signal(
                    symbol=symbol,
                    direction="LONG",
                    entry_type="MARKET",
                    entry_price=0.0,
                    stop_price=0.0,
                    targets=[],
                    qty=buy_qty,
                    instrument_id=None,
                )
            ]

        if share_qty >= shares_per_contract and short_call_contract is None:
            if option_chain:
                contract_id = _pick_next_call(
                    option_chain, symbol, bars_by_symbol, ts, dte_target, strike_rule
                )
                if contract_id:
                    return [
                        Signal(
                            symbol="",
                            direction="SHORT",
                            entry_type="MARKET",
                            entry_price=0.0,
                            stop_price=0.0,
                            targets=[],
                            qty=1,
                            instrument_id=contract_id,
                        )
                    ]
            contract_id = params.get("contract_id")
            if contract_id:
                return [
                    Signal(
                        symbol="",
                        direction="SHORT",
                        entry_type="MARKET",
                        entry_price=0.0,
                        stop_price=0.0,
                        targets=[],
                        qty=1,
                        instrument_id=contract_id,
                    )
                ]

        return []
