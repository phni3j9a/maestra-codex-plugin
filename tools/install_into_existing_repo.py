#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


class InstallError(RuntimeError):
    pass


def git_status(target: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(target), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise InstallError(f"Target is not a usable Git repository: {completed.stderr.strip()}")
    return completed.stdout.splitlines()


def load_marketplace(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "name": "maestra-local",
            "interface": {"displayName": "Maestra Local"},
            "plugins": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InstallError(f"Invalid marketplace JSON: {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("plugins"), list):
        raise InstallError(f"Marketplace must contain a plugins array: {path}")
    return data


def maestra_entry() -> dict[str, Any]:
    return {
        "name": "maestra",
        "source": {"source": "local", "path": "./plugins/maestra"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Developer Tools",
    }


def install(*, source_root: Path, target: Path, force: bool, allow_dirty: bool, dry_run: bool) -> dict[str, Any]:
    source_plugin = source_root / "plugins" / "maestra"
    if not (source_plugin / ".codex-plugin" / "plugin.json").is_file():
        raise InstallError(f"Source Maestra plugin is incomplete: {source_plugin}")
    target = target.expanduser().resolve()
    if not target.is_dir():
        raise InstallError(f"Target directory does not exist: {target}")
    dirty = git_status(target)
    if dirty and not allow_dirty:
        raise InstallError("Target Git working tree is dirty; commit/stash intentionally or use --allow-dirty:\n" + "\n".join(dirty))

    target_plugin = target / "plugins" / "maestra"
    marketplace_path = target / ".agents" / "plugins" / "marketplace.json"
    marketplace = load_marketplace(marketplace_path)
    existing_indexes = [index for index, item in enumerate(marketplace["plugins"]) if item.get("name") == "maestra"]

    if (target_plugin.exists() or existing_indexes) and not force:
        raise InstallError("Maestra already exists in the target; use --force only for an intentional replacement")

    new_plugins = [item for item in marketplace["plugins"] if item.get("name") != "maestra"]
    new_plugins.append(maestra_entry())
    marketplace["plugins"] = new_plugins

    actions = [
        f"copy {source_plugin} -> {target_plugin}",
        f"update {marketplace_path} while preserving {len(new_plugins) - 1} existing plugin entries",
    ]
    if dry_run:
        return {"status": "dry-run", "target": str(target), "actions": actions}

    if target_plugin.exists():
        shutil.rmtree(target_plugin)
    target_plugin.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_plugin, target_plugin, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text(json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "status": "installed",
        "target": str(target),
        "plugin": str(target_plugin),
        "marketplace": str(marketplace_path),
        "preserved_plugin_entries": len(new_plugins) - 1,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add or update Maestra in an existing Codex plugin marketplace repository")
    parser.add_argument("--target", required=True, help="existing Codex plugin marketplace repository")
    parser.add_argument("--source-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = install(
            source_root=Path(args.source_root).expanduser().resolve(),
            target=Path(args.target),
            force=args.force,
            allow_dirty=args.allow_dirty,
            dry_run=args.dry_run,
        )
    except InstallError as exc:
        print(f"install-maestra: error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
