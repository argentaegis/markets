"""FastAPI app factory — lifespan, CORS, routers."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

_env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(_env_path)

from api.ws_handler import ConnectionManager
from api.wiring import consume_bars, consume_quotes
from config import load_config
from core.portfolio import create_mock_portfolio
from engine.engine import Engine
from providers.base import BaseProvider
from providers.sim_provider import SimProvider
from state.market_state import MarketState
from state.persistence import StateStore
from strategies.registry import StrategyRegistry

logger = logging.getLogger(__name__)


def _create_provider() -> BaseProvider:
    """Instantiate provider based on OBSERVER_PROVIDER env var."""
    provider_name = os.environ.get("OBSERVER_PROVIDER", "sim").lower()
    if provider_name == "schwab":
        from providers.schwab_provider import SchwabProvider

        api_key = os.environ.get("SCHWAB_API_KEY", "")
        app_secret = os.environ.get("SCHWAB_APP_SECRET", "")
        token_path = os.environ.get("SCHWAB_TOKEN_PATH", "./schwab_token.json")

        if not api_key or not app_secret:
            raise ValueError(
                "SCHWAB_API_KEY and SCHWAB_APP_SECRET must be set when OBSERVER_PROVIDER=schwab"
            )

        return SchwabProvider(
            api_key=api_key,
            app_secret=app_secret,
            token_path=token_path,
        )

    logger.info("Using SimProvider (OBSERVER_PROVIDER=%s)", provider_name)
    return SimProvider(seed=42)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    db_path = os.environ.get("OBSERVER_DB_PATH")
    store = StateStore(db_path=db_path)
    if store.enabled:
        logger.info("State persistence enabled: %s", db_path)
    else:
        logger.info("State persistence disabled (set OBSERVER_DB_PATH to enable)")

    app_config = load_config()
    logger.info("Loaded config: %d strategies configured", len(app_config.strategies))

    provider = _create_provider()
    await provider.connect()
    specs = provider.get_contract_specs()

    registry = StrategyRegistry()
    strategies = registry.instantiate(app_config)
    logger.info("Enabled strategies: %s", [s.name for s in strategies])

    state = MarketState(specs=specs)
    engine = Engine(
        strategies=strategies,
        state=state,
        config=app_config.engine,
        portfolio=create_mock_portfolio(),
    )
    ws_manager = ConnectionManager()

    symbols = list(specs.keys())
    timeframe = engine._config.eval_timeframe

    quote_task = asyncio.create_task(
        consume_quotes(provider, symbols, state, ws_manager, store=store)
    )
    bar_task = asyncio.create_task(
        consume_bars(provider, symbols, timeframe, engine, ws_manager, store=store)
    )

    app.state.provider = provider
    app.state.market_state = state
    app.state.engine = engine
    app.state.ws_manager = ws_manager
    app.state.store = store

    yield

    quote_task.cancel()
    bar_task.cancel()
    await provider.disconnect()


def create_app() -> FastAPI:
    app = FastAPI(title="Observer", lifespan=_lifespan)

    frontend_port = os.environ.get("FRONTEND_PORT", "5173")
    allowed_origins = os.environ.get(
        "CORS_ORIGINS", f"http://localhost:{frontend_port}"
    ).split(",")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from api.backtester import router as backtester_router
    from api.health import router as health_router
    from api.snapshot import router as snapshot_router
    from api.ws_handler import router as ws_router

    app.include_router(backtester_router)
    app.include_router(snapshot_router)
    app.include_router(health_router)
    app.include_router(ws_router)

    # Serve backtest artifacts for report links
    _repo_root = Path(__file__).resolve().parents[4]
    _runs_dir = _repo_root / "runs"
    if _runs_dir.exists():
        app.mount("/runs", StaticFiles(directory=str(_runs_dir)), name="runs")

    return app
