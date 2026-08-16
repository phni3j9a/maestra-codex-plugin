#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path
from typing import Iterable

from validate_plugin import validate_plugin

FIXED_TIMESTAMP = (2026, 8, 15, 0, 0, 0)
EXCLUDED_PARTS = {".git", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


class PackageError(RuntimeError):
    pass


def include_file(path: Path) -> bool:
    return not any(part in EXCLUDED_PARTS for part in path.parts) and path.suffix not in EXCLUDED_SUFFIXES


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise PackageError(f"Symlinks are not allowed in release archives: {path}")
        if path.is_file() and include_file(path.relative_to(root)):
            yield path


def write_zip(output: Path, root: Path, prefix: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in iter_files(root):
            relative = source.relative_to(root).as_posix()
            member = f"{prefix.rstrip('/')}/{relative}"
            info = zipfile.ZipInfo(member, FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = source.stat().st_mode
            permissions = 0o755 if mode & stat.S_IXUSR else 0o644
            info.external_attr = (stat.S_IFREG | permissions) << 16
            archive.writestr(info, source.read_bytes())


def validate_plugin_zip(path: Path, expected_prefix: str) -> dict[str, object]:
    if path.stat().st_size > 100 * 1024 * 1024:
        raise PackageError("Plugin ZIP exceeds 100 MB")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if not names:
            raise PackageError("Plugin ZIP is empty")
        top_levels = {name.split("/", 1)[0] for name in names}
        if top_levels != {expected_prefix}:
            raise PackageError(f"Plugin ZIP must have one top-level directory: {top_levels}")
        for name in names:
            path_parts = Path(name).parts
            if name.startswith("/") or ".." in path_parts or "\\" in name:
                raise PackageError(f"Unsafe archive member: {name}")
            if len(path_parts) > 20:
                raise PackageError(f"Archive member is too deep: {name}")
        manifest = f"{expected_prefix}/.codex-plugin/plugin.json"
        if manifest not in names:
            raise PackageError("Plugin manifest is missing from ZIP")
        skills = [name for name in names if name.startswith(f"{expected_prefix}/skills/") and name.endswith("/SKILL.md")]
        if not skills:
            raise PackageError("No bundled Skills found in ZIP")
        manifest_data = json.loads(archive.read(manifest))
    return {
        "archive": str(path),
        "bytes": path.stat().st_size,
        "members": len(names),
        "skills": len(skills),
        "plugin": manifest_data.get("name"),
        "version": manifest_data.get("version"),
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic Maestra plugin and source ZIPs")
    parser.add_argument("--source-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source_root = Path(args.source_root).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    plugin_root = source_root / "plugins" / "maestra"
    plugin_validation_report = validate_plugin(plugin_root)
    plugin_validation_report["plugin_root"] = plugin_root.relative_to(source_root).as_posix()
    manifest = json.loads((plugin_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    version = manifest["version"]

    plugin_zip = output / f"maestra-plugin-v{version}.zip"
    source_zip = output / f"maestra-codex-plugin-source-v{version}.zip"
    write_zip(plugin_zip, plugin_root, "maestra")
    write_zip(source_zip, source_root, f"maestra-codex-plugin-v{version}")

    plugin_validation = validate_plugin_zip(plugin_zip, "maestra")
    plugin_validation["archive"] = plugin_zip.name
    artifacts = [plugin_zip, source_zip]
    checksums = {path.name: sha256(path) for path in artifacts}
    checksum_path = output / "SHA256SUMS.txt"
    checksum_path.write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items())), encoding="utf-8")
    release_manifest = {
        "schema_version": 1,
        "plugin": manifest["name"],
        "version": version,
        "plugin_validation": plugin_validation_report,
        "plugin_archive": plugin_validation,
        "source_archive": {"archive": source_zip.name, "bytes": source_zip.stat().st_size},
        "sha256": checksums,
    }
    manifest_path = output / "release-manifest.json"
    manifest_path.write_text(json.dumps(release_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "built", "files": [str(path) for path in [*artifacts, checksum_path, manifest_path]], "validation": plugin_validation}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
