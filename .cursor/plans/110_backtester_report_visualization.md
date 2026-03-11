# 110: Interactive HTML Report with Plotly.js

## Approach

`report.html` is generated as a standard artifact inside `generate_report`, alongside the CSVs and JSON files. No separate flag -- it's just part of the report. When `--save-reports` persists the run directory for human review, the HTML is already there to open in a browser.

The HTML embeds chart data as inline JSON and loads Plotly.js from CDN. Zero new Python dependencies -- pure string templating. Interactive zoom/hover/pan out of the box.

## Report Layout

The HTML page contains four sections stacked vertically:

1. **Summary Card** -- key metrics table (return, drawdown, win rate, fees, trade count) from `summary.json`
2. **Equity Curve** -- interactive line chart from `equity_curve.csv`, with initial cash reference line and fill markers from `fills.csv`
3. **Drawdown** -- area chart (filled red) derived from equity curve peak-to-trough
4. **Trade P&L** -- bar chart of per-trade `realized_pnl` from `trades.csv`, colored green (win) / red (loss); hidden if no trades

## File Changes

### New file: `src/reporter/visualize.py`

Single public function:

```python
def generate_html_report(run_dir: Path) -> Path:
    """Read CSVs/JSON from run_dir, produce run_dir/report.html."""
```

Internally:
- `_read_equity_curve(run_dir)` -> list of `{ts, equity}` dicts
- `_read_trades(run_dir)` -> list of `{instrument_id, realized_pnl, ...}` dicts
- `_read_fills(run_dir)` -> list of `{ts, fill_price, ...}` dicts
- `_read_summary(run_dir)` -> dict from summary.json
- `_compute_drawdown(equity_data)` -> list of `{ts, drawdown}` dicts
- `_render_html(summary, equity, drawdown, trades, fills)` -> HTML string

The HTML template is a multi-line Python string with `{placeholders}` for JSON data. Plotly.js loaded via `<script src="https://cdn.plot.ly/plotly-2.35.2.min.js">`.

### Modified: `src/reporter/reporter.py`

At the end of `generate_report`, call:

```python
from src.reporter.visualize import generate_html_report
generate_html_report(run_dir)
```

### New test: `src/reporter/tests/test_visualize.py`

- `test_html_report_created` -- write minimal CSVs + summary.json to tmp_path, call `generate_html_report`, assert `report.html` exists
- `test_html_contains_plotly_script` -- verify `<script` and `Plotly.newPlot` appear in output
- `test_html_contains_summary_values` -- verify key metrics from summary.json appear in the HTML text
- `test_drawdown_computation` -- unit test `_compute_drawdown` returns correct peak-to-trough values
- `test_empty_trades_no_trade_chart` -- verify trade chart section is omitted when trades.csv is header-only

### Modified: integration tests that check `ALL_FILES`

All tests that assert the exact set of 6 output files need updating to expect 7 (adding `report.html`):
- `tests/integration/test_example_strategies.py`
- `tests/integration/test_underlying_strategy.py`

## No New Dependencies

The HTML is generated via Python string formatting. Plotly.js is loaded from CDN at view time. No `pip install` needed.
