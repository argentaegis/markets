---
name: 070 Backend API
overview: "Implement FastAPI backend: /ws WebSocket for live market updates + candidates, /api/snapshot REST for current state. Wire SimProvider -> MarketState -> Engine -> API. Test-first."
todos: []
isProject: false
---

# 070: Backend API (FastAPI + WebSocket + REST)

Conforms to [000_observer_mvp_initial_plan.md](000_observer_mvp_initial_plan.md) §Implementation stack and §Immediate next step.

---

## Project Practice: Test-First (Red-Green-Refactor)

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests that specify the expected behavior. Run tests; they fail. |
| **Green** | Implement minimal code to make the tests pass. Run tests; they pass. |
| **Refactor** | Clean up implementation while keeping tests green. |

---

## Objective

Build the FastAPI backend that wires the full data pipeline together and exposes it to the frontend. Two endpoints:
1. `/ws` WebSocket — streams live market updates (quotes, bars) and candidate updates
2. `/api/snapshot` REST — returns current MarketState + active candidates as JSON

This is the integration point where SimProvider -> MarketState -> Engine -> API all connect.

---

## Existing Foundation

- Step 010: `backend/src/api/` package (with `__init__.py` and stub `app.py`), pyproject.toml with FastAPI/uvicorn/httpx
- Step 020: canonical types in `core/`
- Step 030: SimProvider in `providers/`
- Step 040: MarketState + Context in `state/`
- Step 050: DummyStrategy in `strategies/`
- Step 060: Engine + CandidateStore in `engine/`

---

## Interface Contract

### REST Endpoints

| Method | Path | Response | Description |
|--------|------|----------|-------------|
| GET | `/api/snapshot` | `{ quotes: {...}, bars: {...}, candidates: [...] }` | Current market state + active candidates |
| GET | `/api/health` | `{ status: "ok", provider: ProviderHealth }` | Backend + provider health |

### WebSocket Endpoint

| Path | Direction | Message Types |
|------|-----------|---------------|
| `/ws` | Server -> Client | `quote_update`, `bar_update`, `candidates_update` |

### WebSocket Message Format

```json
{
  "type": "quote_update",
  "data": { "symbol": "ESH26", "bid": 5412.25, "ask": 5412.50, ... }
}
```

```json
{
  "type": "bar_update",
  "data": { "symbol": "ESH26", "timeframe": "5m", "open": 5410.0, ... }
}
```

```json
{
  "type": "candidates_update",
  "data": [{ "id": "...", "symbol": "ESH26", "strategy": "dummy", "direction": "LONG", ... }]
}
```

---

## Module Layout

```
backend/src/api/
  __init__.py
  app.py               # FastAPI app factory, lifespan, CORS, include routers
  snapshot.py           # GET /api/snapshot
  health.py             # GET /api/health
  ws_handler.py         # WebSocket connection manager + /ws endpoint
  wiring.py             # Background tasks: consume_quotes, consume_bars
  serializers.py        # dataclass → dict helpers for JSON serialization

backend/tests/unit/api/
  __init__.py
  conftest.py           # TestClient fixture, mock state/engine/provider
  test_snapshot.py
  test_health.py
  test_ws.py
```

Note: Flat layout — no `routes/` or `ws/` sub-packages. Only 3 endpoints; nesting adds complexity without benefit at this scale.

---

## Application Startup (wiring)

```python
async def lifespan(app: FastAPI):
    """Application lifecycle: start provider + engine on startup, clean up on shutdown."""
    # Startup
    provider = SimProvider(seed=42)
    state = MarketState()
    engine = Engine(strategies=[DummyStrategy()], state=state, config=EngineConfig())
    ws_manager = ConnectionManager()

    await provider.connect()
    symbols = list(provider.get_contract_specs().keys())  # ["ESH26", "NQM26"]
    timeframe = engine._config.eval_timeframe              # "5m"

    # Background tasks: consume provider streams
    # consume_quotes: state.update_quote + ws broadcast (no engine involvement)
    # consume_bars: engine.on_bar (updates state + evaluates) + ws broadcast
    quote_task = asyncio.create_task(
        consume_quotes(provider, symbols, state, ws_manager)
    )
    bar_task = asyncio.create_task(
        consume_bars(provider, symbols, timeframe, engine, ws_manager)
    )

    app.state.provider = provider
    app.state.market_state = state
    app.state.engine = engine
    app.state.ws_manager = ws_manager

    yield

    # Shutdown
    quote_task.cancel()
    bar_task.cancel()
    await provider.disconnect()
```

#### Background task signatures

```python
async def consume_quotes(provider, symbols, state, ws_manager):
    """Quote loop: update state + broadcast. No engine involvement."""
    async for quote in provider.subscribe_quotes(symbols):
        state.update_quote(quote)
        await ws_manager.broadcast("quote_update", quote)

async def consume_bars(provider, symbols, timeframe, engine, ws_manager):
    """Bar loop: engine.on_bar handles state update + evaluation."""
    async for bar in provider.subscribe_bars(symbols, timeframe):
        new_candidates = engine.on_bar(bar)  # updates MarketState internally
        await ws_manager.broadcast("bar_update", bar)
        if new_candidates:
            await ws_manager.broadcast("candidates_update", new_candidates)
```

Note: `consume_bars` does NOT pass `state` — `engine.on_bar(bar)` owns the state update (per 060 design). Symbols come from `provider.get_contract_specs().keys()`. Timeframe comes from `EngineConfig.eval_timeframe`.

---

## Implementation Phases

### Phase 0: Directory + file setup (Create+Verify)

| Stage | Tasks |
|-------|-------|
| **Create** | Create `backend/tests/unit/api/` with `__init__.py` and `conftest.py`. Create `backend/src/api/serializers.py`, `snapshot.py`, `health.py`, `ws_handler.py`, `wiring.py`. Verify `app.py` already exists (from 010). |
| **Verify** | `pytest backend/tests/unit/api/ --collect-only` discovers no errors (empty test dir is OK). `python -c "from api import ..."` works for existing modules. |

### Phase 1: Serializers (dict helpers)

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_snapshot.py` serializer section: `serialize_quote` returns dict with expected keys; `serialize_bar` returns dict; `serialize_candidate` returns dict with all TradeCandidate fields; `serialize_snapshot` returns `{quotes, bars, candidates}` |
| **Green** | Implement `serializers.py`: plain functions `serialize_quote(q) -> dict`, `serialize_bar(b) -> dict`, `serialize_candidate(c) -> dict`, `serialize_snapshot(snapshot, candidates) -> dict`. Uses `dataclasses.asdict` or manual field mapping. No Pydantic models (core types are already dataclasses with float fields — no Decimal conversion needed). |
| **Refactor** | Ensure `datetime` fields serialize to ISO 8601 strings; `Direction`/`EntryType` enums serialize to `.value` strings |

### Phase 2: App factory + CORS

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_snapshot.py` app test: verify a basic `GET /api/snapshot` returns 200 against a minimal app (pre-populated `app.state`). This requires the app factory to exist. |
| **Green** | Implement `app.py`: `create_app()` factory — creates FastAPI instance, adds CORS middleware (`allow_origins=["http://localhost:5173"]`), includes routers. For now, lifespan is a no-op placeholder. Store nothing on `app.state` at this point (tests will set state manually). |
| **Refactor** | Configurable CORS origins from env var |

### Phase 3: REST — /api/snapshot

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_snapshot.py`: GET /api/snapshot returns 200; response has `quotes`, `bars`, `candidates` keys; with pre-populated MarketState+Engine returns expected data; empty state returns empty collections |
| **Green** | Implement `snapshot.py`: `APIRouter` with GET `/api/snapshot`. Reads `request.app.state.market_state` and `request.app.state.engine`. Calls `serialize_snapshot()`. |
| **Refactor** | Response schema validation |

### Phase 4: REST — /api/health

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_health.py`: GET /api/health returns 200; response contains `status` and `provider` keys; provider health has `connected`, `last_update` fields |
| **Green** | Implement `health.py`: `APIRouter` with GET `/api/health`. Reads `request.app.state.provider.health()`. |
| **Refactor** | Handle case where provider is not yet connected |

### Phase 5: WebSocket — /ws

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_ws.py`: WebSocket at `/ws` accepts connection; ConnectionManager `broadcast()` sends to all connected clients; disconnected clients are removed silently (no crash); message format is `{"type": "...", "data": {...}}` |
| **Green** | Implement `ws_handler.py`: `ConnectionManager` class (connect, disconnect, broadcast), `/ws` endpoint as `APIRouter`. `broadcast(msg_type, data)` serializes core types to dict, wraps in `{"type": msg_type, "data": ...}`, sends JSON to all clients. Disconnected clients caught with try/except. |
| **Refactor** | Clean up message serialization; logging for connect/disconnect |

### Phase 6: Wiring + background tasks

| Stage | Tasks |
|-------|-------|
| **Red** | Write integration test in `test_ws.py`: start app with real SimProvider (fast tick), connect WebSocket, verify `quote_update` message arrives within timeout; verify `bar_update` arrives; verify `candidates_update` after bar close triggers evaluation |
| **Green** | Implement `wiring.py`: `consume_quotes` and `consume_bars` coroutines (signatures per "Background task signatures" above). Update `app.py` lifespan to wire SimProvider → Engine → background tasks per "Application Startup" section. |
| **Refactor** | Error handling in background tasks (log + continue on broadcast failure); graceful shutdown (cancel + await tasks) |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| WebSocket for live data | Server pushes quote/bar/candidate updates | 000 specifies WebSocket for live updates; lower latency than polling |
| REST for snapshots | GET /api/snapshot | Full state on page load; WebSocket for incremental updates |
| Dict serializers (not Pydantic) | Plain `serialize_*` functions | Core types use float (not Decimal), so no type conversion needed; `dataclasses.asdict` + enum `.value` is sufficient |
| Background tasks | `asyncio.create_task` in lifespan | Natural fit for async provider streams; single event loop |
| Connection manager | Broadcast pattern | Multiple UI clients can connect; each gets same updates |
| Flat module layout | No `routes/` or `ws/` sub-packages | Only 3 endpoints — nesting is premature for this scale |
| `engine.on_bar()` owns state update | `consume_bars` does not touch `MarketState` directly | Per 060 design: `Engine.on_bar()` calls `state.update_bar()` internally |
| App factory pattern | `create_app()` function | Enables clean test setup (tests can set `app.state` before requests) |

---

## Acceptance Criteria

- [ ] `pytest backend/tests/unit/api/` — all tests pass
- [ ] `uvicorn` starts the backend without errors (`uvicorn src.api.app:create_app --factory`)
- [ ] `GET /api/snapshot` returns JSON with `quotes`, `bars`, `candidates` keys
- [ ] `GET /api/health` returns JSON with `status` and `provider` keys
- [ ] WebSocket at `/ws` accepts connections and sends JSON messages
- [ ] WebSocket receives `quote_update` messages with serialized Quote data
- [ ] WebSocket receives `bar_update` messages with serialized Bar data
- [ ] WebSocket receives `candidates_update` after bar-close triggers engine evaluation
- [ ] Full pipeline: SimProvider → MarketState → Engine → API → WebSocket
- [ ] CORS allows `http://localhost:5173`
- [ ] No new linter errors introduced

---

## Manual Verification

```bash
# Terminal 1: start backend
cd backend && uvicorn src.api.app:create_app --factory --reload

# Terminal 2: test REST
curl http://localhost:8000/api/health
curl http://localhost:8000/api/snapshot

# Terminal 3: test WebSocket
wscat -c ws://localhost:8000/ws
# Should see quote_update and candidates_update messages
```

---

## Out of Scope

- Authentication / authorization
- Rate limiting
- Historical data REST endpoints
- Frontend serving from backend (Vite handles its own dev server)
