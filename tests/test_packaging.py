from __future__ import annotations

import json
import zipfile
from pathlib import Path

from conftest import PROJECT_ROOT, run

PACKAGER = PROJECT_ROOT / "tools" / "package_release.py"


def test_plugin_release_zip_has_one_valid_plugin_root(tmp_path: Path) -> None:
    manifest = json.loads(
        (PROJECT_ROOT / "plugins" / "maestra" / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    version = manifest["version"]
    completed = run("python3", str(PACKAGER), "--output", str(tmp_path))
    result = json.loads(completed.stdout)
    assert result["status"] == "built"
    plugin_zip = tmp_path / f"maestra-plugin-v{version}.zip"
    assert plugin_zip.is_file()
    with zipfile.ZipFile(plugin_zip) as archive:
        names = archive.namelist()
        assert {name.split("/", 1)[0] for name in names} == {"maestra"}
        assert "maestra/.codex-plugin/plugin.json" in names
        assert len([name for name in names if name.endswith("/SKILL.md")]) == 7
        assert "maestra/skills/using-maestra/SKILL.md" in names
        assert "maestra/skills/using-maestra/agents/openai.yaml" in names
        assert "maestra/hooks/hooks.json" not in names
        metadata = [name for name in names if name.endswith("/agents/openai.yaml")]
        assert len(metadata) == 7
        for name in metadata:
            assert b"policy:\n  allow_implicit_invocation: false\n" in archive.read(name)
        assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
    checksums = (tmp_path / "SHA256SUMS.txt").read_text(encoding="utf-8")
    assert f"maestra-plugin-v{version}.zip" in checksums
    assert f"maestra-codex-plugin-source-v{version}.zip" in checksums
    release = json.loads((tmp_path / "release-manifest.json").read_text(encoding="utf-8"))
    assert release["plugin_validation"]["status"] == "pass"
    assert release["plugin_validation"]["skill_count"] == 7
    assert release["plugin_validation"]["plugin_root"] == "plugins/maestra"
    assert release["plugin_archive"]["archive"] == f"maestra-plugin-v{version}.zip"
    assert release["source_archive"]["archive"] == f"maestra-codex-plugin-source-v{version}.zip"

    source_zip = tmp_path / f"maestra-codex-plugin-source-v{version}.zip"
    with zipfile.ZipFile(source_zip) as archive:
        root = f"maestra-codex-plugin-v{version}"
        names = archive.namelist()
        assert f"{root}/plugins/maestra/skills/using-maestra/SKILL.md" in names
        assert f"{root}/plugins/maestra/skills/using-maestra/agents/openai.yaml" in names
        metadata = [
            name
            for name in names
            if name.startswith(f"{root}/plugins/maestra/skills/") and name.endswith("/agents/openai.yaml")
        ]
        assert len(metadata) == 7
        for name in metadata:
            assert b"policy:\n  allow_implicit_invocation: false\n" in archive.read(name)
