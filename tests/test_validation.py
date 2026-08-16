from __future__ import annotations

import json
from pathlib import Path

from conftest import PROJECT_ROOT, run

VALIDATOR = PROJECT_ROOT / "tools" / "validate_plugin.py"


def test_plugin_passes_final_directory_constraints() -> None:
    completed = run("python3", str(VALIDATOR))
    result = json.loads(completed.stdout)
    assert result["status"] == "pass"
    assert result["manifest"]["short_description_length"] <= 30
    assert result["manifest"]["default_prompts"] <= 3
    assert result["manifest"]["brand_color_contrast"] >= 2.0
    assert result["skill_count"] == 7
    assert {skill["name"] for skill in result["skills"]} == {
        "using-maestra",
        "doctor",
        "spec",
        "plan",
        "run",
        "gate",
        "finish",
    }
    assert all(skill["explicit_only"] for skill in result["skills"])


def test_plugin_only_distribution_bundles_critical_docs_and_license() -> None:
    plugin = PROJECT_ROOT / "plugins" / "maestra"
    assert (plugin / "LICENSE").is_file()
    for name in ("DESIGN.md", "TROUBLESHOOTING.md", "MIGRATION_FROM_GATELEDGER.md", "ACCEPTANCE_CHECKLIST.md"):
        assert (plugin / "docs" / name).is_file()


def test_bundled_docs_match_source_docs() -> None:
    plugin_docs = PROJECT_ROOT / "plugins" / "maestra" / "docs"
    pairs: list[tuple[Path, Path]] = [
        (PROJECT_ROOT / "DESIGN.md", plugin_docs / "DESIGN.md"),
        (PROJECT_ROOT / "MIGRATION_FROM_GATELEDGER.md", plugin_docs / "MIGRATION_FROM_GATELEDGER.md"),
        (PROJECT_ROOT / "docs" / "TROUBLESHOOTING.md", plugin_docs / "TROUBLESHOOTING.md"),
        (PROJECT_ROOT / "docs" / "ACCEPTANCE_CHECKLIST.md", plugin_docs / "ACCEPTANCE_CHECKLIST.md"),
        (PROJECT_ROOT / "CHANGELOG.md", PROJECT_ROOT / "plugins" / "maestra" / "CHANGELOG.md"),
    ]
    for source, bundled in pairs:
        assert bundled.read_bytes() == source.read_bytes()
