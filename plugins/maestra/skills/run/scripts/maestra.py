#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from maestra_core import __version__
from maestra_core.errors import MaestraError
from maestra_core.git import (
    git_available,
    git_path,
    head_commit,
    index_tree,
    product_status,
    repo_root,
    staged_product_paths,
    unstaged_product_paths,
)
from maestra_core.io import atomic_write_json, load_json, sha256_file, utc_now
from maestra_core.review import freeze_review
from maestra_core.routing import default_sessions_dir, verify_rollout_routing
from maestra_core.schema import (
    EXPECTED_MODELS,
    validate_config,
    validate_plan_gap,
    validate_review,
    validate_routing_proof,
    validate_run_packet,
    validate_verification,
)
from maestra_core.state import load_state, mark_review_round, save_state, update_task

MIN_CODEX_VERSION = (0, 147, 0)


def plugin_root() -> Path:
    return Path(__file__).resolve().parents[3]


def normalize_repo(value: str) -> Path:
    return repo_root(Path(value).expanduser().resolve())


def config_path(repo: Path) -> Path:
    return git_path(repo, "maestra/config.json")


def load_config(repo: Path) -> dict[str, Any]:
    config = load_json(config_path(repo))
    validate_config(config)
    return config


def runtime_dir(repo: Path, config: dict[str, Any] | None = None) -> Path:
    artifact = config.get("artifact_dir", "maestra") if config else "maestra"
    return git_path(repo, artifact)


def run_dir_for(repo: Path, run_id: str, config: dict[str, Any] | None = None) -> Path:
    return runtime_dir(repo, config) / "runs" / run_id


def codex_semver(parsed: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in parsed)


def parse_codex_version() -> tuple[str | None, tuple[int, int, int] | None, str | None]:
    binary = shutil.which("codex")
    if not binary:
        return None, None, "codex executable not found"
    completed = subprocess.run([binary, "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    output = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0:
        return binary, None, f"codex --version failed: {output}"
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", output)
    if not match:
        return binary, None, f"could not parse version from: {output}"
    return binary, tuple(int(group) for group in match.groups()), output


def cmd_init(args: argparse.Namespace) -> int:
    repo = normalize_repo(args.repo)
    target_dir = git_path(repo, "maestra")
    target_dir.mkdir(parents=True, exist_ok=True)
    source_config = plugin_root() / "config" / "runtime.example.json"
    target_config = target_dir / "config.json"
    if target_config.exists() and not args.force:
        raise MaestraError(f"Config already exists: {target_config}; use --force to replace it")
    shutil.copyfile(source_config, target_config)
    readme = target_dir / "README.md"
    if not readme.exists() or args.force:
        readme.write_text(
            "# Maestra Runtime Artifacts\n\n"
            "This directory lives in Git metadata, outside the product working tree. "
            "Spec, Plan, Run packets, evidence, and routing proof are local orchestration state.\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "status": "initialized",
        "repo": str(repo),
        "runtime_dir": str(target_dir),
        "config": str(target_config),
    }, ensure_ascii=False, indent=2))
    return 0


def add_check(checks: list[dict[str, Any]], name: str, status: str, detail: str) -> None:
    checks.append({"name": name, "status": status, "detail": detail})


def routing_proof_path(repo: Path, config: dict[str, Any]) -> Path:
    return runtime_dir(repo, config) / "routing-proof.json"


def cmd_doctor(args: argparse.Namespace) -> int:
    checks: list[dict[str, Any]] = []
    repo: Path | None = None
    try:
        repo = normalize_repo(args.repo)
        add_check(checks, "git_repository", "pass", str(repo))
    except MaestraError as exc:
        add_check(checks, "git_repository", "fail", str(exc))

    add_check(checks, "python", "pass" if sys.version_info >= (3, 10) else "fail", sys.version.split()[0])
    add_check(checks, "git_executable", "pass" if git_available() else "fail", shutil.which("git") or "not found")

    config: dict[str, Any] | None = None
    if repo:
        try:
            config = load_config(repo)
            add_check(checks, "runtime_config", "pass", str(config_path(repo)))
        except MaestraError as exc:
            add_check(checks, "runtime_config", "fail", str(exc))

    manifest = plugin_root() / ".codex-plugin" / "plugin.json"
    required_skills = ["doctor", "spec", "plan", "run", "gate", "finish"]
    layout_missing = [name for name in required_skills if not (plugin_root() / "skills" / name / "SKILL.md").is_file()]
    if manifest.is_file() and not layout_missing:
        add_check(checks, "plugin_layout", "pass", f"manifest and {len(required_skills)} Skills present")
    else:
        add_check(checks, "plugin_layout", "fail", f"missing manifest or Skills: {layout_missing}")

    binary, parsed, detail = parse_codex_version()
    current_codex: str | None = None
    if parsed is None:
        status = "warn" if args.allow_missing_codex else "fail"
        add_check(checks, "codex_version", status, detail or "unknown")
    elif parsed < MIN_CODEX_VERSION:
        add_check(checks, "codex_version", "fail", f"{detail}; requires >= 0.147.0")
        current_codex = codex_semver(parsed)
    else:
        current_codex = codex_semver(parsed)
        add_check(checks, "codex_version", "pass", detail or current_codex)

    if repo and config:
        dirty = product_status(repo)
        add_check(checks, "product_worktree", "pass" if not dirty else "warn", "clean" if not dirty else "\n".join(dirty))
        proof_path = routing_proof_path(repo, config)
        if proof_path.exists():
            try:
                proof = load_json(proof_path)
                validate_routing_proof(
                    proof,
                    config,
                    maestra_version=__version__,
                    codex_version=current_codex,
                )
                proof_status = proof.get("status")
                add_check(
                    checks,
                    "routing_proof",
                    "pass" if proof_status == "pass" and current_codex else "warn" if proof_status == "pass" else "fail" if proof_status == "fail" else "warn",
                    f"{proof_status}: {proof_path}",
                )
            except MaestraError as exc:
                add_check(checks, "routing_proof", "fail", str(exc))
        else:
            add_check(checks, "routing_proof", "warn", "live routing probe has not been recorded")

    overall = "fail" if any(item["status"] == "fail" for item in checks) else "warn" if any(item["status"] == "warn" for item in checks) else "pass"
    result = {
        "status": overall,
        "checks": checks,
        "maestra_version": __version__,
        "expected_models": EXPECTED_MODELS,
        "codex_binary": binary,
        "codex_version": current_codex,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Maestra Doctor: {overall.upper()}")
        for item in checks:
            print(f"[{item['status'].upper():4}] {item['name']}: {item['detail']}")
    return 1 if overall == "fail" else 0


def require_routing_proof(repo: Path, config: dict[str, Any], *, allow_unverified: bool) -> None:
    path = routing_proof_path(repo, config)
    if not path.exists():
        if allow_unverified:
            return
        raise MaestraError("Live routing proof is missing; run $maestra:doctor or explicitly use --allow-unverified-routing")
    proof = load_json(path)
    _, parsed, detail = parse_codex_version()
    if parsed is None:
        if allow_unverified:
            return
        raise MaestraError(f"Cannot bind routing proof to current Codex runtime: {detail}")
    current_codex = codex_semver(parsed)
    validate_routing_proof(proof, config, maestra_version=__version__, codex_version=current_codex)
    status = proof["status"]
    if status == "fail":
        raise MaestraError("Routing proof records a known routing failure")
    if status != "pass" and not allow_unverified:
        raise MaestraError("Routing proof is unverified; explicit --allow-unverified-routing is required")


def cmd_record_routing_proof(args: argparse.Namespace) -> int:
    repo = normalize_repo(args.repo)
    config = load_config(repo)
    proof = load_json(Path(args.proof).expanduser().resolve())
    _, parsed, detail = parse_codex_version()
    if parsed is None:
        raise MaestraError(f"Cannot record version-bound routing proof: {detail}")
    current_codex = codex_semver(parsed)
    validate_routing_proof(proof, config, maestra_version=__version__, codex_version=current_codex)
    target = routing_proof_path(repo, config)
    atomic_write_json(target, proof)
    print(json.dumps({
        "status": "recorded",
        "routing_status": proof["status"],
        "maestra_version": __version__,
        "codex_version": current_codex,
        "path": str(target),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_verify_routing_proof(args: argparse.Namespace) -> int:
    repo = normalize_repo(args.repo)
    config = load_config(repo)
    _, parsed, detail = parse_codex_version()
    if parsed is None:
        raise MaestraError(f"Cannot record version-bound routing proof: {detail}")
    current_codex = codex_semver(parsed)
    sessions_dir = Path(args.sessions_dir).expanduser().resolve() if args.sessions_dir else default_sessions_dir()
    verification = verify_rollout_routing(
        sessions_dir=sessions_dir,
        not_before=args.not_before,
        terra_agent_path=args.terra_agent_path,
        luna_agent_path=args.luna_agent_path,
        reviewer_agent_path=args.reviewer_agent_path,
        expected_models=config["models"],
    )
    route_roles = {
        "main_to_terra": "orchestrator",
        "terra_to_luna": "implementer",
        "terra_to_reviewer": "reviewer",
    }
    proof: dict[str, Any] = {
        "schema_version": 2,
        "status": verification["status"],
        "checked_at": utc_now(),
        "maestra_version": __version__,
        "codex_version": current_codex,
        "evidence": verification["evidence"],
    }
    for proof_key, config_role in route_roles.items():
        expected = config["models"][config_role]
        proof[proof_key] = {
            "model": expected["model"],
            "reasoning_effort": expected["reasoning_effort"],
            "fork_turns": "none",
            "verified": verification["routes"][proof_key]["verified"],
        }
    validate_routing_proof(proof, config, maestra_version=__version__, codex_version=current_codex)
    target = routing_proof_path(repo, config)
    atomic_write_json(target, proof)
    print(json.dumps({
        "status": "recorded",
        "routing_status": proof["status"],
        "maestra_version": __version__,
        "codex_version": current_codex,
        "sessions_dir": str(sessions_dir),
        "rollouts": verification["rollouts"],
        "routes": verification["routes"],
        "path": str(target),
    }, ensure_ascii=False, indent=2))
    return 0 if proof["status"] == "pass" else 1


def cmd_create_run(args: argparse.Namespace) -> int:
    repo = normalize_repo(args.repo)
    config = load_config(repo)
    root = runtime_dir(repo, config)
    packet = load_json(Path(args.packet).expanduser().resolve())
    validate_run_packet(repo, root, packet, config, allow_dirty=args.allow_dirty)
    require_routing_proof(repo, config, allow_unverified=args.allow_unverified_routing)

    runs_root = root / "runs"
    if runs_root.exists():
        active: list[str] = []
        for state_path in sorted(runs_root.glob("R*/state.json")):
            state = load_json(state_path)
            if state.get("status") in {"ready", "running", "awaiting_main_gate", "plan_gap"}:
                active.append(str(state.get("run_id")))
        if active:
            raise MaestraError("Another Run requires completion/Main action first: " + ", ".join(active))

    run_id = packet["run_id"]
    run_dir = run_dir_for(repo, run_id, config)
    if run_dir.exists():
        raise MaestraError(f"Run already exists: {run_dir}")
    (run_dir / "tasks").mkdir(parents=True)
    atomic_write_json(run_dir / "run-packet.json", packet)
    now = utc_now()
    tasks = {
        task["id"]: {
            "title": task["title"],
            "status": "pending",
            "depends_on": list(task.get("depends_on", [])),
            "commit": None,
            "review_rounds": 0,
            "notes": [],
            "created_at": now,
            "updated_at": now,
        }
        for task in packet["tasks"]
    }
    state = {
        "schema_version": 1,
        "run_id": run_id,
        "title": packet["title"],
        "status": "ready",
        "base_commit": packet["base_commit"],
        "head_commit": packet["base_commit"],
        "created_at": now,
        "updated_at": now,
        "tasks": tasks,
        "gate": None,
        "plan_gap": None,
    }
    atomic_write_json(run_dir / "state.json", state)
    for task_id in tasks:
        (run_dir / "tasks" / task_id).mkdir(parents=True)
    print(json.dumps({"status": "created", "run_id": run_id, "run_dir": str(run_dir)}, ensure_ascii=False, indent=2))
    return 0


def cmd_task(args: argparse.Namespace) -> int:
    repo = normalize_repo(args.repo)
    config = load_config(repo)
    run_dir = run_dir_for(repo, args.run, config)
    task = update_task(
        repo=repo,
        run_dir=run_dir,
        task_id=args.task,
        new_status=args.status,
        commit=args.commit,
        note=args.note,
        max_major_findings=config["review"]["max_major_findings"],
    )
    print(json.dumps({"run_id": args.run, "task_id": args.task, **task}, ensure_ascii=False, indent=2))
    return 0


def cmd_record_verification(args: argparse.Namespace) -> int:
    repo = normalize_repo(args.repo)
    config = load_config(repo)
    run_dir = run_dir_for(repo, args.run, config)
    state = load_state(run_dir)
    if args.task not in state.get("tasks", {}):
        raise MaestraError(f"Unknown Task: {args.task}")
    result = load_json(Path(args.verification).expanduser().resolve())
    validate_verification(result)
    if result.get("run_id") != args.run or result.get("task_id") != args.task:
        raise MaestraError("VerificationResult run_id/task_id does not match command arguments")
    staged = staged_product_paths(repo)
    if not staged:
        raise MaestraError("Verification requires a non-empty staged Task candidate")
    unstaged = unstaged_product_paths(repo)
    if unstaged:
        raise MaestraError("All product changes must be staged before verification:\n" + "\n".join(unstaged))
    current_tree = index_tree(repo)
    if result.get("candidate_tree") != current_tree:
        raise MaestraError(f"VerificationResult candidate_tree {result.get('candidate_tree')} does not match current index tree {current_tree}")
    target = run_dir / "tasks" / args.task / "verification.json"
    if target.exists() and not args.replace:
        raise MaestraError("VerificationResult is already recorded; use --replace only after an intentional re-verification")
    atomic_write_json(target, result)
    print(json.dumps({
        "status": "recorded",
        "run_id": args.run,
        "task_id": args.task,
        "verification_status": result["status"],
        "path": str(target),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_freeze_review(args: argparse.Namespace) -> int:
    repo = normalize_repo(args.repo)
    config = load_config(repo)
    run_dir = run_dir_for(repo, args.run, config)
    state = load_state(run_dir)
    if args.task not in state.get("tasks", {}):
        raise MaestraError(f"Unknown Task: {args.task}")
    review = load_json(Path(args.review).expanduser().resolve())
    if review.get("run_id") != args.run or review.get("task_id") != args.task:
        raise MaestraError("Review run_id/task_id does not match command arguments")
    task_dir = run_dir / "tasks" / args.task
    verification_path = task_dir / "verification.json"
    if not verification_path.is_file():
        raise MaestraError("A passing recorded VerificationResult is required before independent review")
    verification = load_json(verification_path)
    validate_verification(verification)
    if verification.get("status") != "pass":
        raise MaestraError("Independent review requires a passing deterministic VerificationResult")
    unstaged = unstaged_product_paths(repo)
    if unstaged:
        raise MaestraError("All product changes must remain staged during review:\n" + "\n".join(unstaged))
    current_tree = index_tree(repo)
    expected_tree = verification.get("candidate_tree")
    if current_tree != expected_tree or review.get("candidate_tree") != expected_tree:
        raise MaestraError("Review, VerificationResult, and current Git index must reference the same candidate tree")
    result = freeze_review(
        review=review,
        task_dir=task_dir,
        max_rounds=config["review"]["max_rounds"],
        max_major_findings=config["review"]["max_major_findings"],
    )
    mark_review_round(run_dir, args.task, review["round"])
    print(json.dumps({"status": "recorded", **result}, ensure_ascii=False, indent=2))
    return 0


def cmd_report_plan_gap(args: argparse.Namespace) -> int:
    repo = normalize_repo(args.repo)
    config = load_config(repo)
    run_dir = run_dir_for(repo, args.run, config)
    state = load_state(run_dir)
    gap = load_json(Path(args.gap).expanduser().resolve())
    validate_plan_gap(gap)
    if gap["run_id"] != args.run:
        raise MaestraError("PlanGap.run_id does not match command arguments")
    task_id = gap.get("task_id")
    if isinstance(task_id, str) and task_id != "INTEGRATION":
        if task_id not in state.get("tasks", {}):
            raise MaestraError(f"Unknown Task in PlanGap: {task_id}")
        task = state["tasks"][task_id]
        if task.get("status") == "passed":
            raise MaestraError("A passed Task cannot be converted into PLAN_GAP; report the gap at Run/integration level")
        task["status"] = "plan_gap"
        task["updated_at"] = utc_now()
    target = run_dir / "plan-gap.json"
    atomic_write_json(target, gap)
    state["status"] = "plan_gap"
    state["plan_gap"] = {"path": str(target), "task_id": task_id, "recorded_at": utc_now()}
    save_state(run_dir, state)
    print(json.dumps({
        "status": "PLAN_GAP",
        "run_id": args.run,
        "task_id": task_id,
        "path": str(target),
        "next": "Main must amend the detailed Plan and obtain user approval; Terra must not infer the missing design.",
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_record_integration(args: argparse.Namespace) -> int:
    repo = normalize_repo(args.repo)
    config = load_config(repo)
    run_dir = run_dir_for(repo, args.run, config)
    state = load_state(run_dir)
    not_passed = [task_id for task_id, task in state.get("tasks", {}).items() if task.get("status") != "passed"]
    if not_passed:
        raise MaestraError("Integration review requires all planned Tasks to pass first: " + ", ".join(not_passed))
    dirty = product_status(repo)
    if dirty:
        raise MaestraError("Integration review requires a clean product working tree:\n" + "\n".join(dirty))

    verification = load_json(Path(args.verification).expanduser().resolve())
    review = load_json(Path(args.review).expanduser().resolve())
    validate_verification(verification)
    validate_review(review, max_major_findings=config["review"]["max_major_findings"])
    if verification.get("run_id") != args.run or verification.get("task_id") != "INTEGRATION":
        raise MaestraError("Integration VerificationResult must target this Run with task_id=INTEGRATION")
    if review.get("run_id") != args.run or review.get("task_id") != "INTEGRATION":
        raise MaestraError("Integration Review must target this Run with task_id=INTEGRATION")
    if verification.get("status") != "pass":
        raise MaestraError("Integration deterministic verification must PASS before Run completion")
    if review.get("round") != 1:
        raise MaestraError("Run Integration Review is one fresh bounded review and must declare round=1")
    if review.get("verdict") != "PASS":
        raise MaestraError("Integration Review must PASS; blocking integration findings return to Main as REMEDIATE/REPLAN")
    current_tree = index_tree(repo)
    if verification.get("candidate_tree") != current_tree or review.get("candidate_tree") != current_tree:
        raise MaestraError("Integration verification, review, and current product tree must match")

    verification_target = run_dir / "integration-verification.json"
    review_target = run_dir / "integration-review.json"
    if (verification_target.exists() or review_target.exists()) and not args.replace:
        raise MaestraError("Integration evidence already exists; use --replace only after Main-approved remediation")
    atomic_write_json(verification_target, verification)
    atomic_write_json(review_target, review)
    print(json.dumps({
        "status": "recorded",
        "run_id": args.run,
        "candidate_tree": current_tree,
        "verification": str(verification_target),
        "review": str(review_target),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_complete_run(args: argparse.Namespace) -> int:
    repo = normalize_repo(args.repo)
    config = load_config(repo)
    run_dir = run_dir_for(repo, args.run, config)
    state = load_state(run_dir)
    if state.get("status") not in {"ready", "running"}:
        raise MaestraError(f"Run cannot be completed from status: {state.get('status')}")
    not_passed = [task_id for task_id, task in state.get("tasks", {}).items() if task.get("status") != "passed"]
    if not_passed:
        raise MaestraError("All Tasks must pass before Run completion: " + ", ".join(not_passed))

    verification_path = run_dir / "integration-verification.json"
    review_path = run_dir / "integration-review.json"
    if not verification_path.is_file() or not review_path.is_file():
        raise MaestraError("Run completion requires recorded Run-level verification and fresh Sol Integration Review")
    verification = load_json(verification_path)
    review = load_json(review_path)
    validate_verification(verification)
    validate_review(review, max_major_findings=config["review"]["max_major_findings"])
    current_tree = index_tree(repo)
    if verification.get("status") != "pass" or review.get("verdict") != "PASS":
        raise MaestraError("Run integration evidence must PASS before completion")
    if verification.get("candidate_tree") != current_tree or review.get("candidate_tree") != current_tree:
        raise MaestraError("Run integration evidence does not match the current product tree")

    report_source = Path(args.report).expanduser().resolve()
    if not report_source.is_file():
        raise MaestraError(f"Run report does not exist: {report_source}")
    report_target = run_dir / "run-report.md"
    if report_source != report_target.resolve():
        shutil.copyfile(report_source, report_target)
    state["status"] = "awaiting_main_gate"
    state["head_commit"] = head_commit(repo)
    state["completed_at"] = utc_now()
    state["run_report"] = str(report_target)
    save_state(run_dir, state)
    print(json.dumps({
        "status": state["status"],
        "run_id": args.run,
        "head_commit": state["head_commit"],
        "report": str(report_target),
        "next": "Main must immediately perform the semantic gate in the same interaction; no extra user command is required.",
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_record_gate(args: argparse.Namespace) -> int:
    repo = normalize_repo(args.repo)
    config = load_config(repo)
    run_dir = run_dir_for(repo, args.run, config)
    state = load_state(run_dir)
    current = state.get("status")
    if current not in {"awaiting_main_gate", "plan_gap"}:
        raise MaestraError(f"Main Gate requires awaiting_main_gate or plan_gap status, got: {current}")
    if state.get("gate") is not None:
        raise MaestraError("Main Gate is already recorded")
    decision = args.decision
    if current == "plan_gap" and decision not in {"REPLAN", "USER_DECISION"}:
        raise MaestraError("PLAN_GAP may only resolve through REPLAN or USER_DECISION")
    state["gate"] = {"decision": decision, "note": args.note, "recorded_at": utc_now()}
    state["status"] = "gated"
    save_state(run_dir, state)
    print(json.dumps({"status": "gated", "run_id": args.run, "decision": decision}, ensure_ascii=False, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    repo = normalize_repo(args.repo)
    config = load_config(repo)
    runs_dir = runtime_dir(repo, config) / "runs"
    runs: list[dict[str, Any]] = []
    if runs_dir.exists():
        for state_path in sorted(runs_dir.glob("R*/state.json")):
            state = load_json(state_path)
            task_counts: dict[str, int] = {}
            for task in state.get("tasks", {}).values():
                task_counts[task.get("status", "unknown")] = task_counts.get(task.get("status", "unknown"), 0) + 1
            runs.append({
                "run_id": state.get("run_id"),
                "title": state.get("title"),
                "status": state.get("status"),
                "base_commit": state.get("base_commit"),
                "head_commit": state.get("head_commit"),
                "task_counts": task_counts,
                "gate": state.get("gate"),
                "plan_gap": state.get("plan_gap"),
            })
    result = {"repo": str(repo), "runtime_dir": str(runtime_dir(repo, config)), "runs": runs}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Maestra status: {repo}")
        if not runs:
            print("No Runs recorded.")
        for run in runs:
            print(f"{run['run_id']}  {run['status']}  {run['title']}  {run['task_counts']}")
    return 0


def cmd_paths(args: argparse.Namespace) -> int:
    repo = normalize_repo(args.repo)
    config = load_config(repo)
    root = runtime_dir(repo, config)
    print(json.dumps({
        "repo": str(repo),
        "runtime_dir": str(root),
        "spec": str(root / "spec.md"),
        "plan": str(root / "plan.md"),
        "routing_proof": str(root / "routing-proof.json"),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_hash(args: argparse.Namespace) -> int:
    print(sha256_file(Path(args.file).expanduser().resolve()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Thin runtime helper for the Maestra Codex plugin")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="initialize Maestra artifacts in Git metadata")
    init.add_argument("--repo", required=True)
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    doctor = sub.add_parser("doctor", help="run static preflight checks")
    doctor.add_argument("--repo", required=True)
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument("--allow-missing-codex", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    proof = sub.add_parser("record-routing-proof", help="validate and record version-bound live model-routing evidence")
    proof.add_argument("--repo", required=True)
    proof.add_argument("--proof", required=True)
    proof.set_defaults(func=cmd_record_routing_proof)

    verify_proof = sub.add_parser(
        "verify-routing-proof",
        help="verify and record exact routing from Codex rollout metadata",
    )
    verify_proof.add_argument("--repo", required=True)
    verify_proof.add_argument("--not-before", required=True, help="RFC3339 timestamp captured immediately before the live probe")
    verify_proof.add_argument("--terra-agent-path", required=True)
    verify_proof.add_argument("--luna-agent-path", required=True)
    verify_proof.add_argument("--reviewer-agent-path", required=True)
    verify_proof.add_argument("--sessions-dir", help="override the default CODEX_HOME/sessions location")
    verify_proof.set_defaults(func=cmd_verify_routing_proof)

    create = sub.add_parser("create-run", help="validate a detailed Main-owned RunPacket and create one Run")
    create.add_argument("--repo", required=True)
    create.add_argument("--packet", required=True)
    create.add_argument("--allow-dirty", action="store_true", help="experimental escape hatch; never implied")
    create.add_argument("--allow-unverified-routing", action="store_true", help="explicit experimental routing escape hatch")
    create.set_defaults(func=cmd_create_run)

    task = sub.add_parser("task", help="record a Task state transition")
    task.add_argument("--repo", required=True)
    task.add_argument("--run", required=True)
    task.add_argument("--task", required=True)
    task.add_argument("--status", required=True)
    task.add_argument("--commit")
    task.add_argument("--note")
    task.set_defaults(func=cmd_task)

    verification = sub.add_parser("record-verification", help="validate and record deterministic Task verification")
    verification.add_argument("--repo", required=True)
    verification.add_argument("--run", required=True)
    verification.add_argument("--task", required=True)
    verification.add_argument("--verification", required=True)
    verification.add_argument("--replace", action="store_true")
    verification.set_defaults(func=cmd_record_verification)

    freeze = sub.add_parser("freeze-review", help="record a bounded ReviewProposal and enforce Finding Freeze")
    freeze.add_argument("--repo", required=True)
    freeze.add_argument("--run", required=True)
    freeze.add_argument("--task", required=True)
    freeze.add_argument("--review", required=True)
    freeze.set_defaults(func=cmd_freeze_review)

    gap = sub.add_parser("report-plan-gap", help="stop a Run when execution requires a design decision absent from the approved Main Plan")
    gap.add_argument("--repo", required=True)
    gap.add_argument("--run", required=True)
    gap.add_argument("--gap", required=True)
    gap.set_defaults(func=cmd_report_plan_gap)

    integration = sub.add_parser("record-integration", help="record passing Run-level verification and fresh Sol Integration Review")
    integration.add_argument("--repo", required=True)
    integration.add_argument("--run", required=True)
    integration.add_argument("--verification", required=True)
    integration.add_argument("--review", required=True)
    integration.add_argument("--replace", action="store_true")
    integration.set_defaults(func=cmd_record_integration)

    complete = sub.add_parser("complete-run", help="mark a fully integrated Run ready for automatic Main semantic Gate")
    complete.add_argument("--repo", required=True)
    complete.add_argument("--run", required=True)
    complete.add_argument("--report", required=True)
    complete.set_defaults(func=cmd_complete_run)

    gate = sub.add_parser("record-gate", help="record Main semantic Gate decision")
    gate.add_argument("--repo", required=True)
    gate.add_argument("--run", required=True)
    gate.add_argument("--decision", required=True, choices=["CONTINUE", "REMEDIATE", "REPLAN", "USER_DECISION"])
    gate.add_argument("--note", required=True)
    gate.set_defaults(func=cmd_record_gate)

    status = sub.add_parser("status", help="show lightweight Run state")
    status.add_argument("--repo", required=True)
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    paths = sub.add_parser("paths", help="show resolved Maestra Git-metadata artifact paths")
    paths.add_argument("--repo", required=True)
    paths.set_defaults(func=cmd_paths)

    hash_cmd = sub.add_parser("hash", help="print SHA-256 of one artifact")
    hash_cmd.add_argument("file")
    hash_cmd.set_defaults(func=cmd_hash)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except MaestraError as exc:
        print(f"maestra: error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("maestra: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
