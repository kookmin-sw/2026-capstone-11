#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def _zip_signature(zip_path: Path) -> str:
    stat = zip_path.stat()
    return f"{zip_path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"


def _prepare_project_dir() -> None:
    home = Path.home()
    zip_candidates = [Path.cwd() / "RL_AI.zip", home / "RL_AI.zip"]
    zip_path = next((path for path in zip_candidates if path.exists()), None)
    target_dir = home / "RL_AI"
    marker_path = target_dir / ".source_zip_signature"

    if zip_path is None:
        raise FileNotFoundError("RL_AI.zip not found in current directory or home directory")

    signature = _zip_signature(zip_path)
    if target_dir.exists() and marker_path.exists():
        try:
            if marker_path.read_text(encoding="utf-8").strip() == signature:
                return
        except Exception:
            pass

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_path)

        nested_root = tmp_path / "RL_AI"
        source_root = nested_root if nested_root.exists() else tmp_path
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        for item in source_root.iterdir():
            shutil.move(str(item), str(target_dir / item.name))
        marker_path.write_text(signature, encoding="utf-8")


def main() -> int:
    _prepare_project_dir()
    inner = Path.home() / "RL_AI" / "bias_check.py"
    if not inner.exists():
        raise FileNotFoundError(inner)
    os.execv(sys.executable, [sys.executable, "-u", str(inner), *sys.argv[1:]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
