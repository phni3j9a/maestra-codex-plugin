from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI = PROJECT_ROOT / "plugins" / "maestra" / "skills" / "run" / "scripts" / "maestra.py"


def run(
    *args: str,
    cwd: Path | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=merged_env,
    )
    if check and completed.returncode != 0:
        raise AssertionError(
            f"command failed ({completed.returncode}): {' '.join(args)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def cli(repo: Path, *args: str, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return run("python3", str(CLI), *args, "--repo", str(repo), check=check, env=env)


def runtime_root(repo: Path) -> Path:
    raw = run("git", "-C", str(repo), "rev-parse", "--git-path", "maestra").stdout.strip()
    path = Path(raw)
    if not path.is_absolute():
        path = repo / path
    return path.resolve()


def routing_proof(*, codex_version: str = "0.147.0", maestra_version: str = "0.3.2") -> dict[str, Any]:
    return {
        "schema_version": 2,
        "status": "pass",
        "checked_at": "2026-08-15T12:00:00Z",
        "maestra_version": maestra_version,
        "codex_version": codex_version,
        "main_to_terra": {
            "model": "gpt-5.6-terra",
            "reasoning_effort": "xhigh",
            "fork_turns": "none",
            "verified": True,
        },
        "terra_to_luna": {
            "model": "gpt-5.6-luna",
            "reasoning_effort": "max",
            "fork_turns": "none",
            "verified": True,
        },
        "terra_to_reviewer": {
            "model": "gpt-5.6-sol",
            "reasoning_effort": "xhigh",
            "fork_turns": "none",
            "verified": True,
        },
        "evidence": ["test fixture"],
    }


def fake_codex_env(tmp_path: Path, version: str) -> dict[str, str]:
    bindir = tmp_path / f"codex-{version}" / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    binary = bindir / "codex"
    binary.write_text(f"#!/bin/sh\necho 'codex-cli {version}'\n", encoding="utf-8")
    binary.chmod(0o755)
    return {"PATH": str(bindir) + os.pathsep + os.environ.get("PATH", "")}


def record_routing_proof(repo: Path, *, env: dict[str, str], proof: dict[str, Any] | None = None) -> None:
    root = runtime_root(repo)
    path = root / "routing-proof-input.json"
    path.write_text(json.dumps(proof or routing_proof(), indent=2), encoding="utf-8")
    cli(repo, "record-routing-proof", "--proof", str(path), env=env)


def write_approved_artifacts(repo: Path) -> None:
    root = runtime_root(repo)
    root.mkdir(parents=True, exist_ok=True)
    metadata = "---\nstatus: approved\napproved_by: user\napproved_at: 2026-08-15T12:00:00Z\n---\n"
    (root / "spec.md").write_text(metadata + "# Spec\n\n- AC-001: Works.\n", encoding="utf-8")
    (root / "plan.md").write_text(
        metadata
        + "# Detailed Plan\n\n"
        + "## Run R001\n\n"
        + "### T001\n- target: README.md\n- implementation: update behavior\n- open questions: none\n",
        encoding="utf-8",
    )


def packet_for(repo: Path, *, run_id: str = "R001", task_ids: list[str] | None = None) -> dict[str, Any]:
    task_ids = task_ids or ["T001"]
    tasks = []
    for index, task_id in enumerate(task_ids):
        tasks.append(
            {
                "id": task_id,
                "title": f"Task {task_id}",
                "objective": f"Complete {task_id}",
                "depends_on": [] if index == 0 else [task_ids[index - 1]],
                "acceptance_criteria": ["AC-001"],
                "target_files": ["README.md"],
                "implementation_steps": [f"Implement the Main-approved behavior for {task_id}"],
                "design_decisions": ["Preserve the approved public behavior"],
                "boundaries": ["test boundary"],
                "constraints": ["Do not redesign the task"],
                "non_goals": ["unrelated refactor"],
                "verification_plan": ["Verify README change deterministically"],
                "review_focus": ["correctness against approved Task contract"],
                "expected_evidence": ["deterministic check passes"],
                "open_questions": [],
            }
        )
    return {
        "schema_version": 2,
        "run_id": run_id,
        "title": "Test Run",
        "goal": "Exercise the Maestra runtime",
        "spec_path": "spec.md",
        "plan_path": "plan.md",
        "base_commit": run("git", "-C", str(repo), "rev-parse", "HEAD").stdout.strip(),
        "acceptance_criteria": ["AC-001"],
        "architectural_invariants": ["Keep behavior stable"],
        "non_goals": ["Unrelated work"],
        "integration_verification_plan": ["Verify combined Run behavior"],
        "main_gate_questions": ["Did the Run preserve the Main-approved design?"],
        "tasks": tasks,
        "models": {
            "orchestrator": {"model": "gpt-5.6-terra", "reasoning_effort": "xhigh"},
            "implementer": {"model": "gpt-5.6-luna", "reasoning_effort": "max"},
            "reviewer": {"model": "gpt-5.6-sol", "reasoning_effort": "xhigh"},
        },
        "review": {
            "max_rounds": 2,
            "max_major_findings": 5,
            "finding_freeze": True,
            "minor_findings_block": False,
        },
    }


def write_packet(repo: Path, packet: dict[str, Any], name: str = "packet.json") -> Path:
    path = runtime_root(repo) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    return path


def create_run(repo: Path, packet: dict[str, Any] | None = None) -> dict[str, Any]:
    path = write_packet(repo, packet or packet_for(repo))
    completed = cli(repo, "create-run", "--packet", str(path), "--allow-unverified-routing")
    return json.loads(completed.stdout)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run("git", "init", "-q", str(repo))
    run("git", "-C", str(repo), "config", "user.email", "maestra@example.test")
    run("git", "-C", str(repo), "config", "user.name", "Maestra Test")
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    run("git", "-C", str(repo), "add", "README.md")
    run("git", "-C", str(repo), "commit", "-q", "-m", "initial")
    cli(repo, "init")
    write_approved_artifacts(repo)
    return repo
