from __future__ import annotations

import json
from pathlib import Path

from conftest import PROJECT_ROOT, run

INSTALLER = PROJECT_ROOT / "tools" / "install_into_existing_repo.py"


def make_target(tmp_path: Path) -> Path:
    target = tmp_path / "existing"
    target.mkdir()
    run("git", "init", "-q", str(target))
    run("git", "-C", str(target), "config", "user.email", "maestra@example.test")
    run("git", "-C", str(target), "config", "user.name", "Maestra Test")
    marketplace = target / ".agents" / "plugins" / "marketplace.json"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        json.dumps(
            {
                "name": "existing-marketplace",
                "plugins": [
                    {
                        "name": "gateledger",
                        "source": {"source": "local", "path": "./plugins/gateledger"},
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    gateledger = target / "plugins" / "gateledger"
    gateledger.mkdir(parents=True)
    (gateledger / "sentinel.txt").write_text("keep me\n", encoding="utf-8")
    run("git", "-C", str(target), "add", ".")
    run("git", "-C", str(target), "commit", "-q", "-m", "existing GateLedger")
    return target


def test_installer_adds_maestra_and_preserves_gateledger(tmp_path: Path) -> None:
    target = make_target(tmp_path)
    completed = run("python3", str(INSTALLER), "--target", str(target))
    result = json.loads(completed.stdout)
    assert result["status"] == "installed"
    assert (target / "plugins" / "gateledger" / "sentinel.txt").read_text(encoding="utf-8") == "keep me\n"
    assert (target / "plugins" / "maestra" / ".codex-plugin" / "plugin.json").is_file()
    marketplace = json.loads((target / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    assert marketplace["name"] == "existing-marketplace"
    assert [item["name"] for item in marketplace["plugins"]] == ["gateledger", "maestra"]


def test_installer_dry_run_does_not_mutate_target(tmp_path: Path) -> None:
    target = make_target(tmp_path)
    before = run("git", "-C", str(target), "status", "--porcelain=v1").stdout
    completed = run("python3", str(INSTALLER), "--target", str(target), "--dry-run")
    assert json.loads(completed.stdout)["status"] == "dry-run"
    assert not (target / "plugins" / "maestra").exists()
    assert run("git", "-C", str(target), "status", "--porcelain=v1").stdout == before


def test_installer_refuses_dirty_target(tmp_path: Path) -> None:
    target = make_target(tmp_path)
    (target / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    completed = run("python3", str(INSTALLER), "--target", str(target), check=False)
    assert completed.returncode == 2
    assert "working tree is dirty" in completed.stderr
