# Thin Shell Integration Review

## 1. Executive assessment

- **Integration quality:** The thin shell is implemented and functional. ADR-001 documents decisions; API, UI, and path changes are in place.
- **Single-shell goal achieved:** One frontend (Backtester tab first, Observer second), one `make run`, root `runs/` for artifacts. The unified flow works.
- **Strongest aspects:** Clear separation (API invokes backtester via subprocess; no engine merge); root workflow is simple; CLI untouched; config path validation; PYTHONPATH isolation for subprocess.
- **Weakest aspects:** `make run` does not surface backend startup failures; direct `python -m src.runner` from `backtester/` still writes to `backtester/runs/`; no automated test for a successful UI backtest run.
- **Easier from scratch:** Yes. `make install`, `make build`, `make run` is a clear path. README Quick Start reflects this.
- **Shell thinness:** Acceptable. API is ~90 lines of orchestration; UI is presentation only; engines stay separate.

---

## 2. Validation checklist

| Area | Status | Evidence found | Notes |
|------|--------|----------------|-------|
| Root build/install flow | Pass | `make install` → venv + all deps; `make build` builds backtester, strategizer, portfolio, observer-backend, frontend | Coherent |
| Root run flow | Pass | `make run` starts backend in background, then frontend; README documents it | Backend failure not surfaced |
| Observer tab | Pass | `ObserverTab` wraps StatusBar, MarketPane, RecsPane; switches with Backtester | Unchanged behavior |
| Backtester tab | Pass | Config dropdown, Run button, result panel; API calls work | V1 scope |
| Config listing | Pass | `GET /api/backtester/configs` enumerates `backtester/configs/`; returns name, path, label | |
| Config run launch | Pass | `POST /api/backtester/runs` validates path, invokes runner subprocess, returns run_dir, report_path, summary_path | PYTHONPATH fix in place |
| Root runs output | Pass | Makefile passes `--output-dir REPO_ROOT`; API passes `--output-dir _REPO_ROOT`; output in `runs/` | Consistent |
| CLI still works | Pass | `make backtester-run` unchanged; writes to root `runs/` | |
| Docs alignment | Partial | README Quick Start, Common Commands, runs/showcase correct; backtester README "Or from backtester/" omits that direct run writes to `backtester/runs/` | Minor gap |
| Thin-shell separation | Pass | API wraps subprocess; no backtester engine code in observer; observer/backtester engines independent | |

---

## 3. Hardening gaps

| Gap | Severity | Why it matters | Smallest reasonable fix | Priority |
|-----|----------|----------------|-------------------------|----------|
| Backend startup failure invisible with `make run` | Medium | If OBSERVER_PROVIDER=schwab and creds fail, backend exits; frontend still starts; user gets connection refused with no hint | Add one-line note in README: "If `make run` shows connection errors, ensure OBSERVER_PROVIDER=sim (default) or valid Schwab creds." | Next |
| Direct backtester run writes to backtester/runs/ | Low | User running `python -m src.runner` from backtester/ gets `backtester/runs/`, not root. Inconsistent with docs. | Add sentence to backtester README: "From backtester/, output goes to backtester/runs/; use `make backtester-run` from repo root for root runs/." | Later |
| No automated test for successful POST run | Low | Manual verification only; regressions possible | Add `test_run_backtest_success` that POSTs a fixture-backed config and asserts ok=True, run_dir present | Later |
| ADR run_id format mismatch | Low | ADR says `{timestamp}_{config_stem}`; actual is `{timestamp}_{symbol}_{timeframe}_{start}_{end}` | Fix ADR line 16 to match reporter format | Later |

---

## 4. Top 3 risks introduced by the integration

### Risk 1: Backend startup failure leaves user stranded

**What:** `make run` starts backend in background; if provider (e.g. Schwab) fails during connect, backend exits. Frontend starts after 2s. User opens UI, sees connection refused on any API call.

**Evidence:** User reported connection refused when Schwab configured; worked with `OBSERVER_PROVIDER=sim`.

**Mitigation:** Add a single README note under Quick Start or Common Commands: if connection errors occur, check `OBSERVER_PROVIDER` and use `sim` for local dev. Do not add complex startup orchestration.

### Risk 2: Report link breaks if runs/ mount fails

**What:** Report link uses `/${result.report_path}` (e.g. `/runs/xxx/report.html`). Backend mounts `StaticFiles` only if `_runs_dir.exists()`. If repo is in a weird layout or path resolution is wrong, mount may not happen.

**Evidence:** Code at `app.py` lines 137–140: conditional mount. No explicit test that report links work end-to-end.

**Mitigation:** Low risk in normal layout. If issues arise, add a health-check style test or document that report links require backend to have repo root 4 levels up from `api/app.py`. No change needed now.

### Risk 3: Subprocess runner output parsing is brittle

**What:** API parses `result.stdout` for "Report written to: {path}". If runner changes its output format or adds progress lines, parsing could fail.

**Evidence:** `backtester.py` lines 130–132: `run_dir_line = result.stdout.strip().split("\n")[-1]` assumes last line has the path.

**Mitigation:** Runner is stable; format has been consistent. If runner is refactored, update API parsing. Consider having runner emit JSON to stdout for machine consumption (defer).

---

## 5. Most important hardening step

**Recommendation:** Add one short README note about `OBSERVER_PROVIDER` and connection errors.

**Why highest leverage:** Addresses the one user-reported failure mode (Schwab/connection refused). No code changes; minimal doc edit; improves clean-clone experience when env is misconfigured.

**Files affected:** [README.md](README.md)

**Success looks like:** A user who hits connection refused can find a one- or two-line note directing them to `OBSERVER_PROVIDER=sim` or valid Schwab setup.

**Avoid:** Adding startup checks, retries, or orchestration. Keep the note minimal.

---

## 6. Secondary hardening steps

1. **Clarify direct-run output path** — One sentence in backtester README: direct `python -m src.runner` from backtester/ writes to `backtester/runs/`; use `make backtester-run` for root `runs/`.
2. **Fix ADR run_id format** — Update ADR line 16 to match reporter: `{timestamp}_{symbol}_{timeframe}_{start}_{end}`.
3. **Add POST run success test** — Optional: test that POST with `buy_and_hold_example.yaml` returns ok=True and run_dir; skip or mark slow if needed.

---

## 7. What should remain intentionally out of scope

- Browser config editing
- Strategy authoring in UI
- Run history browser
- Artifact explorer beyond report link
- Queues / workers / async job system
- Merging observer and backtester engines
- Deeper monorepo restructuring (apps/, packages/)
- Production-grade error recovery or monitoring

---

## 8. Clean-clone test judgment

**Does this repository now provide a credible clean-clone experience for a reviewer or hiring manager? Why or why not?**

Yes, with one caveat. A clean clone can run `make install`, `make build`, `make run` and get a working UI with Backtester and Observer tabs. A fixture-backed config (e.g. `buy_and_hold_example`) runs from the UI without extra setup. The flagship TAA showcase is in `runs/showcase/` with CASE_STUDY. The caveat: if `.env` or `observer/.env` sets `OBSERVER_PROVIDER=schwab` with invalid creds, `make run` will show a frontend but API calls will fail. The fix (use `sim`) is simple but not yet documented. With `OBSERVER_PROVIDER=sim` or no override, the experience is credible.

---

## 9. Final answer

**If the owner only does one hardening task next, what should it be, and why?**

Add a one- or two-line note to the README about `OBSERVER_PROVIDER` and connection errors: if the UI shows connection refused, set `OBSERVER_PROVIDER=sim` (or ensure valid Schwab creds). This directly addresses the observed failure mode, requires no code changes, and improves usability for reviewers or hiring managers who hit env misconfiguration.
