---
name: 140 Refresh Time Indicator
overview: "Add a subtle MUI LinearProgress bar beneath the StatusBar that shows time elapsed since the last WebSocket message, giving visual feedback that data is flowing."
todos: []
isProject: false
---

# 140: Refresh Time Indicator

Conforms to [000_observer_mvp_initial_plan.md](000_observer_mvp_initial_plan.md) §ui/ display goals.

---

## Concept

A thin MUI `LinearProgress` bar sits directly beneath the existing StatusBar. It starts at `value={100}` on each incoming WebSocket message and animates down to `0` over ~2 seconds via a CSS `@keyframes` override. This gives a constant, understated visual pulse that data is flowing — without text, numbers, or extra UI chrome.

When connected and receiving data, the bar pulses rhythmically. If messages stop (disconnect/stall), the bar stays at 0% — a subtle visual cue that data has stopped.

## Behavior

- **On each WebSocket message**: bar resets to 100% via React `key` remount
- **Over the next ~2 seconds**: bar shrinks to 0% via CSS keyframe animation on the inner `.MuiLinearProgress-bar` element
- **Color**: inherits MUI theme `primary` color (consistent with app theme)
- **Height**: 2px — visible but unobtrusive
- **Duration**: ~2 seconds (quotes arrive every 0.1s with SimProvider, so the bar will appear nearly full at all times; with Schwab polling it will pulse more visibly)

## Implementation

### Files to change

- `frontend/src/hooks/useWebSocket.ts` — expose a `lastMessageAt` counter
- `frontend/src/components/StatusBar/StatusBar.tsx` — add `LinearProgress` below the AppBar
- `frontend/src/App.tsx` — pass `lastMessageAt` through to StatusBar
- `.cursor/rules/prefer-library-components.mdc` — new rule

### No new dependencies

Uses MUI `LinearProgress` (already available via `@mui/material`). No timers, no `requestAnimationFrame`, no new packages.

## Acceptance Criteria

- [ ] MUI `LinearProgress` bar visible beneath the StatusBar (2px height)
- [ ] Bar resets to full on each WebSocket message
- [ ] Bar shrinks to 0% over ~2 seconds
- [ ] No visible performance impact (CSS animation only, no JS loops)
- [ ] Existing tests unaffected
- [ ] New cursor rule for preferring library components

## Manual Verification

1. Start backend: `make backend`
2. Start frontend: `make frontend`
3. Open `http://localhost:5173`
4. Observe thin progress bar beneath the "Market Observer" header — it should pulse continuously as quotes stream in
5. Kill the backend — bar should stop at 0% and not reset
6. Restart backend — bar resumes pulsing when WebSocket reconnects
