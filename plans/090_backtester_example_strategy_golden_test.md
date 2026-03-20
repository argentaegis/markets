---
name: 090 Example Strategy + Golden Test
overview: "Red-Green-Refactor plan for Step 8 from 001: minimal example strategies, end-to-end golden dataset run with determinism assertions, and CLI runner."
todos: []
isProject: false
---

# 090: Example Strategy + Golden Test (Red-Green-Refactor)

Conforms to [001_mvp_implementation_roadmap.md](001_mvp_implementation_roadmap.md) Step 8, [000_options_backtester_mvp.md](000_options_backtester_mvp.md) sections 7 and 8.

---

## Objective

Deliver the final MVP step:

1. **Example strategies** -- a buy-and-hold and a buy-sell round-trip strategy that exercise the full pipeline (snapshot reading, order generation, position awareness, round-trip trades).
2. **Golden test** -- a deterministic end-to-end run against fixture data that produces known outputs. Any future change that alters behavior breaks the golden test, surfacing regressions.
3. **CLI runner** -- a `run_backtest_cli` entry point that wires config to engine to reporter so users can launch a backtest from the command line.

This completes the MVP acceptance criteria (000 section 7).

---

## Existing Foundation

| Artifact | Location | Usage |
|----------|----------|-------|
| `Strategy` ABC | `src/engine/strategy.py` | `on_step(snapshot, state_view) -> list[Order]` |
| `run_backtest` | `src/engine/engine.py` | Full A3 simulation loop |
| `generate_report` | `src/reporter/reporter.py` | Produces all 6 run artifacts |
| `BacktestConfig` | `src/domain/config.py` | Typed config with initial_cash, fee_config, fill_config |
| `LocalFileDataProvider` | `src/loader/provider.py` | Loads bars, quotes, metadata from fixture files |
| Fixture data | `src/loader/tests/fixtures/` | SPY 1d/1h/1m bars; option quotes for `SPY\|2026-01-17\|C\|480\|100` and `SPY\|2026-03-20\|C\|485\|100` |
| `--save-reports` | `tests/integration/conftest.py` | Toggle for persistent report output |

---

## New Concepts Introduced

### BuyAndHoldStrategy

Simplest strategy that exercises the pipeline. On the first step, buys one call option. Holds until run end. No round-trip trade -- tests position holding, mark-to-market, equity curve variation.

```python
class BuyAndHoldStrategy(Strategy):
    contract_id: str
    _bought: bool = False

    def on_step(self, snapshot, state_view) -> list[Order]:
        if self._bought:
            return []
        self._bought = True
        return [Order(id="entry-1", ts=snapshot.ts,
                      instrument_id=self.contract_id,
                      side="BUY", qty=1, order_type="market")]
```

### CoveredCallStrategy

Buy a call on step 1, sell it on step N. Produces a round-trip trade visible in trades.csv. Exercises realized P&L and trade-level analysis.

```python
class CoveredCallStrategy(Strategy):
    contract_id: str
    exit_step: int = 3
    _step: int = 0

    def on_step(self, snapshot, state_view) -> list[Order]:
        self._step += 1
        if self._step == 1:
            return [BUY order]
        if self._step == self.exit_step:
            return [SELL order]
        return []
```

### Golden Dataset

Frozen expected outputs from running a specific strategy + config against fixture data. Stored as JSON/CSV under `tests/golden/`. The golden test asserts exact match (tolerance for floats).

### CLI Runner

A `run_backtest_cli(config_path, output_dir)` function in `src/runner.py` that parses YAML/JSON config, builds objects, runs the backtest, and generates the report.

---

## Module Layout

```
src/
  strategies/
    __init__.py              # exports BuyAndHoldStrategy, CoveredCallStrategy
    buy_and_hold.py          # Phase 1
    covered_call.py          # Phase 2
    tests/
      __init__.py
      test_buy_and_hold.py   # Phase 1 tests
      test_covered_call.py   # Phase 2 tests
  runner.py                  # Phase 4 CLI entry point

tests/
  golden/
    expected_summary.json    # Phase 3 golden outputs
    expected_equity.csv
    expected_trades.csv
  integration/
    test_golden.py           # Phase 3 golden test
    test_example_strategies.py  # Phase 5 integration tests
```

---

## Implementation Phases

### Phase 1: BuyAndHoldStrategy

| Stage | Tasks |
|-------|-------|
| **Red** | Tests in `src/strategies/tests/test_buy_and_hold.py`: (1) `BuyAndHoldStrategy` is a `Strategy` subclass. (2) First `on_step` returns 1 BUY order with correct contract_id. (3) Second call returns empty list. (4) Order has `order_type="market"`, `side="BUY"`, `qty=1`. (5) `contract_id` is configurable via constructor. (6) Order `ts` matches snapshot `ts`. |
| **Green** | Implement `BuyAndHoldStrategy` in `src/strategies/buy_and_hold.py`. Constructor takes `contract_id`. Tracks `_bought` flag. |
| **Refactor** | Docstrings with reasoning. Export from `__init__.py`. |


### Phase 2: CoveredCallStrategy (buy + sell round-trip)

| Stage | Tasks |
|-------|-------|
| **Red** | Tests in `src/strategies/tests/test_covered_call.py`: (1) `CoveredCallStrategy` is a `Strategy` subclass. (2) Step 1: returns BUY order. (3) Steps 2 to exit_step-1: returns empty. (4) Step exit_step: returns SELL order. (5) Steps after exit_step: returns empty. (6) `exit_step` is configurable (default 3). (7) SELL qty matches BUY qty. (8) Order IDs are distinct ("entry-1" vs "exit-1"). |
| **Green** | Implement `CoveredCallStrategy` in `src/strategies/covered_call.py`. Constructor takes `contract_id` and `exit_step`. Tracks `_step` counter. |
| **Refactor** | Docstrings. Export from `__init__.py`. |


### Phase 3: Golden Test

| Stage | Tasks |
|-------|-------|
| **Red** | Tests in `tests/integration/test_golden.py` (details below). Generate expected golden outputs by running the backtest once and saving results. Tests assert match against saved golden files. |
| **Green** | Run strategies against fixture data. Capture outputs. Store as golden files. All golden tests pass by comparing live run against stored files. |
| **Refactor** | Add `--update-golden` pytest flag to regenerate golden files when intentional changes are made. Document in test docstrings. |

#### Golden Test Specifications

All tests use `@pytest.mark.integration` and the shared `provider` / `provider_config` fixtures.

| # | Test Name | Purpose |
|---|-----------|---------|
| 1 | `test_golden_buy_and_hold_summary` | BuyAndHoldStrategy: summary.json matches expected values (initial_cash, final_equity, num_trades=0, total_fees, num_steps). |
| 2 | `test_golden_covered_call_summary` | CoveredCallStrategy: summary.json matches expected values (num_trades=1, realized_pnl, total_return_pct). |
| 3 | `test_golden_covered_call_trades` | CoveredCallStrategy: trades.csv has exactly 1 row with expected entry_price, exit_price, side=LONG. |
| 4 | `test_golden_determinism` | Two identical CoveredCallStrategy runs produce byte-identical CSV/JSON output (A5). |
| 5 | `test_golden_equity_curve_values` | BuyAndHoldStrategy: equity curve values match expected golden values within tolerance (0.01). |
| 6 | `test_golden_invariants_hold` | Both strategies: no NaN in equity, all fills reference valid orders, portfolio equity == cash + positions. |
| 7 | `test_golden_with_fees` | CoveredCallStrategy with FeeModelConfig: total_fees matches expected, realized_pnl reduced by fees. |

#### Golden File Generation

Golden files are generated by a helper or pytest fixture:
1. Run backtest with known config + strategy + fixture data.
2. Save `summary.json`, `equity_curve.csv`, `trades.csv` to `tests/golden/`.
3. Tests load golden files and compare against live run output.

The `--update-golden` flag regenerates golden files when behavior changes intentionally.


### Phase 4: CLI Runner

| Stage | Tasks |
|-------|-------|
| **Red** | Tests in `tests/integration/test_runner.py`: (1) `run_backtest_cli(config_path, output_dir)` returns run directory path. (2) Given a valid YAML config, produces all 6 report files. (3) Invalid config file raises clear error. (4) Output directory is created if needed. |
| **Green** | Implement `run_backtest_cli` in `src/runner.py`. Parse config from YAML/JSON. Instantiate DataProvider and Strategy from config. Call `run_backtest`, then `generate_report`. |
| **Refactor** | Add `__main__.py` support for `python -m src.runner config.yaml`. Docstrings. |


### Phase 5: Integration Tests (after initial implementation)

Created **after** Phases 1-4 are green. Full end-to-end pipeline tests.

| Stage | Tasks |
|-------|-------|
| **Red** | Tests in `tests/integration/test_example_strategies.py` (details below). |
| **Green** | All integration tests pass with existing implementations. |
| **Refactor** | Shared helpers extracted; consistent assertion style. |

#### Integration Test Specifications

All tests use `@pytest.mark.integration` and shared fixtures.

| # | Test Name | Purpose |
|---|-----------|---------|
| 1 | `test_buy_and_hold_end_to_end` | BuyAndHoldStrategy: run_backtest + generate_report. All 6 files exist. fills.csv has 1 row (buy). trades.csv has 0 rows (no round-trip). Equity curve varies across steps. |
| 2 | `test_covered_call_end_to_end` | CoveredCallStrategy: run_backtest + generate_report. fills.csv has 2 rows. trades.csv has 1 row. summary.json shows realized_pnl != 0. |
| 3 | `test_covered_call_with_fees_end_to_end` | CoveredCallStrategy + FeeModelConfig. Fees deducted from both fills. summary.json total_fees > 0. |
| 4 | `test_report_files_human_readable` | With `--save-reports`: verify files written to `test_runs/`. CSV headers present, JSON parseable. |
| 5 | `test_all_invariants_across_strategies` | Both strategies: portfolio invariants hold at end (equity == cash + positions), no NaN, integer option qty. |

---

## Data Flow

```
config.yaml / BacktestConfig
    |
    v
run_backtest_cli (src/runner.py)
    |
    +-- BacktestConfig.from_dict(yaml)
    +-- LocalFileDataProvider(config)
    +-- Strategy (BuyAndHold or CoveredCall)
    |
    v
run_backtest (src/engine/engine.py)
    |
    v
BacktestResult
    |
    v
generate_report (src/reporter/reporter.py)
    |
    v
runs/{run_id}/
    equity_curve.csv, orders.csv, fills.csv,
    trades.csv, summary.json, run_manifest.json
    |
    v
Golden test comparison (tests/golden/ expected files)
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Two example strategies (buy-and-hold + covered-call) | Buy-and-hold tests position holding without round-trip; covered-call tests full trade lifecycle. Together they exercise all pipeline paths. |
| Golden files stored as JSON/CSV in `tests/golden/` | Human-readable, diffable, version-controlled. Changes to behavior show up in git diff. |
| `--update-golden` flag for regeneration | Intentional changes need a way to update expectations without manual editing. |
| Strategies in `src/strategies/` not `src/engine/` | Strategies are user-authored modules, not engine internals. Keeps engine focused on orchestration. |
| CLI runner as thin wrapper | `runner.py` only wires config to engine to reporter. No logic beyond parsing. Testable by calling the function directly. |
| YAML config for CLI | Human-friendly for interactive use. JSON also supported. BacktestConfig.from_dict handles both. |
| Golden comparison uses tolerance for floats | pytest.approx with tight tolerance (0.01) catches real regressions while tolerating machine epsilon. |
| Test strategies have fixed order IDs | Deterministic IDs ("entry-1", "exit-1") make golden file comparison straightforward. |

---

## pyproject.toml Update

Add `src/strategies/tests` to `testpaths`:

```toml
testpaths = ["src/domain/tests", "src/loader/tests", "src/marketdata/tests", "src/clock/tests", "src/portfolio/tests", "src/broker/tests", "src/engine/tests", "src/reporter/tests", "src/strategies/tests", "tests/integration"]
```

---

## Example Config File (for CLI)

```yaml
# example_config.yaml
symbol: SPY
start: "2026-01-02T14:31:00+00:00"
end: "2026-01-02T14:35:00+00:00"
timeframe_base: "1m"
initial_cash: 100000.0
seed: 42
strategy:
  name: covered_call
  contract_id: "SPY|2026-01-17|C|480|100"
  exit_step: 3
data_provider:
  underlying_path: "src/loader/tests/fixtures/underlying"
  options_path: "src/loader/tests/fixtures/options"
  timeframes_supported: ["1d", "1h", "1m"]
  missing_data_policy: "RETURN_PARTIAL"
  max_quote_age: null
fee_config:
  per_contract: 0.65
  per_order: 0.50
```

---

## Acceptance Criteria

- `BuyAndHoldStrategy` buys one option on first step, holds; exported from `src/strategies/`
- `CoveredCallStrategy` buys then sells after N steps; produces a round-trip trade
- Golden test files in `tests/golden/` with known expected outputs
- Golden tests assert exact or near-exact match against live runs (A5 determinism)
- `--update-golden` flag regenerates golden files for intentional changes
- CLI runner: `python -m src.runner config.yaml` runs backtest and writes reports
- Both strategies exercise full pipeline: engine to reporter to all 6 output files
- All phases follow Red to Green to Refactor
- Unit tests in `src/strategies/tests/`; golden + integration tests in `tests/integration/`
- Functions under 40 lines; line length under 120; reasoning docstrings
- This step completes MVP acceptance criteria (000 section 7)
