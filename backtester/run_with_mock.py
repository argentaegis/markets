#!/usr/bin/env python3
"""Run backtest (strategizer runs in-process, no HTTP service required).

Usage: python run_with_mock.py <config.yaml> [--output-dir DIR]

Note: Alias for src.runner. Use: python -m src.runner <config.yaml> [--output-dir DIR]
"""
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.runner import run_backtest_cli

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_with_mock.py <config.yaml> [--output-dir DIR]")
        sys.exit(1)

    config_path = Path(sys.argv[1])
    output_dir = Path(".")
    if "--output-dir" in sys.argv:
        idx = sys.argv.index("--output-dir")
        if idx + 1 < len(sys.argv):
            output_dir = Path(sys.argv[idx + 1])

    run_dir = run_backtest_cli(config_path, output_dir)
    print(f"Report written to: {run_dir}")
