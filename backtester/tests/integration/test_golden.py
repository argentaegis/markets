"""Golden tests — deterministic end-to-end runs compared against frozen expected output.

Reasoning: any future change that alters backtest behavior breaks these tests,
surfacing regressions. Golden files in tests/golden/ are version-controlled.
Use --update-golden to regenerate when intentional changes are made.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.broker.fee_model import FeeModelConfig
from src.domain.config import BacktestConfig
from src.engine.engine import run_backtest
from src.engine.result import BacktestResult
from src.loader.provider import DataProviderConfig, LocalFileDataProvider
from src.reporter.reporter import generate_report
from src.reporter.summary import compute_summary
from src.reporter.trades import derive_trades
from src.strategies.strategizer_adapter import StrategizerStrategy


GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden"
FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "src" / "loader" / "tests" / "fixtures"
CONTRACT = "SPY|2026-01-17|C|480|100"


def _utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=timezone.utc)


def _engine_config(
    provider_config: DataProviderConfig,
    fee_config: FeeModelConfig | None = None,
) -> BacktestConfig:
    return BacktestConfig(
        symbol="SPY",
        start=_utc(14, 31),
        end=_utc(14, 35),
        timeframe_base="1m",
        data_provider_config=provider_config,
        initial_cash=100_000.0,
        fee_config=fee_config,
    )


def _load_golden_json(name: str) -> dict:
    """Load a golden JSON file."""
    path = GOLDEN_DIR / name
    assert path.exists(), f"Golden file missing: {path}. Run: python tests/golden/generate_golden.py"
    return json.loads(path.read_text())


def _load_golden_csv(name: str) -> list[dict]:
    """Load a golden CSV file as list of dicts."""
    path = GOLDEN_DIR / name
    assert path.exists(), f"Golden file missing: {path}. Run: python tests/golden/generate_golden.py"
    with open(path) as f:
        return list(csv.DictReader(f))


def _maybe_update_golden(request: pytest.FixtureRequest, result: BacktestResult, prefix: str) -> None:
    """If --update-golden is set, regenerate golden files from this run."""
    if not request.config.getoption("--update-golden"):
        return
    summary = compute_summary(result)
    with open(GOLDEN_DIR / f"expected_{prefix}_summary.json", "w") as f:
        json.dump(summary.to_dict(), f, indent=2)
        f.write("\n")
    if prefix == "buy_and_hold":
        with open(GOLDEN_DIR / f"expected_{prefix}_equity.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ts", "equity"])
            for ep in result.equity_curve:
                writer.writerow([ep.ts.isoformat(), ep.equity])
    if prefix == "covered_call":
        trades = derive_trades(result.fills, result.orders)
        with open(GOLDEN_DIR / f"expected_{prefix}_trades.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["instrument_id", "side", "qty", "entry_price", "exit_price", "realized_pnl", "fees"])
            for t in trades:
                writer.writerow([t.instrument_id, t.side, t.qty, t.entry_price, t.exit_price, t.realized_pnl, t.fees])


# ---------------------------------------------------------------------------
# Test 1: BuyAndHold summary matches golden
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_golden_buy_and_hold_summary(
    request: pytest.FixtureRequest,
    provider_config: DataProviderConfig,
    strategizer_required: None,
) -> None:
    """BuyAndHoldStrategy summary matches golden values."""
    cfg = _engine_config(provider_config)
    provider = LocalFileDataProvider(provider_config)
    strategy = StrategizerStrategy("buy_and_hold", {"contract_id": CONTRACT}, config=cfg)
    result = run_backtest(cfg, strategy, provider)
    _maybe_update_golden(request, result, "buy_and_hold")

    expected = _load_golden_json("expected_buy_and_hold_summary.json")
    actual = compute_summary(result).to_dict()

    assert actual["initial_cash"] == expected["initial_cash"]
    assert actual["final_equity"] == pytest.approx(expected["final_equity"], abs=0.01)
    assert actual["num_trades"] == expected["num_trades"]
    assert actual["total_fees"] == pytest.approx(expected["total_fees"], abs=0.01)
    assert actual["num_steps"] == expected["num_steps"]


# ---------------------------------------------------------------------------
# Test 2: CoveredCall summary matches golden
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_golden_covered_call_summary(
    request: pytest.FixtureRequest,
    provider_config: DataProviderConfig,
    strategizer_required: None,
) -> None:
    """CoveredCallStrategy summary matches golden values."""
    cfg = _engine_config(provider_config)
    provider = LocalFileDataProvider(provider_config)
    strategy = StrategizerStrategy("covered_call", {"contract_id": CONTRACT, "exit_step": 3}, config=cfg)
    result = run_backtest(cfg, strategy, provider)
    _maybe_update_golden(request, result, "covered_call")

    expected = _load_golden_json("expected_covered_call_summary.json")
    actual = compute_summary(result).to_dict()

    assert actual["num_trades"] == expected["num_trades"]
    assert actual["realized_pnl"] == pytest.approx(expected["realized_pnl"], abs=0.01)
    assert actual["total_return_pct"] == pytest.approx(expected["total_return_pct"], abs=1e-8)
    assert actual["final_equity"] == pytest.approx(expected["final_equity"], abs=0.01)


# ---------------------------------------------------------------------------
# Test 3: CoveredCall trades match golden
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_golden_covered_call_trades(
    provider_config: DataProviderConfig,
    strategizer_required: None,
) -> None:
    """CoveredCallStrategy trades.csv matches golden: 1 row, correct prices."""
    cfg = _engine_config(provider_config)
    provider = LocalFileDataProvider(provider_config)
    strategy = StrategizerStrategy("covered_call", {"contract_id": CONTRACT, "exit_step": 3}, config=cfg)
    result = run_backtest(cfg, strategy, provider)
    trades = derive_trades(result.fills, result.orders)

    expected_rows = _load_golden_csv("expected_covered_call_trades.csv")
    assert len(trades) == len(expected_rows)

    t = trades[0]
    e = expected_rows[0]
    assert t.side == e["side"]
    assert t.entry_price == pytest.approx(float(e["entry_price"]), abs=0.01)
    assert t.exit_price == pytest.approx(float(e["exit_price"]), abs=0.01)
    assert t.realized_pnl == pytest.approx(float(e["realized_pnl"]), abs=0.01)


# ---------------------------------------------------------------------------
# Test 4: Determinism — two identical runs produce identical output
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_golden_determinism(
    provider_config: DataProviderConfig,
    tmp_path: Path,
    strategizer_required: None,
) -> None:
    """Two identical CoveredCallStrategy runs produce byte-identical CSV/JSON (A5)."""
    cfg = _engine_config(provider_config)

    strategy = StrategizerStrategy("covered_call", {"contract_id": CONTRACT, "exit_step": 3}, config=cfg)
    p1 = LocalFileDataProvider(provider_config)
    r1 = run_backtest(cfg, strategy, p1)
    dir1 = generate_report(r1, tmp_path / "run1")

    p2 = LocalFileDataProvider(provider_config)
    r2 = run_backtest(cfg, strategy, p2)
    dir2 = generate_report(r2, tmp_path / "run2")

    for name in ["equity_curve.csv", "orders.csv", "fills.csv", "trades.csv"]:
        c1 = (dir1 / name).read_text()
        c2 = (dir2 / name).read_text()
        assert c1 == c2, f"{name} differs between runs"

    s1 = json.loads((dir1 / "summary.json").read_text())
    s2 = json.loads((dir2 / "summary.json").read_text())
    assert s1 == s2


# ---------------------------------------------------------------------------
# Test 5: BuyAndHold equity curve matches golden values
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_golden_equity_curve_values(
    provider_config: DataProviderConfig,
    strategizer_required: None,
) -> None:
    """BuyAndHoldStrategy equity curve values match golden within tolerance."""
    cfg = _engine_config(provider_config)
    provider = LocalFileDataProvider(provider_config)
    strategy = StrategizerStrategy("buy_and_hold", {"contract_id": CONTRACT}, config=cfg)
    result = run_backtest(cfg, strategy, provider)

    expected_rows = _load_golden_csv("expected_buy_and_hold_equity.csv")
    assert len(result.equity_curve) == len(expected_rows)

    for ep, row in zip(result.equity_curve, expected_rows):
        assert ep.equity == pytest.approx(float(row["equity"]), abs=0.01)
        assert ep.ts.isoformat() == row["ts"]


# ---------------------------------------------------------------------------
# Test 6: Invariants hold for both strategies
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_golden_invariants_hold(
    provider_config: DataProviderConfig,
    strategizer_required: None,
) -> None:
    """Both strategies: no NaN, fills reference valid orders, equity consistent."""
    cfg = _engine_config(provider_config)

    for name, params in [
            ("buy_and_hold", {"contract_id": CONTRACT}),
        ("covered_call", {"contract_id": CONTRACT, "exit_step": 3}),
    ]:
        strategy = StrategizerStrategy(name, params, config=cfg)
        provider = LocalFileDataProvider(provider_config)
        result = run_backtest(cfg, strategy, provider)

        # No NaN in equity
        for ep in result.equity_curve:
            assert ep.equity == ep.equity, "NaN in equity curve"

        # All fills reference valid orders
        order_ids = {o.id for o in result.orders}
        for fill in result.fills:
            assert fill.order_id in order_ids

        # Final portfolio equity consistent
        p = result.final_portfolio
        assert p is not None
        assert p.equity == p.equity  # not NaN
        for pos in p.positions.values():
            assert isinstance(pos.qty, int)


# ---------------------------------------------------------------------------
# Test 7: CoveredCall with fees matches golden
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_golden_with_fees(
    request: pytest.FixtureRequest,
    provider_config: DataProviderConfig,
    strategizer_required: None,
) -> None:
    """CoveredCallStrategy + FeeModelConfig: fees match golden, reduce P&L."""
    fee_cfg = FeeModelConfig(per_contract=0.65, per_order=0.50)
    cfg = _engine_config(provider_config, fee_config=fee_cfg)
    provider = LocalFileDataProvider(provider_config)
    strategy = StrategizerStrategy("covered_call", {"contract_id": CONTRACT, "exit_step": 3}, config=cfg)
    result = run_backtest(cfg, strategy, provider)
    _maybe_update_golden(request, result, "covered_call_fees")

    expected = _load_golden_json("expected_covered_call_fees_summary.json")
    actual = compute_summary(result).to_dict()

    assert actual["total_fees"] == pytest.approx(expected["total_fees"], abs=0.01)
    assert actual["total_fees"] > 0
    assert actual["final_equity"] == pytest.approx(expected["final_equity"], abs=0.01)

    # Fees version has lower equity than no-fees version
    no_fee_expected = _load_golden_json("expected_covered_call_summary.json")
    assert actual["final_equity"] < no_fee_expected["final_equity"]


# ---------------------------------------------------------------------------
# Test 8: ORB futures golden (120)
# ---------------------------------------------------------------------------
# Fixture: ESH1_1m.parquet with 6 bars — OR = first 5 bars (9:31–9:35 ET), LONG breakout at 9:36 ET.
# Expects 1 order, 1 fill, tick-aligned fill price, deterministic equity.


def _golden_orb_provider_config() -> DataProviderConfig:
    """DataProviderConfig for ORB golden test."""
    return DataProviderConfig(
        underlying_path=FIXTURES_ROOT / "underlying",
        options_path=FIXTURES_ROOT / "options",
        timeframes_supported=["1d", "1h", "1m"],
        missing_data_policy="RETURN_PARTIAL",
        max_quote_age=None,
    )


def _golden_orb_config() -> BacktestConfig:
    """BacktestConfig for ORB golden: ESH1 1m, futures, 500k cash."""
    from datetime import time

    from src.domain.futures import FuturesContractSpec, TradingSession

    session = TradingSession("RTH", time(9, 30), time(16, 0), "America/New_York")
    fc = FuturesContractSpec(symbol="ESH1", tick_size=0.25, point_value=50.0, session=session)
    dp = _golden_orb_provider_config()
    return BacktestConfig(
        symbol="ESH1",
        start=datetime(2026, 1, 2, 14, 31, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, 14, 37, tzinfo=timezone.utc),
        timeframe_base="1m",
        data_provider_config=dp,
        initial_cash=500_000.0,
        instrument_type="future",
        futures_contract_spec=fc,
    )


@pytest.mark.integration
def test_orb_futures_golden() -> None:
    """ORB 1m: fixture produces 1 fill at 5410.25, tick-aligned, deterministic equity."""
    config = _golden_orb_config()
    provider = LocalFileDataProvider(config.data_provider_config)
    strategy = StrategizerStrategy(
        "orb_5m",
        {"qty": 1, "min_range_ticks": 4, "max_range_ticks": 40},
        config=config,
    )
    result = run_backtest(config, strategy, provider)

    assert len(result.fills) == 1
    assert len(result.orders) >= 1
    for fill in result.fills:
        assert (fill.fill_price * 4) % 1 == 0, f"Fill price {fill.fill_price} not ES tick-aligned"
    assert result.fills[0].fill_price == 5410.25  # OR high + 1 tick
    assert result.equity_curve[-1].equity == pytest.approx(500_087.5, rel=1e-6)


@pytest.mark.integration
def test_orb_futures_golden_reproducibility() -> None:
    """Two identical ORB runs produce identical equity and fills (120)."""
    config = _golden_orb_config()
    strategy = StrategizerStrategy("orb_5m", {"qty": 1}, config=config)
    p1 = LocalFileDataProvider(config.data_provider_config)
    r1 = run_backtest(config, strategy, p1)
    p2 = LocalFileDataProvider(config.data_provider_config)
    r2 = run_backtest(config, strategy, p2)

    assert len(r1.equity_curve) == len(r2.equity_curve)
    for ep1, ep2 in zip(r1.equity_curve, r2.equity_curve):
        assert ep1.equity == ep2.equity
        assert ep1.ts == ep2.ts
    assert len(r1.fills) == len(r2.fills)
    for f1, f2 in zip(r1.fills, r2.fills):
        assert f1.fill_price == f2.fill_price
        assert f1.fill_qty == f2.fill_qty
