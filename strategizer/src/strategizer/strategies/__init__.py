"""Strategy implementations."""

from strategizer.strategies.buy_and_hold import BuyAndHoldStrategy
from strategizer.strategies.buy_and_hold_underlying import BuyAndHoldUnderlyingStrategy
from strategizer.strategies.covered_call import CoveredCallStrategy
from strategizer.strategies.orb_5m import ORB5mStrategy
from strategizer.strategies.trend_entry_trailing_stop import TrendEntryTrailingStopStrategy
from strategizer.strategies.trend_follow_risk_sized import TrendFollowRiskSizedStrategy
from strategizer.strategies.tactical_asset_allocation import TacticalAssetAllocationStrategy

STRATEGY_REGISTRY = {
    "orb_5m": ORB5mStrategy,
    "buy_and_hold": BuyAndHoldStrategy,
    "buy_and_hold_underlying": BuyAndHoldUnderlyingStrategy,
    "covered_call": CoveredCallStrategy,
    "trend_entry_trailing_stop": TrendEntryTrailingStopStrategy,
    "trend_follow_risk_sized": TrendFollowRiskSizedStrategy,
    "tactical_asset_allocation": TacticalAssetAllocationStrategy,
}

__all__ = [
    "ORB5mStrategy",
    "BuyAndHoldStrategy",
    "BuyAndHoldUnderlyingStrategy",
    "CoveredCallStrategy",
    "TrendEntryTrailingStopStrategy",
    "TrendFollowRiskSizedStrategy",
    "TacticalAssetAllocationStrategy",
    "STRATEGY_REGISTRY",
]
