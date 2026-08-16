from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .errors import MaestraError
from .git import commit_exists, head_commit, product_status
from .io import read_simple_frontmatter, resolve_inside

RUN_ID_RE = re.compile(r"^R\d{3,}$")
TASK_ID_RE = re.compile(r"^T\d{3,}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
FINDING_ID_RE = re.compile(r"^(T\d{3,}|INTEGRATION|FINAL)-F\d{2,}$")

EXPECTED_MODELS = {
    "main": {"model": "gpt-5.6-sol", "reasoning_effort": "high"},
    "orchestrator": {"model": "gpt-5.6-terra", "reasoning_effort": "xhigh"},
    "implementer": {"model": "gpt-5.6-luna", "reasoning_effort": "max"},
    "reviewer": {"model": "gpt-5.6-sol", "reasoning_effort": "xhigh"},
    "final_reviewer": {"model": "gpt-5.6-sol", "reasoning_effort": "xhigh"},
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MaestraError(message)


def _string_list(value: Any, field: str, *, non_empty: bool = False) -> list[str]:
    require(isinstance(value, list), f"{field} must be a list")
    require(all(isinstance(item, str) and item.strip() for item in value), f"{field} must contain non-empty strings")
    if non_empty:
        require(bool(value), f"{field} must be non-empty")
    return value


def validate_config(config: dict[str, Any]) -> None:
    require(config.get("schema_version") == 1, "config.schema_version must be 1")
    artifact_dir = config.get("artifact_dir")
    require(isinstance(artifact_dir, str) and artifact_dir.strip(), "config.artifact_dir must be a string")
    require(not Path(artifact_dir).is_absolute(), "config.artifact_dir must be Git-metadata-relative")
    require(".." not in Path(artifact_dir).parts, "config.artifact_dir may not escape Git metadata")
    require(artifact_dir == "maestra", "config.artifact_dir must be maestra in v0.3")

    models = config.get("models")
    require(isinstance(models, dict), "config.models must be an object")
    for role, expected in EXPECTED_MODELS.items():
        require(models.get(role) == expected, f"config.models.{role} must be {expected}")

    review = config.get("review")
    require(isinstance(review, dict), "config.review must be an object")
    require(review.get("max_rounds") == 2, "review.max_rounds must be 2 in Maestra v0.3")
    max_findings = review.get("max_major_findings")
    require(isinstance(max_findings, int) and 1 <= max_findings <= 5, "review.max_major_findings must be 1..5")
    require(review.get("finding_freeze") is True, "review.finding_freeze must be true")
    require(review.get("minor_findings_block") is False, "review.minor_findings_block must be false")

    execution = config.get("execution")
    require(isinstance(execution, dict), "config.execution must be an object")
    require(execution.get("sequential_tasks") is True, "execution.sequential_tasks must be true in v0.3")
    require(execution.get("one_task_one_commit") is True, "execution.one_task_one_commit must be true")
    require(execution.get("terra_owns_commits") is True, "execution.terra_owns_commits must be true")
    require(execution.get("require_clean_worktree_at_run_start") is True, "execution.require_clean_worktree_at_run_start must be true")

    planning = config.get("planning")
    require(isinstance(planning, dict), "config.planning must be an object")
    require(planning.get("owner") == "main", "planning.owner must be main")
    require(planning.get("detailed_plan_required") is True, "planning.detailed_plan_required must be true")
    require(planning.get("terra_may_infer_missing_design") is False, "planning.terra_may_infer_missing_design must be false")


def validate_approved_artifact(runtime_root: Path, path_value: str, label: str) -> Path:
    path = resolve_inside(runtime_root, path_value, must_exist=True)
    metadata = read_simple_frontmatter(path)
    require(metadata.get("status") == "approved", f"{label} is not explicitly approved: {path}")
    require(metadata.get("approved_by") == "user", f"{label}.approved_by must be user: {path}")
    require(bool(metadata.get("approved_at")), f"{label}.approved_at is missing: {path}")
    return path


def _validate_model_route(packet: dict[str, Any], config: dict[str, Any]) -> None:
    models = packet.get("models")
    require(isinstance(models, dict), "RunPacket.models must be an object")
    for role in ("orchestrator", "implementer", "reviewer"):
        require(models.get(role) == config["models"][role], f"RunPacket.models.{role} does not match config")


def _validate_review_budget(packet: dict[str, Any], config: dict[str, Any]) -> None:
    review = packet.get("review")
    require(isinstance(review, dict), "RunPacket.review must be an object")
    for key in ("max_rounds", "max_major_findings", "finding_freeze", "minor_findings_block"):
        require(review.get(key) == config["review"][key], f"RunPacket.review.{key} does not match config")


def validate_routing_proof(
    proof: dict[str, Any],
    config: dict[str, Any],
    *,
    maestra_version: str | None = None,
    codex_version: str | None = None,
) -> None:
    require(proof.get("schema_version") == 2, "routing proof schema_version must be 2")
    require(proof.get("status") in {"pass", "fail", "unverified"}, "routing proof status is invalid")
    require(isinstance(proof.get("checked_at"), str) and proof["checked_at"].strip(), "routing proof checked_at is missing")
    proof_maestra = proof.get("maestra_version")
    proof_codex = proof.get("codex_version")
    require(isinstance(proof_maestra, str) and SEMVER_RE.fullmatch(proof_maestra) is not None, "routing proof maestra_version is invalid")
    require(isinstance(proof_codex, str) and SEMVER_RE.fullmatch(proof_codex) is not None, "routing proof codex_version is invalid")
    if maestra_version is not None:
        require(proof_maestra == maestra_version, f"routing proof was recorded for Maestra {proof_maestra}, current version is {maestra_version}")
    if codex_version is not None:
        require(proof_codex == codex_version, f"routing proof was recorded for Codex {proof_codex}, current version is {codex_version}")

    routes = {
        "main_to_terra": "orchestrator",
        "terra_to_luna": "implementer",
        "terra_to_reviewer": "reviewer",
    }
    for proof_key, config_role in routes.items():
        route = proof.get(proof_key)
        require(isinstance(route, dict), f"routing proof {proof_key} must be an object")
        expected = config["models"][config_role]
        require(route.get("model") == expected["model"], f"routing proof {proof_key}.model does not match config")
        require(route.get("reasoning_effort") == expected["reasoning_effort"], f"routing proof {proof_key}.reasoning_effort does not match config")
        require(route.get("fork_turns") == "none", f"routing proof {proof_key}.fork_turns must be none")
        require(isinstance(route.get("verified"), bool), f"routing proof {proof_key}.verified must be boolean")
    evidence = proof.get("evidence")
    require(isinstance(evidence, list) and all(isinstance(item, str) for item in evidence), "routing proof evidence must be a string list")
    if proof.get("status") == "pass":
        require(all(proof[key]["verified"] is True for key in routes), "pass routing proof requires every route to be verified")


def _validate_target_files(value: Any, field: str) -> None:
    files = _string_list(value, field, non_empty=True)
    for item in files:
        path = Path(item)
        require(not path.is_absolute(), f"{field} entries must be repository-relative: {item}")
        require(".." not in path.parts, f"{field} entries may not escape repository: {item}")


def validate_run_packet(
    repo: Path,
    runtime_root: Path,
    packet: dict[str, Any],
    config: dict[str, Any],
    *,
    allow_dirty: bool,
) -> None:
    require(packet.get("schema_version") == 2, "RunPacket.schema_version must be 2 for Maestra v0.3 detailed plans")
    run_id = packet.get("run_id")
    require(isinstance(run_id, str) and RUN_ID_RE.fullmatch(run_id) is not None, "Invalid Run ID")
    for key in ("title", "goal", "spec_path", "plan_path"):
        require(isinstance(packet.get(key), str) and packet[key].strip(), f"RunPacket.{key} must be non-empty")

    base = packet.get("base_commit")
    require(isinstance(base, str) and SHA_RE.fullmatch(base) is not None, "RunPacket.base_commit must be a 40-char lowercase SHA")
    require(commit_exists(repo, base), f"Run base commit does not exist: {base}")
    require(head_commit(repo) == base, f"HEAD does not match Run base commit {base}")

    validate_approved_artifact(runtime_root, packet["spec_path"], "Spec")
    validate_approved_artifact(runtime_root, packet["plan_path"], "Plan")

    acceptance = packet.get("acceptance_criteria")
    require(isinstance(acceptance, list) and acceptance, "RunPacket.acceptance_criteria must be a non-empty list")
    require(all(isinstance(item, str) and item.startswith("AC-") for item in acceptance), "Invalid acceptance criterion ID")
    _string_list(packet.get("architectural_invariants"), "RunPacket.architectural_invariants")
    _string_list(packet.get("non_goals"), "RunPacket.non_goals")
    _string_list(packet.get("integration_verification_plan"), "RunPacket.integration_verification_plan", non_empty=True)
    _string_list(packet.get("main_gate_questions"), "RunPacket.main_gate_questions", non_empty=True)

    tasks = packet.get("tasks")
    require(isinstance(tasks, list) and tasks, "RunPacket.tasks must be a non-empty list")
    seen: set[str] = set()
    for index, task in enumerate(tasks):
        require(isinstance(task, dict), f"Task {index} must be an object")
        task_id = task.get("id")
        require(isinstance(task_id, str) and TASK_ID_RE.fullmatch(task_id) is not None, f"Invalid Task ID at index {index}")
        require(task_id not in seen, f"Duplicate Task ID: {task_id}")
        for key in ("title", "objective"):
            require(isinstance(task.get(key), str) and task[key].strip(), f"{task_id}.{key} must be non-empty")
        dependencies = task.get("depends_on")
        require(isinstance(dependencies, list), f"{task_id}.depends_on must be a list")
        require(all(dep in seen for dep in dependencies), f"{task_id} depends on a missing or later Task")
        task_acs = task.get("acceptance_criteria")
        require(isinstance(task_acs, list) and task_acs, f"{task_id}.acceptance_criteria must be non-empty")
        require(set(task_acs).issubset(set(acceptance)), f"{task_id} references an AC outside the Run")

        _validate_target_files(task.get("target_files"), f"{task_id}.target_files")
        _string_list(task.get("implementation_steps"), f"{task_id}.implementation_steps", non_empty=True)
        _string_list(task.get("design_decisions"), f"{task_id}.design_decisions", non_empty=True)
        _string_list(task.get("verification_plan"), f"{task_id}.verification_plan", non_empty=True)
        _string_list(task.get("review_focus"), f"{task_id}.review_focus", non_empty=True)
        _string_list(task.get("expected_evidence"), f"{task_id}.expected_evidence", non_empty=True)
        for key in ("boundaries", "constraints", "non_goals"):
            _string_list(task.get(key), f"{task_id}.{key}")
        open_questions = task.get("open_questions")
        require(open_questions == [], f"PLAN_GAP: {task_id}.open_questions must be empty before execution")
        seen.add(task_id)

    _validate_model_route(packet, config)
    _validate_review_budget(packet, config)

    if not allow_dirty and config["execution"].get("require_clean_worktree_at_run_start", True):
        dirty = product_status(repo)
        require(not dirty, "Product working tree is not clean:\n" + "\n".join(dirty))


def validate_plan_gap(gap: dict[str, Any]) -> None:
    require(gap.get("schema_version") == 1, "PlanGap.schema_version must be 1")
    run_id = gap.get("run_id")
    require(isinstance(run_id, str) and RUN_ID_RE.fullmatch(run_id) is not None, "PlanGap.run_id is invalid")
    task_id = gap.get("task_id")
    require(task_id is None or (isinstance(task_id, str) and (TASK_ID_RE.fullmatch(task_id) is not None or task_id == "INTEGRATION")), "PlanGap.task_id is invalid")
    require(isinstance(gap.get("reason"), str) and gap["reason"].strip(), "PlanGap.reason must be non-empty")
    _string_list(gap.get("missing_plan_elements"), "PlanGap.missing_plan_elements", non_empty=True)
    _string_list(gap.get("evidence"), "PlanGap.evidence", non_empty=True)
    require(isinstance(gap.get("requested_main_action"), str) and gap["requested_main_action"].strip(), "PlanGap.requested_main_action must be non-empty")


def validate_verification(result: dict[str, Any]) -> None:
    require(result.get("schema_version") == 1, "VerificationResult.schema_version must be 1")
    run_id = result.get("run_id")
    subject_id = result.get("task_id")
    require(isinstance(run_id, str) and RUN_ID_RE.fullmatch(run_id) is not None, "VerificationResult.run_id is invalid")
    require(
        isinstance(subject_id, str) and (TASK_ID_RE.fullmatch(subject_id) or subject_id in {"INTEGRATION", "FINAL"}),
        "VerificationResult.task_id is invalid",
    )
    require(result.get("status") in {"pass", "fail", "blocked"}, "VerificationResult.status is invalid")
    candidate_tree = result.get("candidate_tree")
    require(isinstance(candidate_tree, str) and SHA_RE.fullmatch(candidate_tree) is not None, "VerificationResult.candidate_tree must be a 40-char lowercase tree SHA")
    commands = result.get("commands")
    require(isinstance(commands, list) and commands, "VerificationResult.commands must be a non-empty list")
    for index, command in enumerate(commands):
        require(isinstance(command, dict), f"VerificationResult.commands[{index}] must be an object")
        argv = command.get("argv")
        require(
            isinstance(argv, list) and argv and all(isinstance(item, str) and item for item in argv),
            f"VerificationResult.commands[{index}].argv must be a non-empty string list",
        )
        cwd = command.get("cwd")
        require(isinstance(cwd, str) and cwd.strip(), f"VerificationResult.commands[{index}].cwd must be non-empty")
        exit_code = command.get("exit_code")
        require(isinstance(exit_code, int), f"VerificationResult.commands[{index}].exit_code must be an integer")
        duration = command.get("duration_seconds")
        require(isinstance(duration, (int, float)) and duration >= 0, f"VerificationResult.commands[{index}].duration_seconds must be non-negative")
        log_path = command.get("log_path")
        require(isinstance(log_path, str) and log_path.strip(), f"VerificationResult.commands[{index}].log_path must be non-empty")
    summary = result.get("summary")
    require(isinstance(summary, list) and all(isinstance(item, str) for item in summary), "VerificationResult.summary must be a string list")
    if result.get("status") == "pass":
        failed = [index for index, command in enumerate(commands) if command.get("exit_code") != 0]
        require(not failed, "Pass VerificationResult contains non-zero command exit codes: " + ", ".join(map(str, failed)))


def validate_review(review: dict[str, Any], *, max_major_findings: int) -> None:
    require(review.get("schema_version") == 1, "Review.schema_version must be 1")
    run_id = review.get("run_id")
    task_id = review.get("task_id")
    round_number = review.get("round")
    require(isinstance(run_id, str) and RUN_ID_RE.fullmatch(run_id) is not None, "Review.run_id is invalid")
    require(isinstance(task_id, str) and (TASK_ID_RE.fullmatch(task_id) or task_id in {"INTEGRATION", "FINAL"}), "Review.task_id is invalid")
    require(round_number in {1, 2}, "Review.round must be 1 or 2")
    candidate_tree = review.get("candidate_tree")
    require(isinstance(candidate_tree, str) and SHA_RE.fullmatch(candidate_tree) is not None, "Review.candidate_tree must be a 40-char lowercase tree SHA")
    verdict = review.get("verdict")
    require(verdict in {"PASS", "CHANGES_REQUESTED", "ESCALATE"}, "Review.verdict is invalid")
    findings = review.get("findings")
    require(isinstance(findings, list), "Review.findings must be a list")
    ids: set[str] = set()
    blocking = 0
    for finding in findings:
        require(isinstance(finding, dict), "Each Finding must be an object")
        finding_id = finding.get("id")
        require(isinstance(finding_id, str) and FINDING_ID_RE.fullmatch(finding_id) is not None, f"Invalid Finding ID: {finding_id}")
        require(finding_id not in ids, f"Duplicate Finding ID: {finding_id}")
        ids.add(finding_id)
        severity = finding.get("severity")
        require(severity in {"critical", "major", "minor"}, f"Invalid severity for {finding_id}")
        if severity in {"critical", "major"}:
            if round_number == 1 or finding.get("resolution") not in {"resolved", "not_applicable"}:
                blocking += 1
        require(finding.get("category") in {"spec", "correctness", "security", "data_loss", "tests", "maintainability", "compatibility", "migration"}, f"Invalid category for {finding_id}")
        for key in ("location", "summary", "evidence", "required_change"):
            require(isinstance(finding.get(key), str) and finding[key].strip(), f"{finding_id}.{key} must be non-empty")
        introduced = finding.get("introduced_by_fix")
        require(isinstance(introduced, bool), f"{finding_id}.introduced_by_fix must be boolean")
        exception = finding.get("exception")
        require(exception in {None, "security", "data_loss", "fix_regression"}, f"Invalid exception for {finding_id}")
        resolution = finding.get("resolution")
        require(resolution in {None, "resolved", "unresolved", "not_applicable"}, f"Invalid resolution for {finding_id}")
    require(blocking <= max_major_findings, f"Review has {blocking} blocking findings; maximum is {max_major_findings}")
    if verdict == "PASS":
        require(blocking == 0, "PASS review may not contain critical or major findings")
    if verdict == "CHANGES_REQUESTED":
        require(blocking > 0, "CHANGES_REQUESTED requires at least one critical or major Finding")
    residual = review.get("residual_risks")
    require(isinstance(residual, list) and all(isinstance(item, str) for item in residual), "Review.residual_risks must be a string list")
