"""Thin backtester API — list configs and launch runs.

V1: GET /api/backtester/configs, POST /api/backtester/runs.
Config path validation: only allow configs from backtester/configs/.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Repo root: observer/backend/src/api/backtester.py -> 4 levels up (api, src, backend, observer)
_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONFIGS_DIR = _REPO_ROOT / "backtester" / "configs"
_ALLOWED_SUFFIXES = (".yaml", ".yml", ".json")

router = APIRouter()


def _list_configs() -> list[dict[str, str]]:
    """List runnable config files from backtester/configs/."""
    if not _CONFIGS_DIR.exists():
        return []
    configs = []
    for p in sorted(_CONFIGS_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in _ALLOWED_SUFFIXES:
            rel_path = f"backtester/configs/{p.name}"
            configs.append({
                "name": p.stem,
                "path": rel_path,
                "label": p.name,
            })
    return configs


def _resolve_config_path(config_path: str) -> Path:
    """Resolve and validate config path. Raises ValueError if invalid."""
    # Normalize: allow backtester/configs/foo.yaml or configs/foo.yaml
    path_str = config_path.strip().replace("\\", "/")
    if path_str.startswith("backtester/configs/"):
        stem = path_str[len("backtester/configs/"):]
    elif path_str.startswith("configs/"):
        stem = path_str[len("configs/"):]
    else:
        raise ValueError("Config path must be under backtester/configs/")

    # Guard against traversal
    if ".." in stem or stem.startswith("/"):
        raise ValueError("Path traversal not allowed")

    resolved = _CONFIGS_DIR / stem
    resolved = resolved.resolve()
    if not resolved.is_file():
        raise ValueError(f"Config not found: {stem}")
    if not resolved.is_relative_to(_CONFIGS_DIR.resolve()):
        raise ValueError("Config must be under backtester/configs/")

    return resolved


@router.get("/api/backtester/configs")
async def get_configs() -> dict:
    """List available backtester configs."""
    configs = _list_configs()
    return {"configs": configs}


class RunRequest(BaseModel):
    config_path: str


@router.post("/api/backtester/runs")
async def run_backtest(req: RunRequest) -> dict:
    """Launch a backtest for the selected config. Synchronous in V1."""
    try:
        resolved = _resolve_config_path(req.config_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Config name for run dir
    config_stem = resolved.stem
    # Path relative to backtester cwd
    config_rel = f"configs/{resolved.name}"

    # Run from backtester dir so data/catalog.yaml etc resolve.
    # Use clean env so observer's PYTHONPATH=src does not shadow backtester imports.
    backtester_dir = _REPO_ROOT / "backtester"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(backtester_dir)

    python = sys.executable
    cmd = [
        python,
        "-m",
        "src.runner",
        config_rel,
        "--output-dir",
        str(_REPO_ROOT),
        "--silent",
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(backtester_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Backtest timed out",
        ) from None

    if result.returncode != 0:
        err = result.stderr or result.stdout or "Unknown error"
        raise HTTPException(
            status_code=500,
            detail=f"Backtest failed: {err[:500]}",
        ) from None

    # Parse output: "Report written to: /path/to/runs/20260316_123456_..."
    run_dir_line = result.stdout.strip().split("\n")[-1] if result.stdout else ""
    prefix = "Report written to: "
    if run_dir_line.startswith(prefix):
        run_dir_abs = run_dir_line[len(prefix):].strip()
        run_dir = Path(run_dir_abs)
    else:
        raise HTTPException(
            status_code=500,
            detail="Could not determine run directory from output",
        ) from None

    # Relative paths for response
    try:
        run_dir_rel = str(run_dir.relative_to(_REPO_ROOT))
    except ValueError:
        run_dir_rel = str(run_dir)

    report_path = Path(run_dir) / "report.html"
    summary_path = Path(run_dir) / "summary.json"

    return {
        "ok": True,
        "config_path": f"backtester/configs/{resolved.name}",
        "run_dir": run_dir_rel.replace("\\", "/"),
        "report_path": (run_dir_rel + "/report.html").replace("\\", "/") if report_path.exists() else None,
        "summary_path": (run_dir_rel + "/summary.json").replace("\\", "/") if summary_path.exists() else None,
    }
