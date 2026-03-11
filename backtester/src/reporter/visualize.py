"""HTML report generator — interactive Plotly.js charts from run artifacts.

Reasoning: produces a self-contained report.html in the run directory.
Chart data is embedded as inline JSON; Plotly.js is loaded from CDN.
Zero Python dependencies beyond the standard library. The user opens
the file in any browser for interactive zoom/hover/pan.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


def _read_equity_curve(run_dir: Path) -> list[dict]:
    """Read equity_curve.csv into list of {ts, equity} dicts."""
    path = run_dir / "equity_curve.csv"
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def _read_trades(run_dir: Path) -> list[dict]:
    """Read trades.csv into list of dicts."""
    path = run_dir / "trades.csv"
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def _read_fills(run_dir: Path) -> list[dict]:
    """Read fills.csv into list of dicts."""
    path = run_dir / "fills.csv"
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def _read_summary(run_dir: Path) -> dict:
    """Read summary.json into dict."""
    path = run_dir / "summary.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _read_run_manifest(run_dir: Path) -> dict:
    """Read run_manifest.json into dict. Returns {} if missing."""
    path = run_dir / "run_manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _compute_drawdown(equity_data: list[dict]) -> list[dict]:
    """Compute peak-to-trough drawdown from equity curve data.

    Returns list of {ts, drawdown} where drawdown is <= 0 (negative means loss).
    """
    result = []
    peak = float("-inf")
    for row in equity_data:
        equity = float(row["equity"])
        if equity > peak:
            peak = equity
        dd = equity - peak
        result.append({"ts": row["ts"], "drawdown": dd})
    return result


def _format_asset_type(instrument_type: str) -> str:
    """Human label for instrument type: equity → Equity, option → Option, future → Future."""
    return instrument_type.capitalize() if instrument_type else ""


def _render_html(
    summary: dict,
    equity: list[dict],
    drawdown: list[dict],
    trades: list[dict],
    fills: list[dict],
    *,
    strategy_name: str = "",
    symbol: str = "",
    instrument_type: str = "",
) -> str:
    """Render the full HTML report string."""
    eq_ts = json.dumps([r["ts"] for r in equity])
    eq_values = json.dumps([float(r["equity"]) for r in equity])
    dd_ts = json.dumps([r["ts"] for r in drawdown])
    dd_values = json.dumps([r["drawdown"] for r in drawdown])

    initial_cash = summary.get("initial_cash", 0)
    fill_ts = json.dumps([r["ts"] for r in fills])
    fill_prices_text = json.dumps([f"Fill: ${float(r['fill_price']):.2f} x {r['fill_qty']}" for r in fills])

    # Map fill timestamps to equity values for marker placement
    eq_by_ts = {r["ts"]: float(r["equity"]) for r in equity}
    fill_eq = []
    for f in fills:
        fill_eq.append(eq_by_ts.get(f["ts"], initial_cash))
    fill_eq_json = json.dumps(fill_eq)

    # Trade P&L chart (only if trades exist)
    trade_chart_html = ""
    if trades:
        def _trade_label(r: dict) -> str:
            base = f"{r['instrument_id']} ({r['side']})"
            return f"{base} (Open)" if str(r.get("is_open", "")).lower() == "true" else base

        trade_labels = json.dumps([_trade_label(r) for r in trades])
        trade_pnl = json.dumps([float(r["realized_pnl"]) for r in trades])

        def _trade_color(r: dict) -> str:
            if str(r.get("is_open", "")).lower() == "true":
                return "#95a5a6"  # neutral gray for open positions (unrealized)
            return "#2ecc71" if float(r["realized_pnl"]) > 0 else "#e74c3c"

        trade_colors = json.dumps([_trade_color(r) for r in trades])
        trade_chart_html = f"""
    <h2>Trade P&L</h2>
    <div id="trade-pnl"></div>
    <script>
      Plotly.newPlot('trade-pnl', [{{
        x: {trade_labels},
        y: {trade_pnl},
        type: 'bar',
        marker: {{ color: {trade_colors} }}
      }}], {{
        margin: {{ t: 20, b: 60, l: 70, r: 30 }},
        yaxis: {{ title: 'P&L ($)' }},
        paper_bgcolor: '#1e1e2f',
        plot_bgcolor: '#1e1e2f',
        font: {{ color: '#e0e0e0' }}
      }}, {{ responsive: true }});
    </script>
"""

    # Report title: strategy_name — symbol (instrument_type) or "Backtest Report" if no strategy
    if strategy_name:
        mid = f" — {symbol}" if symbol else ""
        suffix = f" ({_format_asset_type(instrument_type)})" if instrument_type else ""
        report_title = f"{strategy_name}{mid}{suffix}"
    else:
        report_title = "Backtest Report"

    # Summary table rows
    def _fmt_pct(val: float) -> str:
        return f"{val * 100:.2f}%"

    def _fmt_dollar(val: float) -> str:
        return f"${val:,.2f}"

    metadata_rows = ""
    if strategy_name or symbol or instrument_type:
        metadata_rows = """
        <tr><td>Strategy</td><td>""" + (strategy_name or "—") + """</td></tr>
        <tr><td>Symbol</td><td>""" + (symbol or "—") + """</td></tr>
        <tr><td>Asset Type</td><td>""" + (_format_asset_type(instrument_type) or "—") + """</td></tr>
"""

    num_open = sum(1 for r in trades if str(r.get("is_open", "")).lower() == "true") if trades else 0
    trades_suffix = f" / {num_open} open" if num_open else ""

    summary_rows = metadata_rows + f"""
        <tr><td>Initial Cash</td><td>{_fmt_dollar(summary.get('initial_cash', 0))}</td></tr>
        <tr><td>Final Equity</td><td>{_fmt_dollar(summary.get('final_equity', 0))}</td></tr>
        <tr><td>Total Return</td><td>{_fmt_pct(summary.get('total_return_pct', 0))}</td></tr>
        <tr><td>Max Drawdown</td><td>{_fmt_dollar(summary.get('max_drawdown', 0))} ({_fmt_pct(summary.get('max_drawdown_pct', 0))})</td></tr>
        <tr><td>Trades</td><td>{summary.get('num_trades', 0)} (W: {summary.get('num_winning', 0)} / L: {summary.get('num_losing', 0)}){trades_suffix}</td></tr>
        <tr><td>Win Rate</td><td>{_fmt_pct(summary.get('win_rate', 0))}</td></tr>
        <tr><td>Total Fees</td><td>{_fmt_dollar(summary.get('total_fees', 0))}</td></tr>
        <tr><td>Period</td><td>{summary.get('start', '')} to {summary.get('end', '')}</td></tr>
        <tr><td>Steps</td><td>{summary.get('num_steps', 0)}</td></tr>
        {f'<tr><td>Run Time</td><td>{summary["elapsed_seconds"]:.2f}s</td></tr>' if summary.get('elapsed_seconds') is not None else ''}
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{report_title}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1e1e2f; color: #e0e0e0; padding: 24px; }}
    h1 {{ font-size: 1.5rem; margin-bottom: 16px; color: #fff; }}
    h2 {{ font-size: 1.1rem; margin: 24px 0 8px 0; color: #ccc; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 500px; margin-bottom: 16px; }}
    td {{ padding: 6px 12px; border-bottom: 1px solid #333; }}
    td:first-child {{ color: #aaa; }}
    td:last-child {{ text-align: right; font-weight: 600; }}
  </style>
</head>
<body>
  <h1>{report_title}</h1>

  <h2>Summary</h2>
  <table>
    {summary_rows}
  </table>

  <h2>Equity Curve</h2>
  <div id="equity-curve"></div>
  <script>
    Plotly.newPlot('equity-curve', [
      {{
        x: {eq_ts},
        y: {eq_values},
        type: 'scatter',
        mode: 'lines',
        name: 'Equity',
        line: {{ color: '#3498db', width: 2 }}
      }},
      {{
        x: {eq_ts},
        y: Array({len(equity)}).fill({initial_cash}),
        type: 'scatter',
        mode: 'lines',
        name: 'Initial Cash',
        line: {{ color: '#555', width: 1, dash: 'dot' }}
      }},
      {{
        x: {fill_ts},
        y: {fill_eq_json},
        type: 'scatter',
        mode: 'markers',
        name: 'Fills',
        marker: {{ color: '#e67e22', size: 10, symbol: 'triangle-up' }},
        text: {fill_prices_text},
        hoverinfo: 'text+x'
      }}
    ], {{
      margin: {{ t: 20, b: 40, l: 70, r: 30 }},
      yaxis: {{ title: 'Equity ($)' }},
      xaxis: {{ title: '' }},
      legend: {{ x: 0, y: 1.12, orientation: 'h' }},
      paper_bgcolor: '#1e1e2f',
      plot_bgcolor: '#1e1e2f',
      font: {{ color: '#e0e0e0' }}
    }}, {{ responsive: true }});
  </script>

  <h2>Drawdown</h2>
  <div id="drawdown"></div>
  <script>
    Plotly.newPlot('drawdown', [{{
      x: {dd_ts},
      y: {dd_values},
      type: 'scatter',
      fill: 'tozeroy',
      fillcolor: 'rgba(231, 76, 60, 0.3)',
      line: {{ color: '#e74c3c', width: 1 }},
      name: 'Drawdown'
    }}], {{
      margin: {{ t: 20, b: 40, l: 70, r: 30 }},
      yaxis: {{ title: 'Drawdown ($)' }},
      paper_bgcolor: '#1e1e2f',
      plot_bgcolor: '#1e1e2f',
      font: {{ color: '#e0e0e0' }}
    }}, {{ responsive: true }});
  </script>

  {trade_chart_html}
</body>
</html>
"""


def generate_html_report(run_dir: Path) -> Path:
    """Read CSVs/JSON from run_dir, produce run_dir/report.html.

    Reasoning: single entry point for HTML report generation. Reads all
    artifacts, computes drawdown, renders HTML with embedded Plotly.js charts.
    Strategy metadata from run_manifest.json used for title and summary rows.
    Returns path to the created report.html.
    """
    equity = _read_equity_curve(run_dir)
    trades = _read_trades(run_dir)
    fills = _read_fills(run_dir)
    summary = _read_summary(run_dir)
    drawdown = _compute_drawdown(equity)
    manifest = _read_run_manifest(run_dir)
    config = manifest.get("config") or {}
    strategy_name = str(config.get("strategy_name", ""))
    symbol = str(config.get("symbol", ""))
    instrument_type = str(config.get("instrument_type", ""))

    html = _render_html(
        summary, equity, drawdown, trades, fills,
        strategy_name=strategy_name, symbol=symbol, instrument_type=instrument_type,
    )
    out = run_dir / "report.html"
    out.write_text(html)
    return out
