---
name: 100 Schwab Provider
overview: "Implement SchwabProvider using schwab-py library: message-pump architecture bridging handler callbacks to AsyncIterator, symbol mapping (bidirectional), 1m→Nm bar aggregation, OAuth auth. Test-first."
todos: []
isProject: false
---

# 100: Schwab Provider Integration

Conforms to [000_observer_mvp_initial_plan.md](000_observer_mvp_initial_plan.md) §providers/ and M2 milestone.

---

## Project Practice: Test-First (Red-Green-Refactor)

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests that specify the expected behavior. Run tests; they fail. |
| **Green** | Implement minimal code to make the tests pass. Run tests; they pass. |
| **Refactor** | Clean up implementation while keeping tests green. |

---

## Objective

Implement `SchwabProvider` — the first real data provider — using the `schwab-py` library. This provider streams live futures quotes and OHLCV bars from Schwab's WebSocket API, maps them to canonical types, aggregates 1-minute bars into the requested timeframe, and auto-populates ContractSpec from stream metadata.

### Key architectural challenge

schwab-py uses a **callback handler pattern** (register handler → loop on `handle_message()`), but `BaseProvider` requires **`AsyncIterator`** returns from `subscribe_quotes()` / `subscribe_bars()`. A message-pump architecture with `asyncio.Queue`s bridges this gap.

---

## Existing Foundation

- Step 030: BaseProvider protocol, SimProvider, ProviderHealth
- Step 020: canonical types (Quote, Bar, FutureSymbol, ContractSpec, DataQuality) in `core/`
- Step 040: MarketState that consumes Quote and Bar events
- Step 070: Backend API wiring (`consume_quotes`, `consume_bars` — swap SimProvider for SchwabProvider)
- Step 090: `app.py` lifespan pattern, `OBSERVER_DB_PATH` env var precedent

---

## Prerequisites

- **Schwab brokerage account** with futures trading enabled
- **Developer app** registered at [developer.schwab.com](https://developer.schwab.com)
- Credentials in `.env`:

| Env Var | Description | Example |
|---------|-------------|---------|
| `SCHWAB_API_KEY` | App key from developer portal | `abc123...` |
| `SCHWAB_APP_SECRET` | App secret from developer portal | `xyz789...` |
| `SCHWAB_CALLBACK_URL` | OAuth callback URL | `https://127.0.0.1` |
| `SCHWAB_TOKEN_PATH` | File path for cached OAuth token | `./schwab_token.json` |
| `SCHWAB_ACCOUNT_ID` | Numeric account ID (int) | `1234567890` |

---

## Interface Contract

### SchwabProvider (implements BaseProvider)

```python
class SchwabProvider(BaseProvider):
    """Live futures data from Schwab via schwab-py streaming API.

    Architecture: connect() starts a _message_pump task that loops on
    handle_message(), dispatching to registered handlers. Handlers push
    normalized events onto asyncio.Queues. subscribe_quotes() and
    subscribe_bars() read from their respective queues, yielding
    canonical types.

    Reasoning: schwab-py's callback handler pattern cannot directly
    produce AsyncIterator. Queues decouple the single WebSocket
    message loop from the two independent consumer iterators.
    """

    def __init__(
        self,
        api_key: str,
        app_secret: str,
        callback_url: str,
        token_path: str,
        account_id: int,
        symbols: list[str] | None = None,
    ) -> None: ...
```

### Message Pump Architecture

```
                    ┌──────────────────────────────┐
                    │   schwab-py StreamClient      │
                    │   (single WebSocket)          │
                    └──────────┬───────────────────┘
                               │ handle_message() loop
                               │ (_message_pump task)
                    ┌──────────┴───────────────────┐
          ┌────────┤  dispatcher (registered        ├────────┐
          │        │  handlers by service type)     │        │
          ▼        └───────────────────────────────┘        ▼
  _on_quote_msg()                                   _on_bar_msg()
     │ normalize + push                                │ normalize + push
     ▼                                                 ▼
  _quote_queue                                      _bar_queue
  (asyncio.Queue)                                   (asyncio.Queue)
     │                                                 │
     ▼                                                 ▼
  subscribe_quotes()                                subscribe_bars()
  yields Quote                                      yields Bar (aggregated)
```

### Schwab API Streams Used

| schwab-py Method | Data | Canonical Output |
|------------------|------|------------------|
| `StreamClient.level_one_futures_subs(symbols, fields=...)` | Bid, Ask, Last, Volume, Tick, Multiplier, Trading Hours | `Quote` |
| `StreamClient.chart_futures_subs(symbols)` | 1-minute OHLCV | `Bar` (aggregated to requested timeframe) |

### Schwab Futures Quote Fields (from `StreamClient.LevelOneFuturesFields`)

schwab-py relabels numeric field keys to string names. The handler receives a dict with these string keys:

| Relabeled Key | Enum | Use |
|---------------|------|-----|
| `"SYMBOL"` | `SYMBOL` (0) | Map via `schwab_to_canonical()` |
| `"BID_PRICE"` | `BID_PRICE` (1) | `Quote.bid` |
| `"ASK_PRICE"` | `ASK_PRICE` (2) | `Quote.ask` |
| `"LAST_PRICE"` | `LAST_PRICE` (3) | `Quote.last` |
| `"BID_SIZE"` | `BID_SIZE` (4) | `Quote.bid_size` |
| `"ASK_SIZE"` | `ASK_SIZE` (5) | `Quote.ask_size` |
| `"TOTAL_VOLUME"` | `TOTAL_VOLUME` (8) | `Quote.volume` |
| `"QUOTE_TIME_MILLIS"` | `QUOTE_TIME_MILLIS` (10) | `Quote.timestamp` (ms → UTC datetime) |
| `"SECURITY_STATUS"` | `SECURITY_STATUS` (22) | `DataQuality` mapping (see below) |
| `"TICK"` | `TICK` (25) | `ContractSpec.tick_size` |
| `"TICK_AMOUNT"` | `TICK_AMOUNT` (26) | Validation (tick dollar value) |
| `"FUTURE_MULTIPLIER"` | `FUTURE_MULTIPLIER` (31) | `ContractSpec.point_value` |
| `"FUTURE_TRADING_HOURS"` | `FUTURE_TRADING_HOURS` (29) | `ContractSpec.session` |
| `"FUTURE_ACTIVE_SYMBOL"` | `FUTURE_ACTIVE_SYMBOL` (34) | Active contract resolution |

### Schwab Futures Chart Fields (from `StreamClient.ChartFuturesFields`)

| Relabeled Key | Enum | Use |
|---------------|------|-----|
| `"SYMBOL"` | `SYMBOL` (0) | Map via `schwab_to_canonical()` |
| `"CHART_TIME_MILLIS"` | `CHART_TIME_MILLIS` (1) | Bar close timestamp (ms → UTC datetime) |
| `"OPEN_PRICE"` | `OPEN_PRICE` (2) | `Bar.open` |
| `"HIGH_PRICE"` | `HIGH_PRICE` (3) | `Bar.high` |
| `"LOW_PRICE"` | `LOW_PRICE` (4) | `Bar.low` |
| `"CLOSE_PRICE"` | `CLOSE_PRICE` (5) | `Bar.close` |
| `"VOLUME"` | `VOLUME` (6) | `Bar.volume` |

### SECURITY_STATUS → DataQuality Mapping

| SECURITY_STATUS | DataQuality | Rationale |
|-----------------|-------------|-----------|
| `"Normal"` | `OK` | Market is open and streaming normally |
| `"Halted"` | `STALE` | Trading halted; data frozen |
| `"Closed"` | `STALE` | Market closed; data is last known |
| unknown / missing | `PARTIAL` | Unexpected status; flag for attention |

### Symbol Mapping (Bidirectional)

| Direction | Input | Output | Function |
|-----------|-------|--------|----------|
| Schwab → Canonical | `"/ESH26"` (from `FUTURE_ACTIVE_SYMBOL`) | `FutureSymbol(root="ES", contract_code="H26", front_month_alias="/ES")` | `schwab_to_canonical()` |
| Canonical → Schwab | `"ESH26"` (canonical symbol string) | `"/ES"` (root-only, for subscription) | `canonical_to_schwab()` |

Note: Schwab subscriptions use root symbols (`/ES`, `/NQ`). The active contract symbol (e.g., `/ESH26`) arrives in the `FUTURE_ACTIVE_SYMBOL` field on the first message and is used to determine `contract_code`.

### Bar Aggregation (1m → Nm)

```python
class BarAggregator:
    """Aggregates 1-minute Schwab bars into N-minute bars.

    Reasoning: Schwab only streams 1m bars via chart_futures_subs.
    Engine.on_bar() only triggers evaluation when bar.timeframe matches
    EngineConfig.eval_timeframe (default "5m"). The provider must deliver
    bars at the requested timeframe per P1 (canonical types only).
    """

    def __init__(self, target_timeframe: str) -> None: ...
    def add(self, bar_1m: Bar) -> Bar | None:
        """Accumulate a 1m bar. Return aggregated bar when window completes, else None."""
```

Aggregation rules:
- `open` = first bar's open
- `high` = max of all bars' highs
- `low` = min of all bars' lows
- `close` = last bar's close
- `volume` = sum of all bars' volumes
- `timestamp` = last bar's timestamp (bar close convention)
- Window boundary: aligned to clock (e.g., 5m bars close at :05, :10, :15, ...)

### ContractSpec Bootstrap

`get_contract_specs()` is called *before* streaming starts (by `app.py`). Since ContractSpec data only arrives in the first stream message, the provider uses **hardcoded initial specs** for known symbols (ES, NQ) and validates/updates them when the first level-one message arrives.

```python
_KNOWN_SPECS: dict[str, ContractSpec] = {
    "ESH26": ContractSpec(symbol="ESH26", instrument_type=InstrumentType.FUTURE,
                          tick_size=0.25, point_value=50.0, session=_ES_RTH),
    "NQH26": ContractSpec(symbol="NQH26", instrument_type=InstrumentType.FUTURE,
                          tick_size=0.25, point_value=20.0, session=_NQ_RTH),
}
```

On first stream message with TICK / FUTURE_MULTIPLIER fields, log a warning if values don't match the hardcoded spec. Update the spec in-place if they differ. This keeps `get_contract_specs()` synchronous and available before streaming.

---

## Module Layout

```
backend/src/providers/
  __init__.py             # updated: export SchwabProvider
  base.py                 # (existing from 030)
  sim_provider.py         # (existing from 030)
  schwab_provider.py      # SchwabProvider + message pump + bar aggregation
  schwab_mapper.py        # Bidirectional symbol mapping + ContractSpec extraction

backend/tests/unit/providers/
  __init__.py             # (existing)
  conftest.py             # (existing)
  test_base.py            # (existing)
  test_sim_provider.py    # (existing)
  test_schwab_mapper.py   # symbol mapping + ContractSpec extraction + DataQuality mapping
  test_schwab_provider.py # unit tests with mocked schwab-py client
  test_bar_aggregator.py  # 1m → Nm bar aggregation tests
```

---

## Implementation Phases

### Phase 0: Directory + file setup + dependency (Create+Verify)

| Stage | Tasks |
|-------|-------|
| **Create** | `pip install schwab-py` and add to `backend/pyproject.toml` `[project.dependencies]`. Create stub files: `schwab_provider.py`, `schwab_mapper.py`, `test_schwab_mapper.py`, `test_schwab_provider.py`, `test_bar_aggregator.py`. Update `.env.example` with Schwab credential variables. |
| **Verify** | `pytest backend/tests/unit/ --collect-only` discovers no errors. `python -c "import schwab"` succeeds. |

### Phase 1: Bidirectional symbol mapping + ContractSpec extraction

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_schwab_mapper.py`: `schwab_to_canonical("/ESH26")` returns `FutureSymbol(root="ES", contract_code="H26", front_month_alias="/ES")`; `canonical_to_schwab("ESH26")` returns `"/ES"`; `extract_contract_spec()` from a sample relabeled field dict returns `ContractSpec` with correct `tick_size`, `point_value`; `map_security_status("Normal")` returns `DataQuality.OK`, `"Halted"` → `STALE`, `"Closed"` → `STALE`, unknown → `PARTIAL`; handle unknown symbol format gracefully (raise `ValueError`) |
| **Green** | Implement `schwab_mapper.py`: `schwab_to_canonical`, `canonical_to_schwab`, `extract_contract_spec`, `map_security_status`, `parse_trading_hours` |
| **Refactor** | Edge cases: unknown root symbols, missing fields default to `None` with logged warning |

### Phase 2: Bar aggregation (1m → Nm)

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_bar_aggregator.py`: `BarAggregator("5m")` collects 5 sequential 1m bars, returns `None` for bars 1-4, returns aggregated `Bar(timeframe="5m")` on bar 5 with correct OHLCV; multiple symbols tracked independently; window aligned to clock boundaries; `BarAggregator("1m")` passes bars through unchanged |
| **Green** | Implement `BarAggregator` in `schwab_provider.py` (or `schwab_mapper.py`): `add(bar_1m)` accumulates per-symbol, returns aggregated bar when window completes |
| **Refactor** | Handle partial windows at session boundaries (flush on disconnect) |

### Phase 3: SchwabProvider — auth, connection, message pump

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_schwab_provider.py` (with mocked `schwab.auth.easy_client` and `StreamClient`): `__init__` accepts credential params; `connect()` calls `easy_client()`, creates `StreamClient`, calls `login()`, starts `_message_pump` task; `disconnect()` cancels pump, calls `logout()`; `health()` returns `ProviderHealth(connected=True)` after connect, `connected=False` after disconnect; `get_contract_specs()` returns hardcoded specs before streaming |
| **Green** | Implement `SchwabProvider.__init__`, `connect()` (auth → StreamClient → login → start `_message_pump`), `disconnect()`, `health()`, `get_contract_specs()`. The `_message_pump` loops `handle_message()` and catches exceptions. |
| **Refactor** | Credential validation on startup (raise early if env vars missing). Log provider version + connected symbols on connect. |

### Phase 4: SchwabProvider — quote stream

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: `subscribe_quotes(["ESH26"])` calls `canonical_to_schwab` → `level_one_futures_subs(["/ES"])` with requested fields; handler pushes normalized `Quote` to `_quote_queue`; iterator yields `Quote` with correct `bid`, `ask`, `last`, `volume`, `timestamp`; `source="schwab"`; `quality` from `SECURITY_STATUS` mapping; first message triggers `ContractSpec` validation |
| **Green** | Implement `subscribe_quotes`: register `_on_quote_msg` handler → subscribe → yield from `_quote_queue`. Handler: extract relabeled fields, call `schwab_to_canonical`, map security status, construct `Quote`, push to queue. First message: call `extract_contract_spec` and validate against hardcoded spec. |
| **Refactor** | Request only needed fields via `fields=` parameter to reduce bandwidth |

### Phase 5: SchwabProvider — bar stream

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: `subscribe_bars(["ESH26"], "5m")` subscribes to chart stream; handler pushes 1m bars through `BarAggregator`; only yields aggregated 5m bars; OHLCV mapped correctly; `timestamp` = bar close (UTC); `source="schwab"` |
| **Green** | Implement `subscribe_bars`: register `_on_bar_msg` handler → subscribe → yield from `_bar_queue`. Handler: normalize 1m bar, feed to `BarAggregator`, push aggregated bar to queue when returned. |
| **Refactor** | Verify timestamp alignment with known market data |

### Phase 6: Error handling + reconnection

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: `_message_pump` catches `ConnectionClosed` / `Exception`; sets `_connected = False`; health reflects disconnected; reconnection sequence: re-create `StreamClient` → re-`login()` → re-subscribe → re-add handlers; backoff: 1s, 2s, 4s, ..., max 60s; no raw schwab-py exceptions leak to consumers (queues get sentinel or exception wrapper) |
| **Green** | Implement reconnection state machine in `_message_pump`: catch → log → backoff → re-init → re-login → re-subscribe → re-add handlers. On disconnect, push `None` sentinel to queues so iterators can detect and re-await. Update `ProviderHealth` throughout. |
| **Refactor** | Configurable backoff parameters (`min_backoff`, `max_backoff`). Log reconnection attempts with attempt count. |

### Phase 7: Integration with backend API

| Stage | Tasks |
|-------|-------|
| **Red** | Integration test (mocked schwab-py): create app with `OBSERVER_PROVIDER=schwab`, verify `SchwabProvider` is instantiated; feed mock messages → MarketState populated → Engine triggers on bar close → candidates appear in snapshot |
| **Green** | Update `app.py` lifespan: read `OBSERVER_PROVIDER` env var; when `"schwab"`, read Schwab credential env vars, instantiate `SchwabProvider`; default remains `SimProvider`. Both providers are `BaseProvider` — rest of wiring is unchanged. |
| **Refactor** | Update `providers/__init__.py` exports. Update existing integration tests to explicitly use `OBSERVER_PROVIDER=sim` (they already do implicitly). |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Library | `schwab-py` | Well-maintained, async, handles OAuth + field relabeling automatically |
| Message pump | `connect()` starts `_message_pump` task; handlers push to `asyncio.Queue`s | Bridges schwab-py's callback pattern to BaseProvider's AsyncIterator contract; single WebSocket → multiple consumers |
| Auth | OAuth via `easy_client()` | Standard schwab-py pattern; token cached to file for session persistence |
| Symbol mapping | Bidirectional: `canonical_to_schwab()` for subscriptions, `schwab_to_canonical()` for normalization | Subscription API expects `/ES`; all internal types use `ESH26` |
| ContractSpec bootstrap | Hardcoded initial specs for known symbols; validate from first stream message | `get_contract_specs()` must work before streaming starts (called in `app.py` lifespan) |
| Bar aggregation | Provider-side 1m → Nm via `BarAggregator` | Schwab only streams 1m bars; Engine requires matching `eval_timeframe`; P1 says providers emit canonical types at the requested granularity |
| Reconnection | Full state machine: re-create StreamClient → re-login → re-subscribe → re-add handlers | schwab-py's WebSocket lifecycle requires complete reinitialization on disconnect |
| Backoff | Exponential: 1s, 2s, 4s, ... max 60s | Resilient to temporary disconnects without hammering the API |
| Provider selection | `OBSERVER_PROVIDER` env var (`sim` or `schwab`) | Simple, matches existing pattern (`OBSERVER_DB_PATH`); default `sim` keeps dev easy |
| SECURITY_STATUS mapping | `"Normal"` → OK, `"Halted"` / `"Closed"` → STALE, unknown → PARTIAL | Conservative: unknown status flagged for attention rather than silently assumed OK |

---

## Acceptance Criteria

- [x] `schwab-py` added to `pyproject.toml` dependencies (v1.5.1)
- [x] `.env.example` updated with all Schwab credential variables
- [x] `canonical_to_schwab("ESH26")` returns `"/ES"`
- [x] `schwab_to_canonical("/ESH26")` returns correct `FutureSymbol`
- [x] `map_security_status` maps all known statuses to correct `DataQuality`
- [x] `BarAggregator("5m")` correctly aggregates 5 sequential 1m bars
- [x] `BarAggregator("1m")` passes bars through unchanged
- [x] `SchwabProvider` implements `BaseProvider` protocol
- [x] `connect()` creates client, StreamClient, logs in, starts message pump
- [x] `disconnect()` cancels pump, logs out
- [x] `get_contract_specs()` returns specs before streaming starts
- [x] `subscribe_quotes` yields `Quote` objects with correct fields, `source="schwab"`
- [x] `subscribe_bars` yields aggregated `Bar` objects at requested timeframe
- [x] All emitted events have appropriate `DataQuality` from `SECURITY_STATUS`
- [x] ContractSpec validated/updated from first stream message
- [x] Reconnection: pump error sets disconnected, no raw exceptions leak to queues
- [x] `health()` reflects connection state throughout lifecycle
- [x] No raw schwab-py exceptions leak to consumers
- [x] `OBSERVER_PROVIDER=schwab` in `app.py` selects `SchwabProvider`
- [x] `OBSERVER_PROVIDER=sim` (default) keeps existing behavior
- [x] All unit tests pass with mocked schwab-py client (330 total)
- [x] Existing SimProvider tests unaffected
- [ ] Live verification with Schwab credentials (manual — during market hours)

---

## Manual Verification

```bash
# 1. Run all unit tests (mocked, no credentials needed)
cd backend && python -m pytest tests/unit/ -v

# 2. Set credentials in .env (copy from .env.example)
cp .env.example .env
# Edit .env with real Schwab credentials

# 3. Start backend with Schwab provider (during market hours)
cd backend && OBSERVER_PROVIDER=schwab PYTHONPATH=src uvicorn api.app:create_app --factory --port 8000

# 4. Verify live data
curl -s http://localhost:8000/api/snapshot | python -m json.tool
# Should show real ES/NQ quotes with source="schwab"

# 5. Verify WebSocket stream
wscat -c ws://localhost:8000/ws
# Should show live quote_update and bar_update messages with real prices

# 6. Verify provider health
curl -s http://localhost:8000/api/health | python -m json.tool
# Should show provider.connected=true, provider.source="schwab"

# 7. Start backend with SimProvider (default) — verify no regression
cd backend && PYTHONPATH=src uvicorn api.app:create_app --factory --port 8000
# Should work exactly as before
```

---

## Out of Scope

- Equities/options streaming (v2; schwab-py supports it)
- Historical bar fetch via REST (schwab-py has `get_price_history`)
- Order placement (V1 is observation only)
- Level Two data
- Tradovate provider (parked as step 102)
- Bar aggregation for non-minute multiples (e.g., tick bars)
- Multi-account support
