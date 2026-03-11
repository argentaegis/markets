# Strategizer

Shared strategy package for the markets repo.

This package is imported directly by `backtester/`. The repo's `observer/` app can also expose it through an HTTP wrapper in its own backend, but the strategy package itself is just Python code.

## Install

```bash
pip install -e .
```

## Usage

```python
from strategizer.strategies import STRATEGY_REGISTRY
from strategizer.types import BarInput, Signal

strategy = STRATEGY_REGISTRY["orb_5m"](symbols=["ESH26"])
signals = strategy.evaluate(ts, bars_by_symbol, specs, portfolio, step_index=1, strategy_params={})
```

## Strategies

| Name | Type |
|------|------|
| orb_5m | Opening range breakout (futures) |
| trend_entry_trailing_stop | MA cross + trailing stop |
| trend_follow_risk_sized | Trend-following entry with portfolio-aware risk sizing |
| buy_and_hold | Options entry |
| buy_and_hold_underlying | Equity entry |
| covered_call | Time-based |
