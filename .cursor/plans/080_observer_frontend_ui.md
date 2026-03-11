---
name: 080 Frontend UI
overview: "Build the React + Vite + TypeScript + MUI dashboard: split-view with market pane (watchlist + quotes), recommendations pane (candidate table), and details panel. WebSocket connection to backend."
todos: []
isProject: false
---

# 080: Frontend UI (React + Vite + TS + MUI)

Conforms to [000_observer_mvp_initial_plan.md](000_observer_mvp_initial_plan.md) §ui/ and §UI requirements.

---

## Project Practice: Manual Verification

This step deviates from the backend's Red-Green-Refactor pattern. Frontend components are manually verified in the browser rather than unit-tested. Rationale: V1 UI is a thin display layer over backend data — the backend pipeline (provider → state → engine → API) is thoroughly tested in steps 020–070. Adding Vitest/React Testing Library is deferred until the UI stabilizes.

---

## Objective

Build a single dashboard showing **market data + recommendations** simultaneously. The UI connects to the backend `/ws` WebSocket for live updates and `/api/snapshot` for initial state. This is the M0 user-facing deliverable.

---

## Existing Foundation

- Step 010: frontend scaffold (React + Vite + TS + MUI, `package.json`, `vite.config.ts`, `main.tsx`, `App.tsx`)
- Step 070: backend API running with `/ws`, `/api/snapshot`, `/api/health`
- `main.tsx` already has `ThemeProvider` + `CssBaseline` with inline `createTheme()` — will be updated to import from `theme.ts`
- `App.tsx` currently uses `Container maxWidth="lg"` — will be replaced with full-width layout

---

## Layout (from 000 §UI requirements)

```
+------------------------------------------------------+
|  Market Observer                           [status]   |
+---------------------------+--------------------------+
|  MARKET PANE (left)       |  RECOMMENDATIONS (right) |
|                           |                          |
|  Watchlist Table:         |  Candidate Table:        |
|  Symbol | Last | Bid/Ask  |  Symbol | Strategy |     |
|  ES     | 5412 | 11/12   |  Direction | Entry |     |
|  NQ     | 18900| 99/01   |  Stop | Target | Score | |
|                           |  Valid Until | Why       |
|  [selected symbol chart]  |                          |
|                           +--------------------------+
|                           |  DETAILS PANEL           |
|                           |  (click candidate)       |
|                           |  - Full explain bullets  |
|                           |  - Entry/Stop/Target     |
|                           |  - Tags                  |
+---------------------------+--------------------------+
```

---

## Module Layout

```
frontend/src/
  main.tsx                  # React entry point (update: import theme from theme.ts)
  App.tsx                   # Root component with full-width split layout
  theme.ts                  # MUI theme customization
  components/
    MarketPane/
      MarketPane.tsx        # Left pane container
      WatchlistTable.tsx    # Symbol | Last | Bid | Ask | Volume
    RecsPane/
      RecsPane.tsx          # Right pane container
      CandidateTable.tsx    # Candidate table (sortable)
      CandidateDetail.tsx   # Expanded detail view
    StatusBar/
      StatusBar.tsx         # Connection status indicator
  hooks/
    useWebSocket.ts         # WebSocket connection + message handling
    useMarketData.ts        # State management for quotes/bars
    useCandidates.ts        # State management for candidates
  types/
    market.ts               # Quote, Bar, DataQuality (matching backend serializers)
    candidate.ts            # TradeCandidate, Direction, EntryType
    ws.ts                   # WsMessage discriminated union
  api/
    snapshot.ts             # REST client for /api/snapshot

frontend/vite.config.ts      # Updated: add proxy for /api and /ws → localhost:8000
```

---

## Implementation Phases

### Phase 0: Directory setup + Vite proxy (Create+Verify)

| Stage | Tasks |
|-------|-------|
| **Create** | Create directories: `frontend/src/components/MarketPane/`, `RecsPane/`, `StatusBar/`, `hooks/`, `types/`, `api/`. Update `vite.config.ts` to add dev server proxy: `/api` → `http://localhost:8000`, `/ws` → `ws://localhost:8000` (WebSocket upgrade). |
| **Verify** | `npm run dev` starts without errors. Proxy works: open `http://localhost:5173/api/health` in browser while backend is running → returns JSON. |

#### Vite proxy config

```typescript
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/ws': { target: 'ws://localhost:8000', ws: true },
  },
},
```

Note: With the proxy, all frontend code uses **relative URLs** (`/api/snapshot`, `/ws`) — no hardcoded `localhost:8000`.

### Phase 1: TypeScript types + API client

| Stage | Tasks |
|-------|-------|
| **Green** | Define TypeScript interfaces in `types/` matching backend serializer output exactly. Implement `api/snapshot.ts`: `fetchSnapshot()` → `GET /api/snapshot`. |

#### Exact type shapes (must match `api/serializers.py` output)

`types/market.ts`:
```typescript
type DataQuality = "OK" | "STALE" | "MISSING" | "PARTIAL";

interface Quote {
  symbol: string;
  bid: number;
  ask: number;
  last: number;
  bid_size: number;
  ask_size: number;
  volume: number;
  timestamp: string;  // ISO 8601
  source: string;
  quality: DataQuality;
}

interface Bar {
  symbol: string;
  timeframe: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  timestamp: string;  // ISO 8601
  source: string;
  quality: DataQuality;
}
```

`types/candidate.ts`:
```typescript
type Direction = "LONG" | "SHORT";
type EntryType = "MARKET" | "LIMIT" | "STOP";

interface TradeCandidate {
  id: string;
  symbol: string;
  strategy: string;
  direction: Direction;
  entry_type: EntryType;
  entry_price: number;
  stop_price: number;
  targets: number[];
  score: number;
  explain: string[];
  valid_until: string;  // ISO 8601
  tags: Record<string, string>;
  created_at: string;   // ISO 8601
}
```

`types/ws.ts` — discriminated union for WebSocket envelope:
```typescript
type WsMessage =
  | { type: "quote_update"; data: Quote }
  | { type: "bar_update"; data: Bar }
  | { type: "candidates_update"; data: TradeCandidate[] };
```

`types/snapshot.ts`:
```typescript
interface SnapshotResponse {
  quotes: Record<string, Quote>;
  bars: Record<string, Record<string, Bar[]>>;
  candidates: TradeCandidate[];
}
```

Key: timestamps are `string` (ISO 8601), not `Date`. Enums are string literal unions. Field names use snake_case matching the backend JSON.

### Phase 2: App shell + theme + status bar

| Stage | Tasks |
|-------|-------|
| **Green** | Create `theme.ts`: MUI `createTheme()` with dashboard-appropriate defaults (dense spacing, monospace for numbers). Update `main.tsx` to `import { theme } from './theme'` (replace inline `createTheme()`). Rewrite `App.tsx`: full-width `Box` layout (no `Container maxWidth`) with MUI Grid — left pane (40%) and right pane (60%). Use placeholder `Typography` elements in each pane for now. Add `StatusBar.tsx` at top with hardcoded "Connecting..." text. |
| **Verify** | `npm run dev` → browser shows split-pane skeleton with status bar. |

### Phase 3: WebSocket hook

| Stage | Tasks |
|-------|-------|
| **Green** | Implement `hooks/useWebSocket.ts`: connect to `/ws` (relative URL, proxy handles routing). Parse incoming `WsMessage` by `type` field. Expose `{ status, lastMessage }` where `status` is `"connecting" \| "connected" \| "disconnected"`. Reconnect on disconnect with exponential backoff (initial 1s, max 30s, doubles each attempt, reset on successful connection). |
| **Verify** | Wire into `App.tsx` temporarily — status bar shows "Connected" when backend is running. Stop backend → shows "Disconnected". Restart → reconnects within backoff window. |

#### Reconnection behavior

- Initial delay: **1 second**
- Backoff: **double** each attempt (1s → 2s → 4s → 8s → 16s → 30s cap)
- Max delay: **30 seconds**
- Reset: delay returns to 1s on successful `onopen`
- On reconnect: caller should re-fetch `/api/snapshot` to sync any missed updates (WebSocket only sends incremental updates — gaps during disconnection leave stale state)

### Phase 4: Market data + candidate state hooks

| Stage | Tasks |
|-------|-------|
| **Green** | Implement `hooks/useMarketData.ts`: `useMarketData(ws)` — maintains `quotes: Record<string, Quote>` and `bars: Record<string, Record<string, Bar[]>>`. Updates from `quote_update`/`bar_update` messages. Initializes from `SnapshotResponse` on mount and on reconnect. |
| **Green** | Implement `hooks/useCandidates.ts`: `useCandidates(ws)` — maintains `candidates: TradeCandidate[]` and `selectedId: string \| null`. Replaces full array on `candidates_update`. Initializes from snapshot. Exposes `select(id)` and `selectedCandidate`. |
| **Verify** | Add temporary `JSON.stringify` debug output in each pane of `App.tsx` to confirm data is flowing. |

### Phase 5: Market Pane (left)

| Stage | Tasks |
|-------|-------|
| **Green** | Implement `MarketPane.tsx` (container) and `WatchlistTable.tsx`: MUI Table with columns: Symbol, Last, Bid, Ask, Volume. Rows update live from `useMarketData`. Brief flash (green for price up, red for price down) via CSS transition on `last` price change. |
| **Refactor** | Memoize table rows (`React.memo`) to prevent unnecessary rerenders from other state changes. |

### Phase 6: Recommendations Pane (right)

| Stage | Tasks |
|-------|-------|
| **Green** | Implement `RecsPane.tsx` (container), `CandidateTable.tsx`, and `CandidateDetail.tsx`. Table columns per 000 §Candidate table columns: Symbol, Strategy, Direction, Entry/Stop/Target, Score, Valid Until, Why (first 1–2 bullets inline). Sortable by Score. Clickable rows set `selectedId`. |
| **Green** | `CandidateDetail.tsx`: Card/Paper below table showing full `explain` bullets, entry/stop/target prices, tags, created_at. Visible when a candidate is selected. |
| **Refactor** | Handle empty state ("No active candidates" message). Handle deselect (click again or click away). |

### Phase 7: Polish + integration

| Stage | Tasks |
|-------|-------|
| **Green** | Wire `StatusBar.tsx` to real WebSocket status from `useWebSocket`. Show green dot + "Connected", yellow + "Reconnecting...", red + "Disconnected". Update `App.tsx` to compose all components (remove debug output). |
| **Refactor** | Polish spacing, typography, number formatting (tick-aligned decimals for prices). Ensure full pipeline works end-to-end: start backend → start frontend → see live data flowing. |

---

## Update Behavior (from 000 §Update behavior)

- Quotes update live (every WebSocket quote_update message)
- Bars update on close for selected timeframe
- Recommendations update on bar close (from candidates_update messages)
- No flicker: candidate table only rerenders on candidates_update, not on every tick

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| State management | React hooks (useState/useReducer) | Simple enough for V1; no Redux needed |
| WebSocket reconnection | Exponential backoff (1s–30s) | Resilient to backend restarts during dev; re-fetch snapshot on reconnect to fill gaps |
| Table library | MUI Table | Already using MUI; consistent styling |
| Chart library | Deferred to later | M0 focus is data + candidates; mini chart is nice-to-have |
| Price flash | Brief CSS transition on value change | Visual feedback without external library |
| Vite proxy | `/api` and `/ws` → `localhost:8000` | Frontend uses relative URLs; no hardcoded backend host; works for dev; production will use reverse proxy |
| Timestamps as strings | TS types use `string` (ISO 8601) | Parse on display only; avoids unnecessary `Date` construction on every WebSocket tick |
| Snake_case field names | Match backend JSON exactly | No camelCase conversion layer; keeps types trivially verifiable against backend serializers |
| Full-width layout | `Box` instead of `Container maxWidth` | Dashboard needs horizontal space for two panes; `Container` caps at ~1200px |
| No frontend tests in V1 | Manual browser verification | UI is thin display layer; backend pipeline is thoroughly tested; Vitest deferred until UI stabilizes |

---

## Acceptance Criteria

- [ ] `npm run dev` starts without errors
- [ ] Vite proxy works: `/api/health` returns backend JSON via `localhost:5173`
- [ ] App renders full-width split-view layout with Market Pane (left ~40%) and Recs Pane (right ~60%)
- [ ] Watchlist table shows live-updating quotes (Symbol, Last, Bid, Ask, Volume)
- [ ] Price changes flash green (up) or red (down) briefly
- [ ] Candidate table shows all columns from 000 §Candidate table columns
- [ ] Candidate table is sortable by Score
- [ ] Clicking a candidate row shows detail panel with full explain bullets, prices, tags
- [ ] Status bar shows connection status: Connected (green) / Disconnected (red) / Reconnecting (yellow)
- [ ] Reconnects automatically if backend restarts (exponential backoff 1s–30s)
- [ ] Re-fetches `/api/snapshot` on reconnect to sync missed updates
- [ ] Initializes from `/api/snapshot` on page load
- [ ] Empty state handled: "No active candidates" message when none exist
- [ ] No hardcoded `localhost:8000` in frontend source — all URLs relative

---

## Manual Verification

```bash
# Terminal 1: start backend
cd backend && PYTHONPATH=src uvicorn api.app:create_app --factory --reload

# Terminal 2: start frontend
cd frontend && npm run dev
```

1. Open browser to `http://localhost:5173`
2. Verify: status bar shows "Connected" (green)
3. Verify: quotes updating live in watchlist (prices ticking)
4. Verify: price flashes green/red on change
5. Verify: candidate table shows DummyStrategy candidates after bar close
6. Verify: clicking a candidate row shows detail panel with explain bullets + prices + tags
7. Verify: sort candidates by Score column
8. Verify: `http://localhost:5173/api/health` returns backend JSON (proxy working)
9. Verify: stop backend → status bar shows "Disconnected" (red) → restart → shows "Reconnecting..." (yellow) → "Connected" (green)
10. Verify: after reconnect, data is current (snapshot re-fetched)

---

## Out of Scope

- Mini chart for selected symbol (nice-to-have, not M0)
- Dark/light mode toggle (can use system preference)
- Mobile responsive layout
- User preferences / saved layouts
- Authentication
