"""SchwabProvider — live futures data via Schwab's official REST API.

Architecture: connect() validates credentials and fetches initial data.
subscribe_quotes() and subscribe_bars() poll the REST API at configurable
intervals, yielding canonical Quote and Bar types. Token refresh is handled
automatically when the access token expires.

Uses httpx for HTTP requests — no third-party Schwab client libraries.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

import httpx

from core.instrument import ContractSpec, InstrumentType, TradingSession
from core.market_data import Bar, DataQuality, Quote
from providers.base import BaseProvider, ProviderHealth
from providers.schwab_mapper import (
    canonical_to_schwab,
    map_security_status,
    schwab_to_canonical,
)

logger = logging.getLogger(__name__)

_API_BASE = "https://api.schwabapi.com"
_TOKEN_URL = f"{_API_BASE}/v1/oauth/token"
_QUOTES_URL = f"{_API_BASE}/marketdata/v1/quotes"
_PRICE_HISTORY_URL = f"{_API_BASE}/marketdata/v1/pricehistory"

_TIMEFRAME_TO_FREQUENCY = {
    "1m": 1,
    "5m": 5,
    "10m": 10,
    "15m": 15,
    "30m": 30,
}

_ES_RTH = TradingSession(
    name="ES_RTH", start_time=datetime.strptime("09:30", "%H:%M").time(),
    end_time=datetime.strptime("16:00", "%H:%M").time(), timezone="US/Eastern",
)
_NQ_RTH = TradingSession(
    name="NQ_RTH", start_time=datetime.strptime("09:30", "%H:%M").time(),
    end_time=datetime.strptime("16:00", "%H:%M").time(), timezone="US/Eastern",
)

_KNOWN_SPECS: dict[str, ContractSpec] = {
    "ESH26": ContractSpec(
        symbol="ESH26", instrument_type=InstrumentType.FUTURE,
        tick_size=0.25, point_value=50.0, session=_ES_RTH,
    ),
    "NQH26": ContractSpec(
        symbol="NQH26", instrument_type=InstrumentType.FUTURE,
        tick_size=0.25, point_value=20.0, session=_NQ_RTH,
    ),
}


class SchwabProvider(BaseProvider):
    """Live futures data from Schwab via official REST API polling.

    Polls /marketdata/v1/quotes for quotes and /marketdata/v1/pricehistory
    for bars at configurable intervals. Handles OAuth token refresh
    automatically using the refresh_token from the token file.
    """

    def __init__(
        self,
        api_key: str,
        app_secret: str,
        token_path: str,
        symbols: list[str] | None = None,
        quote_poll_seconds: float = 5.0,
        bar_poll_seconds: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._app_secret = app_secret
        self._token_path = token_path
        self._symbols = symbols or ["ESH26", "NQH26"]
        self._quote_poll_seconds = quote_poll_seconds
        self._bar_poll_seconds = bar_poll_seconds

        self._connected = False
        self._last_heartbeat: datetime | None = None
        self._client: httpx.AsyncClient | None = None

        self._access_token: str = ""
        self._refresh_token: str = ""
        self._token_expires_at: float = 0.0

        self._specs: dict[str, ContractSpec] = {
            s: _KNOWN_SPECS[s] for s in self._symbols if s in _KNOWN_SPECS
        }

        self._last_bar_timestamps: dict[str, datetime] = {}

    async def connect(self) -> None:
        self._load_token_file()
        await self._ensure_valid_token()
        self._client = httpx.AsyncClient(timeout=15.0)

        schwab_symbols = [canonical_to_schwab(s) for s in self._symbols]
        r = await self._client.get(
            _QUOTES_URL,
            params={"symbols": ",".join(schwab_symbols)},
            headers=self._auth_headers(),
        )
        if r.status_code != 200:
            raise ConnectionError(
                f"Schwab API connection test failed: {r.status_code} {r.text[:200]}"
            )

        self._connected = True
        self._last_heartbeat = datetime.now(timezone.utc)
        logger.info("SchwabProvider connected (REST polling), symbols: %s", self._symbols)

    async def disconnect(self) -> None:
        self._connected = False
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        logger.info("SchwabProvider disconnected")

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            connected=self._connected,
            source="schwab",
            last_heartbeat=self._last_heartbeat,
            message="OK" if self._connected else "Disconnected",
        )

    def get_contract_specs(self) -> dict[str, ContractSpec]:
        return dict(self._specs)

    async def subscribe_quotes(self, symbols: list[str]) -> AsyncIterator[Quote]:
        assert self._client is not None
        schwab_symbols = [canonical_to_schwab(s) for s in symbols]
        symbol_str = ",".join(schwab_symbols)

        while self._connected:
            try:
                await self._ensure_valid_token()
                r = await self._client.get(
                    _QUOTES_URL,
                    params={"symbols": symbol_str},
                    headers=self._auth_headers(),
                )
                if r.status_code == 200:
                    self._last_heartbeat = datetime.now(timezone.utc)
                    for schwab_sym, info in r.json().items():
                        quote = self._parse_quote(schwab_sym, info)
                        if quote is not None:
                            yield quote
                else:
                    logger.warning("Quote poll failed: %d %s", r.status_code, r.text[:100])
            except httpx.HTTPError:
                logger.exception("Quote poll HTTP error")
            except Exception:
                logger.exception("Quote poll error")

            await asyncio.sleep(self._quote_poll_seconds)

    async def subscribe_bars(
        self, symbols: list[str], timeframe: str,
    ) -> AsyncIterator[Bar]:
        assert self._client is not None
        frequency = _TIMEFRAME_TO_FREQUENCY.get(timeframe)
        if frequency is None:
            raise ValueError(f"Unsupported timeframe: {timeframe!r}")

        while self._connected:
            try:
                await self._ensure_valid_token()
                for symbol in symbols:
                    schwab_sym = canonical_to_schwab(symbol)
                    r = await self._client.get(
                        _PRICE_HISTORY_URL,
                        params={
                            "symbol": schwab_sym,
                            "periodType": "day",
                            "period": 1,
                            "frequencyType": "minute",
                            "frequency": frequency,
                        },
                        headers=self._auth_headers(),
                    )
                    if r.status_code == 200:
                        self._last_heartbeat = datetime.now(timezone.utc)
                        for bar in self._parse_bars(symbol, timeframe, r.json()):
                            yield bar
                    else:
                        logger.warning(
                            "Bar poll failed for %s: %d %s",
                            symbol, r.status_code, r.text[:100],
                        )
            except httpx.HTTPError:
                logger.exception("Bar poll HTTP error")
            except Exception:
                logger.exception("Bar poll error")

            await asyncio.sleep(self._bar_poll_seconds)

    # -- Token management ---------------------------------------------------

    def _load_token_file(self) -> None:
        path = Path(self._token_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Token file not found: {self._token_path}. "
                "Run the OAuth flow first to generate a token."
            )
        with open(path) as f:
            data = json.load(f)

        token = data.get("token", data)
        self._access_token = token["access_token"]
        self._refresh_token = token["refresh_token"]
        creation = data.get("creation_timestamp", 0)
        expires_in = token.get("expires_in", 1800)
        self._token_expires_at = creation + expires_in

    def _save_token_file(self) -> None:
        data = {
            "creation_timestamp": int(time.time()),
            "token": {
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "expires_in": 1800,
                "token_type": "Bearer",
                "scope": "api",
            },
        }
        with open(self._token_path, "w") as f:
            json.dump(data, f, indent=2)

    async def _ensure_valid_token(self) -> None:
        if time.time() < self._token_expires_at - 60:
            return
        logger.info("Access token expired or expiring, refreshing...")
        await self._refresh_access_token()

    async def _refresh_access_token(self) -> None:
        creds = base64.b64encode(
            f"{self._api_key}:{self._app_secret}".encode(),
        ).decode()
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                _TOKEN_URL,
                headers={
                    "Authorization": f"Basic {creds}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                },
            )
        if r.status_code != 200:
            logger.error("Token refresh failed: %d %s", r.status_code, r.text[:200])
            self._connected = False
            raise ConnectionError(f"Token refresh failed: {r.status_code}")

        token = r.json()
        self._access_token = token["access_token"]
        self._refresh_token = token.get("refresh_token", self._refresh_token)
        self._token_expires_at = time.time() + token.get("expires_in", 1800)
        self._save_token_file()
        logger.info("Token refreshed successfully")

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    # -- Response parsing ---------------------------------------------------

    def _parse_quote(self, schwab_sym: str, info: dict) -> Quote | None:
        try:
            q = info.get("quote", {})
            ref = info.get("reference", {})

            active_symbol = q.get("futureActiveSymbol", schwab_sym)
            try:
                fs = schwab_to_canonical(active_symbol)
            except ValueError:
                fs = schwab_to_canonical(schwab_sym)
            canonical_sym = fs.to_symbol()

            ts_millis = q.get("quoteTime", 0)
            timestamp = (
                datetime.fromtimestamp(ts_millis / 1000, tz=timezone.utc)
                if ts_millis
                else datetime.now(timezone.utc)
            )

            security_status = q.get("securityStatus")
            quality = map_security_status(security_status)

            return Quote(
                symbol=canonical_sym,
                bid=float(q.get("bidPrice", 0)),
                ask=float(q.get("askPrice", 0)),
                last=float(q.get("lastPrice", 0)),
                bid_size=int(q.get("bidSize", 0)),
                ask_size=int(q.get("askSize", 0)),
                volume=int(q.get("totalVolume", 0)),
                timestamp=timestamp,
                source="schwab",
                quality=quality,
            )
        except Exception:
            logger.exception("Failed to parse quote for %s", schwab_sym)
            return None

    def _parse_bars(
        self, symbol: str, timeframe: str, data: dict,
    ) -> list[Bar]:
        candles = data.get("candles", [])
        last_ts = self._last_bar_timestamps.get(symbol)
        new_bars: list[Bar] = []

        for candle in candles:
            ts_millis = candle.get("datetime", 0)
            timestamp = datetime.fromtimestamp(ts_millis / 1000, tz=timezone.utc)

            if last_ts is not None and timestamp <= last_ts:
                continue

            new_bars.append(Bar(
                symbol=symbol,
                timeframe=timeframe,
                open=float(candle.get("open", 0)),
                high=float(candle.get("high", 0)),
                low=float(candle.get("low", 0)),
                close=float(candle.get("close", 0)),
                volume=int(candle.get("volume", 0)),
                timestamp=timestamp,
                source="schwab",
                quality=DataQuality.OK,
            ))

        if new_bars:
            self._last_bar_timestamps[symbol] = new_bars[-1].timestamp

        return new_bars
