"""StateStore — optional SQLite persistence for quotes and bars.

When db_path is None, all methods are no-ops. The system works
identically with or without persistence enabled.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from core.market_data import Bar, DataQuality, Quote

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS quotes (
    symbol     TEXT    NOT NULL,
    bid        REAL    NOT NULL,
    ask        REAL    NOT NULL,
    last       REAL    NOT NULL,
    bid_size   INTEGER NOT NULL,
    ask_size   INTEGER NOT NULL,
    volume     INTEGER NOT NULL,
    timestamp  TEXT    NOT NULL,
    source     TEXT    NOT NULL,
    quality    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS bars (
    symbol     TEXT    NOT NULL,
    timeframe  TEXT    NOT NULL,
    open       REAL    NOT NULL,
    high       REAL    NOT NULL,
    low        REAL    NOT NULL,
    close      REAL    NOT NULL,
    volume     INTEGER NOT NULL,
    timestamp  TEXT    NOT NULL,
    source     TEXT    NOT NULL,
    quality    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_quotes_symbol_ts ON quotes (symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_bars_symbol_ts ON bars (symbol, timestamp);
"""


def _dt_to_str(dt: datetime) -> str:
    return dt.isoformat()


def _str_to_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class StateStore:
    """Optional SQLite persistence for quotes and bars.

    When db_path is None, all methods are no-ops (disabled by default).
    Candidate persistence is NOT handled here — that belongs to the
    Journal in step 130.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        if db_path is not None:
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.executescript(_SCHEMA)

    @property
    def enabled(self) -> bool:
        return self._conn is not None

    def save_quote(self, quote: Quote) -> None:
        if not self.enabled:
            return
        assert self._conn is not None
        self._conn.execute(
            "INSERT INTO quotes (symbol, bid, ask, last, bid_size, ask_size, volume, timestamp, source, quality) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                quote.symbol,
                quote.bid,
                quote.ask,
                quote.last,
                quote.bid_size,
                quote.ask_size,
                quote.volume,
                _dt_to_str(quote.timestamp),
                quote.source,
                quote.quality.value,
            ),
        )
        self._conn.commit()

    def save_bar(self, bar: Bar) -> None:
        if not self.enabled:
            return
        assert self._conn is not None
        self._conn.execute(
            "INSERT INTO bars (symbol, timeframe, open, high, low, close, volume, timestamp, source, quality) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                bar.symbol,
                bar.timeframe,
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
                _dt_to_str(bar.timestamp),
                bar.source,
                bar.quality.value,
            ),
        )
        self._conn.commit()

    def get_quotes(
        self, symbol: str, since: datetime | None = None
    ) -> list[Quote]:
        if not self.enabled:
            return []
        assert self._conn is not None
        if since is not None:
            cursor = self._conn.execute(
                "SELECT symbol, bid, ask, last, bid_size, ask_size, volume, timestamp, source, quality "
                "FROM quotes WHERE symbol = ? AND timestamp >= ? ORDER BY timestamp",
                (symbol, _dt_to_str(since)),
            )
        else:
            cursor = self._conn.execute(
                "SELECT symbol, bid, ask, last, bid_size, ask_size, volume, timestamp, source, quality "
                "FROM quotes WHERE symbol = ? ORDER BY timestamp",
                (symbol,),
            )
        return [
            Quote(
                symbol=row[0],
                bid=row[1],
                ask=row[2],
                last=row[3],
                bid_size=row[4],
                ask_size=row[5],
                volume=row[6],
                timestamp=_str_to_dt(row[7]),
                source=row[8],
                quality=DataQuality(row[9]),
            )
            for row in cursor.fetchall()
        ]

    def get_bars(
        self, symbol: str, timeframe: str, since: datetime | None = None
    ) -> list[Bar]:
        if not self.enabled:
            return []
        assert self._conn is not None
        if since is not None:
            cursor = self._conn.execute(
                "SELECT symbol, timeframe, open, high, low, close, volume, timestamp, source, quality "
                "FROM bars WHERE symbol = ? AND timeframe = ? AND timestamp >= ? ORDER BY timestamp",
                (symbol, timeframe, _dt_to_str(since)),
            )
        else:
            cursor = self._conn.execute(
                "SELECT symbol, timeframe, open, high, low, close, volume, timestamp, source, quality "
                "FROM bars WHERE symbol = ? AND timeframe = ? ORDER BY timestamp",
                (symbol, timeframe),
            )
        return [
            Bar(
                symbol=row[0],
                timeframe=row[1],
                open=row[2],
                high=row[3],
                low=row[4],
                close=row[5],
                volume=row[6],
                timestamp=_str_to_dt(row[7]),
                source=row[8],
                quality=DataQuality(row[9]),
            )
            for row in cursor.fetchall()
        ]
