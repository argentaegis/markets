# Cursor Instructions: Modular Market Observer + Trade Recommender (Futures-first)

## Project intent (keep this fixed)
Build a **manual algo / algorithm-augmented mechanical trading** tool that:
1) ingests live market data from **pluggable providers** (swap Schwab/NinjaTrader/etc without changing strategy code),
2) shows **market state + recommendations** on the same screen,
3) lets me **define/enable strategies** that emit trade candidates (entry/exit), not orders.

### V1 focus
- Asset class: **futures** (ES/NQ/etc)
- Data source: **provider plug-in** (start with a futures-capable provider; keep Schwab adapter scaffolded for later equities/options)
- Output: **trade candidates** + "why", ranked, with validity windows
- No auto execution in V1

---

## Non-goals (explicitly out of scope for V1)
- automated trade execution
- "AI prediction" models
- portfolio optimization across strategies
- full options chain ingestion (v2+)

---

## Architecture (modules and responsibilities)
Implement a clean pipeline with strict boundaries:

**Provider Adapter** → **Normalizer** → **Market State Store** → **Strategy Engine** → **Recommendation Store** → **UI**

### 1) `providers/` (pluggable data ingestion)
Goal: connect to a data source and emit canonical events.
- `BaseProvider` interface (required)
- `FuturesProviderX` implementation for V1
- `SchwabProvider` stub (scaffold only; used later for equities/options)
- `SimProvider` (replay / fake data for dev + tests)

**Rule:** Providers emit only canonical types. No broker/vendor objects leak past this layer.

### 2) `core/` (canonical schema + utilities)
Define canonical domain types used everywhere:
- `Instrument` (type: future/equity/option), `Symbol` normalization, `ContractSpec` (tick size, multiplier, session)
- `Quote`, `Bar`
- `TradeCandidate` (the recommendation artifact)
- `DataQuality` flags (stale/missing/partial)

### 3) `state/` (market state store)
Goal: "current truth" for strategies.
- latest quote per symbol
- rolling bar windows per symbol/timeframe
- (later) chain snapshots / greeks
- persistence: SQLite/DuckDB optional but recommended for debugging

### 4) `strategies/` (user strategies)
Goal: user-defined strategies that read from `Context` and emit `TradeCandidate[]`.
- strategies are pure logic, no direct API calls
- dynamic loading/registry so strategies can be added without touching engine code

### 5) `engine/` (scheduler + evaluator + ranking)
Goal:
- decide when to evaluate (bar-close cadence recommended)
- run enabled strategies
- dedupe + rank candidates
- manage candidate validity windows and invalidation

### 6) `ui/` (display)
Goal: single dashboard showing **market data + recommendations** simultaneously.
- left pane: watchlist + live quote + last bar + mini chart
- right pane: candidate table + score + entry/stop/target + why bullets
- details panel: indicators + evidence

---

## Implementation stack (recommendation)
Use a simple local client/server split:
- **Backend:** Python + FastAPI (fits strategy/backtester reuse and data work)
- **Frontend:** React + Vite (fits your existing preferences)
- **Transport:** WebSockets for live updates + REST for snapshots

Keep everything runnable locally.

---

## Futures-specific requirements (V1 must handle)
### Contract identity and roll
- Define a canonical `FutureSymbol` model:
  - root (e.g., ES)
  - contract code (e.g., H26)
  - "front month continuous" alias (e.g., ES1!)
- V1: allow manual selection of the active contract per root in config.
- Store `ContractSpec`: tick size, point value/multiplier, trading hours/session calendar.

### Session/time handling
- Use exchange session rules (RTH vs ETH) explicitly.
- Strategies must know whether they evaluate on:
  - bar close (recommended) and which session they mean.

### Tick size normalization
- All prices must be normalized to tick size in `core/`.

---

## Canonical interfaces (do not deviate)
### Provider interface (backend)
Create a base provider protocol:

- `connect()`
- `subscribe_quotes(symbols) -> async iterator[Quote]`
- `subscribe_bars(symbols, timeframe) -> async iterator[Bar]`
- `disconnect()`
- `health() -> ProviderHealth`

Providers must:
- attach `source`
- attach `quality` (stale/missing)
- never throw raw exceptions to engine; wrap and report health

### Strategy interface (backend)
Strategies emit candidates:

- `name: str`
- `requirements() -> Requirements`
  - symbols/universe
  - timeframes + lookback
  - needs_quotes bool
- `evaluate(ctx: Context) -> list[TradeCandidate]`

### TradeCandidate schema (backend -> UI)
A candidate must include at least:
- symbol / instrument
- direction (LONG/SHORT)
- entry (type + price or trigger rule)
- stop (price)
- targets (list) OR exit rule
- score (float)
- explain bullets (3–6)
- valid_until timestamp
- tags (regime, setup name)

**Rule:** Candidate is informational only (no order placement fields in V1).

---

## Strategy specification goals (how user "specifies strategies")
V1: strategies as Python modules/classes + config to enable/disable them.
- `config.yaml`:
  - enabled strategies list
  - per-strategy parameters
  - watchlists/universes

V2 option (do not implement now): YAML/DSL strategy definitions.

---

## UI requirements (V1)
### Layout
- Split view:
  - **Market pane**: watchlist table + selected symbol chart (simple)
  - **Recs pane**: candidate table (sortable by score)
  - **Details**: click a candidate to show evidence

### Candidate table columns
- Symbol
- Strategy
- Direction
- Entry / Stop / Target
- Score
- Valid until
- Why (first 1–2 bullets inline; full on click)

### Update behavior
- Quotes update live
- Bars update on close for selected TF
- Recommendations update on bar close + debounce (avoid flicker)

---

## Milestones (build in this order)

### M0 — Repo skeleton + canonical schema + dev harness
Deliverables:
- folder structure exists
- `core/` types defined
- `SimProvider` produces fake quotes/bars
- backend publishes market state + dummy candidates over WebSocket
- UI renders market + candidates side-by-side

Acceptance:
- run one command for backend, one for UI
- see live updating numbers and a sample candidate

### M1 — Market State Store + Engine loop
Deliverables:
- `MarketState` stores latest quotes + rolling bars
- evaluation scheduler triggers on bar close
- candidate store retains last N candidates + invalidation by timestamp

Acceptance:
- engine runs one dummy strategy consistently on bar close
- UI shows candidates updating only on bar close

### M2 — Futures provider integration (real data)
Deliverables:
- Implement `FuturesProviderV1` (choose one feasible source for futures data)
- Map provider symbols → canonical symbols
- Populate `ContractSpec` (tick size, multiplier) for supported futures

Acceptance:
- live ES/NQ quotes and 1m/5m bars populate state store
- quality flags show if data stream drops

### M3 — First real strategy (bars-only)
Deliverables:
- Implement one simple, robust futures strategy:
  - ORB (5m or 15m) OR trend pullback
- Candidate includes entry/stop/target and "why" bullets

Acceptance:
- tool produces candidates that make sense visually vs chart
- candidates expire appropriately (valid_until)

### M4 — Strategy modularity + configuration
Deliverables:
- strategy registry + dynamic loading
- per-strategy parameters from config
- enable/disable strategies without code change

Acceptance:
- add a new strategy file, enable it in config, see it in UI

### M5 — Ranking + throttling + journaling
Deliverables:
- scoring normalization (0–100)
- top-N filtering and per-strategy throttles
- journal recommendations and input features to SQLite

Acceptance:
- no alert flood; only top candidates show
- can inspect a stored record for "why this candidate appeared"

---

## Testing requirements (start early)
- Unit tests for:
  - tick normalization
  - bar-close scheduler logic
  - candidate validity/invalidation
  - symbol mapping
- Sim tests:
  - replay canned bar series through `SimProvider` and assert candidate triggers

---

## Open decisions (choose now; keep stable for V1)
1) Futures provider for V1:
   - pick one realistic source you can access for ES/NQ bars/quotes
2) Evaluation cadence:
   - default: **bar close** on 1m or 5m
3) First strategy:
   - ORB_5m (fast) vs ORB_15m (less noise) vs trend pullback

---

## Immediate next step (for Cursor)
Implement M0 with these tasks:
1) Create repo skeleton and `core/` canonical schema.
2) Implement `SimProvider` emitting Quote + Bar streams.
3) Implement `MarketState` and store updates.
4) Implement `Strategy` interface and one `DummyStrategy`.
5) Backend publishes:
   - `/ws` websocket for market updates and candidates
   - `/snapshot` REST for current state
6) UI shows split view: market + candidates.

Do not touch real providers until M0 is working end-to-end.
