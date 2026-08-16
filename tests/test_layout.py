from __future__ import annotations

import json
from pathlib import Path

from conftest import PROJECT_ROOT


def test_portable_plugin_layout_and_seven_explicit_only_skills() -> None:
    plugin = PROJECT_ROOT / "plugins" / "maestra"
    manifest = json.loads((plugin / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "maestra"
    assert manifest["skills"] == "./skills/"

    expected = {"using-maestra", "doctor", "spec", "plan", "run", "gate", "finish"}
    actual = {path.parent.name for path in (plugin / "skills").glob("*/SKILL.md")}
    assert actual == expected
    for name in expected:
        text = (plugin / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert f"name: {name}\n" in text.split("---", 2)[1]
        metadata = plugin / "skills" / name / "agents" / "openai.yaml"
        assert metadata.is_file()
        metadata_text = metadata.read_text(encoding="utf-8")
        assert "policy:\n  allow_implicit_invocation: false\n" in metadata_text


def test_using_maestra_is_the_only_workflow_entry_and_routes_independent_skills() -> None:
    plugin = PROJECT_ROOT / "plugins" / "maestra"
    router_dir = plugin / "skills" / "using-maestra"
    router = (router_dir / "SKILL.md").read_text(encoding="utf-8")

    assert (router_dir / "agents" / "openai.yaml").is_file()
    assert "only workflow entry" in router
    assert "thread-local instruction state" in router
    assert "Activation alone must not create runtime state, artifacts, or subagents" in router
    for phase in ("spec", "plan", "run", "gate", "finish"):
        assert f"../{phase}/SKILL.md" in router
        assert (plugin / "skills" / phase / "SKILL.md").is_file()
    assert not (router_dir / "references").exists()

    manifest = json.loads((plugin / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    prompts = manifest["interface"]["defaultPrompt"]
    assert prompts == [
        "Use $maestra:using-maestra to activate Maestra for this development workflow.",
        "Use $maestra:doctor to verify routing before the first Maestra execution.",
    ]


def test_plugin_is_hook_free() -> None:
    plugin = PROJECT_ROOT / "plugins" / "maestra"
    assert not (plugin / "hooks").exists()
    assert not list(plugin.rglob("hooks.json"))
    for manifest_path in (plugin / ".codex-plugin" / "plugin.json", plugin / "plugin.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "hooks" not in manifest


def test_exact_model_routes_are_consistent() -> None:
    config = json.loads(
        (PROJECT_ROOT / "plugins" / "maestra" / "config" / "runtime.example.json").read_text(encoding="utf-8")
    )
    assert config["models"] == {
        "main": {"model": "gpt-5.6-sol", "reasoning_effort": "high"},
        "orchestrator": {"model": "gpt-5.6-terra", "reasoning_effort": "xhigh"},
        "implementer": {"model": "gpt-5.6-luna", "reasoning_effort": "max"},
        "reviewer": {"model": "gpt-5.6-sol", "reasoning_effort": "xhigh"},
        "final_reviewer": {"model": "gpt-5.6-sol", "reasoning_effort": "xhigh"},
    }
    run_skill = (PROJECT_ROOT / "plugins" / "maestra" / "skills" / "run" / "SKILL.md").read_text(encoding="utf-8")
    assert "fork_turns: none" in run_skill
    assert "silent fallback" in run_skill

    doctor_skill = (PROJECT_ROOT / "plugins" / "maestra" / "skills" / "doctor" / "SKILL.md").read_text(encoding="utf-8")
    assert "verify-routing-proof" in doctor_skill
    assert "turn_context.model" in doctor_skill
    assert "--not-before" in doctor_skill


def test_run_orchestrators_use_event_driven_hour_waits() -> None:
    run_root = PROJECT_ROOT / "plugins" / "maestra" / "skills" / "run"
    main_protocol = (run_root / "SKILL.md").read_text(encoding="utf-8")
    terra_protocol = (run_root / "references" / "orchestrator.md").read_text(encoding="utf-8")

    for protocol in (main_protocol, terra_protocol):
        assert "timeout_ms: 3600000" in protocol
        assert "do not use short polling waits" in protocol
        assert "Do not call `list_agents` during normal" in protocol
        assert "One timeout alone is not a failure" in protocol or "do not treat one timeout as a failure" in protocol

    assert "maestra.py status --repo <repository-root> --json" in main_protocol
    assert "completed descendant `last_task_message`" in main_protocol
    assert "`path_prefix` set to the exact current child path" in terra_protocol
    assert "send it to Luna with `followup_task`" in terra_protocol


def test_marketplace_points_to_portable_plugin() -> None:
    marketplace = json.loads((PROJECT_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    entry = marketplace["plugins"][0]
    assert entry["name"] == "maestra"
    assert entry["source"] == {"source": "local", "path": "./plugins/maestra"}
