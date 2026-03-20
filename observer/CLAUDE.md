# Claude Code — Observer Sub-project

See the root [CLAUDE.md](../CLAUDE.md) for all project-wide standards (code standards, workflow, test-first, secrets policy, etc.). This file covers observer-specific context only.

## Observer Architecture

**Backend** (`observer/backend/`): FastAPI + uvicorn, WebSocket-based live data streaming, SQLite journal.
**Frontend** (`observer/frontend/`): React 19 + TypeScript + MUI 7 + Vite.

```
make observer-backend       # start API at http://localhost:8000
make observer-frontend      # start dev server at http://localhost:5173
make run                    # start both together
```

## Frontend: Prefer MUI Components

The frontend uses **MUI / Material UI**. Always use its component catalog before building custom elements. See root CLAUDE.md for examples.

## Test Locations

- Backend: `observer/backend/tests/`
- Frontend: lint via `make observer-frontend-lint` (`npm run lint`)

## Manual Verification for Observer

Concrete checks after any backend change:
```
curl http://localhost:8000/api/health
```
Concrete checks after any frontend change:
```
Open http://localhost:5173 and inspect the specific component in the browser
```
