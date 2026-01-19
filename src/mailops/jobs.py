from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]  # repo root
JOBS_DIR = ROOT / "output" / "jobs"


def new_job_dir(job_id: str) -> Path:
    d = JOBS_DIR / job_id
    (d / "thumbs").mkdir(parents=True, exist_ok=True)
    return d


def latest_job_dir() -> Optional[Path]:
    if not JOBS_DIR.exists():
        return None
    dirs = [p for p in JOBS_DIR.iterdir() if p.is_dir()]
    if not dirs:
        return None
    return sorted(dirs, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
