from __future__ import annotations

import json
from pathlib import Path

from conftest import (
    cli,
    create_run,
    fake_codex_env,
    packet_for,
    record_routing_proof,
    routing_proof,
    run,
    runtime_root,
    write_packet,
)


def stage_candidate(repo: Path, content: str) -> str:
    (repo / "README.md").write_text(content, encoding="utf-8")
    run("git", "-C", str(repo), "add", "README.md")
    return run("git", "-C", str(repo), "write-tree").stdout.strip()


def verification_payload(*, candidate_tree: str, subject: str = "T001", status: str = "pass", exit_code: int = 0) -> dict:
    return {
        "schema_version": 1,
        "run_id": "R001",
        "task_id": subject,
        "candidate_tree": candidate_tree,
        "status": status,
        "commands": [
            {
                "argv": ["python3", "-c", "print('ok')"],
                "cwd": ".",
                "exit_code": exit_code,
                "duration_seconds": 0.1,
                "log_path": f"maestra/runs/R001/{subject.lower()}-test.log",
            }
        ],
        "summary": ["deterministic evidence"],
    }


def finding(
    finding_id: str,
    *,
    severity: str = "major",
    resolution: str | None = None,
    introduced_by_fix: bool = False,
    exception: str | None = None,
) -> dict:
    return {
        "id": finding_id,
        "severity": severity,
        "category": "correctness",
        "location": "README.md:1",
        "summary": "Concrete issue",
        "evidence": "Candidate shows the issue",
        "required_change": "Apply bounded correction",
        "introduced_by_fix": introduced_by_fix,
        "exception": exception,
        "resolution": resolution,
    }


def review_payload(
    *,
    candidate_tree: str,
    subject: str = "T001",
    round_number: int = 1,
    verdict: str = "PASS",
    findings: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "run_id": "R001",
        "task_id": subject,
        "candidate_tree": candidate_tree,
        "round": round_number,
        "verdict": verdict,
        "findings": findings or [],
        "residual_risks": [],
    }


def record_task_verification(repo: Path, tree: str, *, replace: bool = False) -> None:
    path = write_packet(repo, verification_payload(candidate_tree=tree), "verification-input.json")
    args = ["record-verification", "--run", "R001", "--task", "T001", "--verification", str(path)]
    if replace:
        args.append("--replace")
    cli(repo, *args)


def record_task_review(
    repo: Path,
    tree: str,
    *,
    round_number: int = 1,
    verdict: str = "PASS",
    findings: list[dict] | None = None,
    name: str = "review-input.json",
    check: bool = True,
):
    path = write_packet(
        repo,
        review_payload(candidate_tree=tree, round_number=round_number, verdict=verdict, findings=findings),
        name,
    )
    return cli(repo, "freeze-review", "--run", "R001", "--task", "T001", "--review", str(path), check=check)


def pass_one_task(repo: Path, *, content: str = "implemented\n") -> str:
    cli(repo, "task", "--run", "R001", "--task", "T001", "--status", "implementing")
    tree = stage_candidate(repo, content)
    cli(repo, "task", "--run", "R001", "--task", "T001", "--status", "verifying")
    record_task_verification(repo, tree)
    cli(repo, "task", "--run", "R001", "--task", "T001", "--status", "reviewing")
    record_task_review(repo, tree)
    run(
        "git",
        "-C",
        str(repo),
        "commit",
        "-q",
        "-m",
        "Implement T001\n\nMaestra-Run: R001\nMaestra-Task: T001",
    )
    commit = run("git", "-C", str(repo), "rev-parse", "HEAD").stdout.strip()
    cli(repo, "task", "--run", "R001", "--task", "T001", "--status", "passed", "--commit", commit)
    return commit


def record_integration(repo: Path) -> str:
    tree = run("git", "-C", str(repo), "write-tree").stdout.strip()
    verification = write_packet(repo, verification_payload(candidate_tree=tree, subject="INTEGRATION"), "integration-verification-input.json")
    review = write_packet(repo, review_payload(candidate_tree=tree, subject="INTEGRATION"), "integration-review-input.json")
    cli(repo, "record-integration", "--run", "R001", "--verification", str(verification), "--review", str(review))
    return tree


def write_routing_rollouts(
    sessions_dir: Path,
    *,
    luna_model: str = "gpt-5.6-luna",
    include_reviewer: bool = True,
    reviewer_parent: str | None = None,
) -> dict[str, str]:
    root_id = "root-thread"
    terra_id = "terra-thread"
    luna_id = "luna-thread"
    reviewer_id = "reviewer-thread"
    terra_path = "/root/doctor-terra"
    luna_path = f"{terra_path}/doctor-luna"
    reviewer_path = f"{terra_path}/doctor-reviewer"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    def session_meta(
        *,
        thread_id: str,
        timestamp: str,
        parent_thread_id: str | None = None,
        agent_path: str | None = None,
        depth: int | None = None,
    ) -> dict:
        payload: dict = {
            "id": thread_id,
            "session_id": root_id,
            "timestamp": timestamp,
            "thread_source": "subagent" if agent_path else "cli",
        }
        if parent_thread_id and agent_path and depth is not None:
            payload.update({
                "parent_thread_id": parent_thread_id,
                "agent_path": agent_path,
                "source": {
                    "subagent": {
                        "thread_spawn": {
                            "parent_thread_id": parent_thread_id,
                            "depth": depth,
                            "agent_path": agent_path,
                        }
                    }
                },
            })
        return {"timestamp": timestamp, "type": "session_meta", "payload": payload}

    def turn_context(*, timestamp: str, model: str, effort: str) -> dict:
        return {
            "timestamp": timestamp,
            "type": "turn_context",
            "payload": {"turn_id": f"turn-{timestamp}", "model": model, "effort": effort},
        }

    def spawn_call(*, timestamp: str, task_name: str, model: str, effort: str) -> dict:
        return {
            "timestamp": timestamp,
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "spawn_agent",
                "arguments": json.dumps({
                    "task_name": task_name,
                    "model": model,
                    "reasoning_effort": effort,
                    "fork_turns": "none",
                    "message": "SENSITIVE PROBE PROMPT MUST NOT ENTER EVIDENCE",
                }),
            },
        }

    def write(name: str, entries: list[dict]) -> None:
        target = sessions_dir / "2026" / "08" / "15" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("".join(json.dumps(item) + "\n" for item in entries), encoding="utf-8")

    write(
        "rollout-root-thread.jsonl",
        [
            session_meta(thread_id=root_id, timestamp="2026-08-15T12:00:00Z"),
            turn_context(timestamp="2026-08-15T12:00:01Z", model="gpt-5.6-sol", effort="high"),
            spawn_call(
                timestamp="2026-08-15T13:00:01Z",
                task_name="doctor-terra",
                model="gpt-5.6-terra",
                effort="xhigh",
            ),
        ],
    )
    write(
        "rollout-terra-thread.jsonl",
        [
            session_meta(
                thread_id=terra_id,
                timestamp="2026-08-15T13:00:02Z",
                parent_thread_id=root_id,
                agent_path=terra_path,
                depth=1,
            ),
            turn_context(timestamp="2026-08-15T13:00:03Z", model="gpt-5.6-terra", effort="xhigh"),
            spawn_call(
                timestamp="2026-08-15T13:00:04Z",
                task_name="doctor-luna",
                model="gpt-5.6-luna",
                effort="max",
            ),
            spawn_call(
                timestamp="2026-08-15T13:00:05Z",
                task_name="doctor-reviewer",
                model="gpt-5.6-sol",
                effort="xhigh",
            ),
        ],
    )
    write(
        "rollout-luna-thread.jsonl",
        [
            session_meta(
                thread_id=luna_id,
                timestamp="2026-08-15T13:00:06Z",
                parent_thread_id=terra_id,
                agent_path=luna_path,
                depth=2,
            ),
            turn_context(timestamp="2026-08-15T13:00:07Z", model=luna_model, effort="max"),
        ],
    )
    if include_reviewer:
        write(
            "rollout-reviewer-thread.jsonl",
            [
                session_meta(
                    thread_id=reviewer_id,
                    timestamp="2026-08-15T13:00:08Z",
                    parent_thread_id=reviewer_parent or terra_id,
                    agent_path=reviewer_path,
                    depth=2,
                ),
                turn_context(timestamp="2026-08-15T13:00:09Z", model="gpt-5.6-sol", effort="xhigh"),
            ],
        )
    return {"terra": terra_path, "luna": luna_path, "reviewer": reviewer_path}


def test_init_keeps_runtime_outside_product_worktree(git_repo: Path) -> None:
    root = runtime_root(git_repo)
    assert root.is_dir()
    assert (root / "config.json").is_file()
    assert not (git_repo / ".maestra").exists()
    assert run("git", "-C", str(git_repo), "status", "--porcelain=v1").stdout == ""


def test_linked_worktree_resolves_checkout_specific_runtime(tmp_path: Path) -> None:
    main = tmp_path / "main"
    main.mkdir()
    run("git", "init", "-q", str(main))
    run("git", "-C", str(main), "config", "user.email", "maestra@example.test")
    run("git", "-C", str(main), "config", "user.name", "Maestra Test")
    (main / "README.md").write_text("initial\n", encoding="utf-8")
    run("git", "-C", str(main), "add", "README.md")
    run("git", "-C", str(main), "commit", "-q", "-m", "initial")
    worktree = tmp_path / "wt"
    run("git", "-C", str(main), "worktree", "add", "-q", "-b", "wt-branch", str(worktree))
    cli(worktree, "init")
    assert runtime_root(worktree).is_dir()
    assert not (worktree / ".maestra").exists()
    assert run("git", "-C", str(worktree), "status", "--porcelain=v1").stdout == ""


def test_doctor_static_checks(git_repo: Path) -> None:
    completed = cli(git_repo, "doctor", "--json", "--allow-missing-codex")
    result = json.loads(completed.stdout)
    assert result["status"] in {"pass", "warn"}
    by_name = {item["name"]: item for item in result["checks"]}
    assert by_name["git_repository"]["status"] == "pass"
    assert by_name["runtime_config"]["status"] == "pass"
    assert by_name["plugin_layout"]["status"] == "pass"


def test_verify_routing_proof_reads_codex_rollout_metadata(git_repo: Path, tmp_path: Path) -> None:
    sessions_dir = tmp_path / "codex-sessions"
    paths = write_routing_rollouts(sessions_dir)
    env = fake_codex_env(tmp_path, "0.147.0")
    completed = cli(
        git_repo,
        "verify-routing-proof",
        "--sessions-dir",
        str(sessions_dir),
        "--not-before",
        "2026-08-15T13:00:00Z",
        "--terra-agent-path",
        paths["terra"],
        "--luna-agent-path",
        paths["luna"],
        "--reviewer-agent-path",
        paths["reviewer"],
        env=env,
    )
    result = json.loads(completed.stdout)
    assert result["routing_status"] == "pass"
    assert all(route["verified"] for route in result["routes"].values())
    proof_text = (runtime_root(git_repo) / "routing-proof.json").read_text(encoding="utf-8")
    proof = json.loads(proof_text)
    assert proof["status"] == "pass"
    assert "SENSITIVE PROBE PROMPT" not in proof_text


def test_verify_routing_proof_records_observed_model_mismatch_as_fail(git_repo: Path, tmp_path: Path) -> None:
    sessions_dir = tmp_path / "codex-sessions"
    paths = write_routing_rollouts(sessions_dir, luna_model="gpt-5.6-sol")
    env = fake_codex_env(tmp_path, "0.147.0")
    completed = cli(
        git_repo,
        "verify-routing-proof",
        "--sessions-dir",
        str(sessions_dir),
        "--not-before",
        "2026-08-15T13:00:00Z",
        "--terra-agent-path",
        paths["terra"],
        "--luna-agent-path",
        paths["luna"],
        "--reviewer-agent-path",
        paths["reviewer"],
        env=env,
        check=False,
    )
    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["routing_status"] == "fail"
    assert result["routes"]["terra_to_luna"]["state"] == "fail"
    proof = json.loads((runtime_root(git_repo) / "routing-proof.json").read_text(encoding="utf-8"))
    assert proof["status"] == "fail"
    assert proof["terra_to_luna"]["verified"] is False


def test_verify_routing_proof_records_missing_rollout_as_unverified(git_repo: Path, tmp_path: Path) -> None:
    sessions_dir = tmp_path / "codex-sessions"
    paths = write_routing_rollouts(sessions_dir, include_reviewer=False)
    env = fake_codex_env(tmp_path, "0.147.0")
    completed = cli(
        git_repo,
        "verify-routing-proof",
        "--sessions-dir",
        str(sessions_dir),
        "--not-before",
        "2026-08-15T13:00:00Z",
        "--terra-agent-path",
        paths["terra"],
        "--luna-agent-path",
        paths["luna"],
        "--reviewer-agent-path",
        paths["reviewer"],
        env=env,
        check=False,
    )
    assert completed.returncode == 1
    assert json.loads(completed.stdout)["routing_status"] == "unverified"
    proof = json.loads((runtime_root(git_repo) / "routing-proof.json").read_text(encoding="utf-8"))
    assert proof["status"] == "unverified"


def test_verify_routing_proof_records_parent_mismatch_as_fail(git_repo: Path, tmp_path: Path) -> None:
    sessions_dir = tmp_path / "codex-sessions"
    paths = write_routing_rollouts(sessions_dir, reviewer_parent="wrong-parent")
    env = fake_codex_env(tmp_path, "0.147.0")
    completed = cli(
        git_repo,
        "verify-routing-proof",
        "--sessions-dir",
        str(sessions_dir),
        "--not-before",
        "2026-08-15T13:00:00Z",
        "--terra-agent-path",
        paths["terra"],
        "--luna-agent-path",
        paths["luna"],
        "--reviewer-agent-path",
        paths["reviewer"],
        env=env,
        check=False,
    )
    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["routing_status"] == "fail"
    assert result["routes"]["terra_to_reviewer"]["state"] == "fail"


def test_create_run_accepts_detailed_main_owned_packet(git_repo: Path) -> None:
    result = create_run(git_repo)
    assert result["run_id"] == "R001"
    state = json.loads((runtime_root(git_repo) / "runs" / "R001" / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "ready"
    assert state["tasks"]["T001"]["status"] == "pending"


def test_create_run_rejects_coarse_plan_packet(git_repo: Path) -> None:
    packet = packet_for(git_repo)
    del packet["tasks"][0]["implementation_steps"]
    path = write_packet(git_repo, packet)
    completed = cli(git_repo, "create-run", "--packet", str(path), "--allow-unverified-routing", check=False)
    assert completed.returncode == 2
    assert "implementation_steps" in completed.stderr


def test_create_run_rejects_open_questions_as_plan_gap(git_repo: Path) -> None:
    packet = packet_for(git_repo)
    packet["tasks"][0]["open_questions"] = ["Choose storage ownership"]
    path = write_packet(git_repo, packet)
    completed = cli(git_repo, "create-run", "--packet", str(path), "--allow-unverified-routing", check=False)
    assert completed.returncode == 2
    assert "PLAN_GAP" in completed.stderr


def test_create_run_fails_on_dirty_product_tree(git_repo: Path) -> None:
    (git_repo / "README.md").write_text("dirty\n", encoding="utf-8")
    path = write_packet(git_repo, packet_for(git_repo))
    completed = cli(git_repo, "create-run", "--packet", str(path), "--allow-unverified-routing", check=False)
    assert completed.returncode == 2
    assert "Product working tree is not clean" in completed.stderr


def test_create_run_requires_current_routing_proof(git_repo: Path) -> None:
    path = write_packet(git_repo, packet_for(git_repo))
    completed = cli(git_repo, "create-run", "--packet", str(path), check=False)
    assert completed.returncode == 2
    assert "routing proof" in completed.stderr.lower()


def test_routing_proof_is_bound_to_codex_and_maestra_versions(git_repo: Path, tmp_path: Path) -> None:
    env147 = fake_codex_env(tmp_path, "0.147.0")
    record_routing_proof(git_repo, env=env147)
    packet_path = write_packet(git_repo, packet_for(git_repo))
    ok = cli(git_repo, "create-run", "--packet", str(packet_path), env=env147)
    assert json.loads(ok.stdout)["status"] == "created"

    # A fresh repo demonstrates Codex-version invalidation without active-run interference.
    other = tmp_path / "other"
    other.mkdir()
    run("git", "init", "-q", str(other))
    run("git", "-C", str(other), "config", "user.email", "maestra@example.test")
    run("git", "-C", str(other), "config", "user.name", "Maestra Test")
    (other / "README.md").write_text("initial\n", encoding="utf-8")
    run("git", "-C", str(other), "add", "README.md")
    run("git", "-C", str(other), "commit", "-q", "-m", "initial")
    cli(other, "init")
    root = runtime_root(other)
    metadata = "---\nstatus: approved\napproved_by: user\napproved_at: 2026-08-15T12:00:00Z\n---\n"
    (root / "spec.md").write_text(metadata + "# Spec\n", encoding="utf-8")
    (root / "plan.md").write_text(metadata + "# Plan\n", encoding="utf-8")
    record_routing_proof(other, env=env147)
    env148 = fake_codex_env(tmp_path, "0.148.0")
    path2 = write_packet(other, packet_for(other))
    bad = cli(other, "create-run", "--packet", str(path2), env=env148, check=False)
    assert bad.returncode == 2
    assert "recorded for Codex 0.147.0" in bad.stderr

    wrong = routing_proof(maestra_version="0.2.0")
    proof_path = runtime_root(other) / "wrong-maestra-proof.json"
    proof_path.write_text(json.dumps(wrong, indent=2), encoding="utf-8")
    bad_maestra = cli(other, "record-routing-proof", "--proof", str(proof_path), env=env147, check=False)
    assert bad_maestra.returncode == 2
    assert "current version is 0.3.2" in bad_maestra.stderr


def test_finding_freeze_rejects_ordinary_new_round_two_finding(git_repo: Path) -> None:
    create_run(git_repo)
    cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "implementing")
    tree1 = stage_candidate(git_repo, "round one\n")
    cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "verifying")
    record_task_verification(git_repo, tree1)
    cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "reviewing")
    record_task_review(git_repo, tree1, verdict="CHANGES_REQUESTED", findings=[finding("T001-F01")], name="review1.json")

    cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "fixing")
    tree2 = stage_candidate(git_repo, "accepted fix\n")
    cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "verifying")
    record_task_verification(git_repo, tree2, replace=True)
    cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "reviewing")
    completed = record_task_review(
        git_repo,
        tree2,
        round_number=2,
        verdict="CHANGES_REQUESTED",
        findings=[finding("T001-F01", resolution="resolved"), finding("T001-F02")],
        name="review2.json",
        check=False,
    )
    assert completed.returncode == 2
    assert "Finding Freeze" in completed.stderr


def test_finding_freeze_allows_critical_fix_regression(git_repo: Path) -> None:
    create_run(git_repo)
    cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "implementing")
    tree1 = stage_candidate(git_repo, "round one\n")
    cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "verifying")
    record_task_verification(git_repo, tree1)
    cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "reviewing")
    record_task_review(git_repo, tree1, verdict="CHANGES_REQUESTED", findings=[finding("T001-F01")], name="review1.json")
    cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "fixing")
    tree2 = stage_candidate(git_repo, "critical regression\n")
    cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "verifying")
    record_task_verification(git_repo, tree2, replace=True)
    cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "reviewing")
    critical = finding("T001-F02", severity="critical", introduced_by_fix=True, exception="fix_regression")
    completed = record_task_review(
        git_repo,
        tree2,
        round_number=2,
        verdict="CHANGES_REQUESTED",
        findings=[finding("T001-F01", resolution="resolved"), critical],
        name="review2.json",
    )
    assert json.loads(completed.stdout)["new_exception_ids"] == ["T001-F02"]


def test_task_commit_must_match_verified_reviewed_tree(git_repo: Path) -> None:
    create_run(git_repo)
    cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "implementing")
    tree = stage_candidate(git_repo, "reviewed\n")
    cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "verifying")
    record_task_verification(git_repo, tree)
    cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "reviewing")
    record_task_review(git_repo, tree)
    stage_candidate(git_repo, "unreviewed mutation\n")
    run(
        "git",
        "-C",
        str(git_repo),
        "commit",
        "-q",
        "-m",
        "Mutated\n\nMaestra-Run: R001\nMaestra-Task: T001",
    )
    commit = run("git", "-C", str(git_repo), "rev-parse", "HEAD").stdout.strip()
    completed = cli(git_repo, "task", "--run", "R001", "--task", "T001", "--status", "passed", "--commit", commit, check=False)
    assert completed.returncode == 2
    assert "does not match the verified and reviewed candidate tree" in completed.stderr


def test_plan_gap_stops_run_and_requires_main_replan(git_repo: Path) -> None:
    create_run(git_repo)
    gap = {
        "schema_version": 1,
        "run_id": "R001",
        "task_id": "T001",
        "reason": "Repository requires an unplanned storage ownership decision",
        "missing_plan_elements": ["Choose token persistence owner"],
        "evidence": ["Two existing layers can own persistence and Plan chooses neither"],
        "requested_main_action": "Main Sol revises Detailed Plan and obtains user approval",
    }
    gap_path = write_packet(git_repo, gap, "plan-gap-input.json")
    result = json.loads(cli(git_repo, "report-plan-gap", "--run", "R001", "--gap", str(gap_path)).stdout)
    assert result["status"] == "PLAN_GAP"
    state = json.loads((runtime_root(git_repo) / "runs" / "R001" / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "plan_gap"
    assert state["tasks"]["T001"]["status"] == "plan_gap"

    invalid = cli(
        git_repo,
        "record-gate",
        "--run",
        "R001",
        "--decision",
        "CONTINUE",
        "--note",
        "Terra should decide",
        check=False,
    )
    assert invalid.returncode == 2
    assert "REPLAN or USER_DECISION" in invalid.stderr

    valid = cli(
        git_repo,
        "record-gate",
        "--run",
        "R001",
        "--decision",
        "REPLAN",
        "--note",
        "Main will fill the missing plan decision.",
    )
    assert json.loads(valid.stdout)["status"] == "gated"


def test_complete_run_requires_run_integration_review(git_repo: Path) -> None:
    create_run(git_repo)
    pass_one_task(git_repo)
    report = runtime_root(git_repo) / "runs" / "R001" / "run-report.md"
    report.write_text("# Run Report\n", encoding="utf-8")
    completed = cli(git_repo, "complete-run", "--run", "R001", "--report", str(report), check=False)
    assert completed.returncode == 2
    assert "Integration Review" in completed.stderr


def test_run_integration_pass_allows_completion_and_main_gate(git_repo: Path) -> None:
    create_run(git_repo)
    pass_one_task(git_repo)
    record_integration(git_repo)
    report = runtime_root(git_repo) / "runs" / "R001" / "run-report.md"
    report.write_text("# Run Report\n\nAll good.\n", encoding="utf-8")
    completed = cli(git_repo, "complete-run", "--run", "R001", "--report", str(report))
    result = json.loads(completed.stdout)
    assert result["status"] == "awaiting_main_gate"
    assert "immediately perform the semantic gate" in result["next"]

    gate = cli(
        git_repo,
        "record-gate",
        "--run",
        "R001",
        "--decision",
        "CONTINUE",
        "--note",
        "Run satisfies the approved detailed design.",
    )
    assert json.loads(gate.stdout)["status"] == "gated"


def test_pass_verification_rejects_unstaged_product_changes(git_repo: Path) -> None:
    create_run(git_repo)
    tree = stage_candidate(git_repo, "staged\n")
    (git_repo / "extra.txt").write_text("unstaged\n", encoding="utf-8")
    path = write_packet(git_repo, verification_payload(candidate_tree=tree), "verification.json")
    completed = cli(
        git_repo,
        "record-verification",
        "--run",
        "R001",
        "--task",
        "T001",
        "--verification",
        str(path),
        check=False,
    )
    assert completed.returncode == 2
    assert "must be staged before verification" in completed.stderr
    assert "extra.txt" in completed.stderr
