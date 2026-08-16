from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import MaestraError


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MaestraError(f"JSON file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MaestraError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise MaestraError(f"Expected a JSON object in {path}")
    return data


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write one small runtime artifact atomically without building a transaction engine."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise MaestraError(f"File does not exist: {path}") from exc
    return digest.hexdigest()


def resolve_inside(root: Path, value: str, *, must_exist: bool = False) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise MaestraError(f"Path escapes repository root: {value}") from exc
    if must_exist and not resolved.exists():
        raise MaestraError(f"Required path does not exist: {resolved}")
    return resolved


def read_simple_frontmatter(path: Path) -> dict[str, str]:
    """Read the flat metadata used by Maestra Spec/Plan without a YAML dependency."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise MaestraError(f"Markdown artifact does not exist: {path}") from exc
    if not lines or lines[0].strip() != "---":
        raise MaestraError(f"Missing YAML frontmatter in {path}")
    metadata: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return metadata
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise MaestraError(f"Unsupported frontmatter line in {path}: {line}")
        key, raw_value = line.split(":", 1)
        metadata[key.strip()] = raw_value.strip().strip('"').strip("'")
    raise MaestraError(f"Unterminated YAML frontmatter in {path}")
