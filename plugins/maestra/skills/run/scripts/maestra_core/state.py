from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import MaestraError
from .git import commit_exists, commit_message, commit_trailer, commit_tree, head_commit, product_status
from .io import atomic_write_json, load_json, utc_now
from .schema import validate_review, validate_verification

TASK_STATUSES = {
    "pending",
    "implementing",
    "verifying",
    "reviewing",
    "fixing",
    "passed",
    "blocked",
    "escalated",
    "plan_gap",
}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"implementing", "blocked", "escalated", "plan_gap"},
    "implementing": {"verifying", "blocked", "escalated", "plan_gap"},
    "verifying": {"reviewing", "fixing", "blocked", "escalated", "plan_gap"},
    "reviewing": {"fixing", "passed", "blocked", "escalated", "plan_gap"},
    "fixing": {"verifying", "blocked", "escalated", "plan_gap"},
    "blocked": {"implementing", "escalated", "plan_gap"},
    "escalated": set(),
    "plan_gap": set(),
    "passed": set(),
}


def load_state(run_dir: Path) -> dict[str, Any]:
    return load_json(run_dir / "state.json")


def save_state(run_dir: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    atomic_write_json(run_dir / "state.json", state)


def update_task(
    *,
    repo: Path,
    run_dir: Path,
    task_id: str,
    new_status: str,
    commit: str | None,
    note: str | None,
    max_major_findings: int,
) -> dict[str, Any]:
    if new_status not in TASK_STATUSES:
        raise MaestraError(f"Invalid Task status: {new_status}")
    state = load_state(run_dir)
    tasks = state.get("tasks")
    if not isinstance(tasks, dict) or task_id not in tasks:
        raise MaestraError(f"Unknown Task: {task_id}")
    task = tasks[task_id]
    current = task.get("status")
    if new_status != current and new_status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise MaestraError(f"Invalid Task transition: {current} -> {new_status}")

    if new_status == "passed":
        task_dir = run_dir / "tasks" / task_id
        verification_path = task_dir / "verification.json"
        if not verification_path.is_file():
            raise MaestraError("A recorded VerificationResult is required before marking a Task passed")
        verification = load_json(verification_path)
        validate_verification(verification)
        if verification.get("run_id") != state["run_id"] or verification.get("task_id") != task_id:
            raise MaestraError("VerificationResult run_id/task_id does not match the Task")
        if verification.get("status") != "pass":
            raise MaestraError("Latest deterministic verification must pass before marking a Task passed")

        review_rounds = int(task.get("review_rounds", 0))
        if review_rounds < 1:
            raise MaestraError("At least one validated independent review is required before marking a Task passed")
        review_path = task_dir / f"review-round-{review_rounds}.json"
        if not review_path.is_file():
            raise MaestraError("Latest validated independent Review evidence is missing")
        review = load_json(review_path)
        validate_review(review, max_major_findings=max_major_findings)
        if review.get("verdict") != "PASS":
            raise MaestraError("Latest validated independent review must PASS before marking a Task passed")
        candidate_tree = verification.get("candidate_tree")
        if review.get("candidate_tree") != candidate_tree:
            raise MaestraError("Verification and Review refer to different candidate trees")

        if not commit:
            raise MaestraError("--commit is required when marking a Task passed")
        if not commit_exists(repo, commit):
            raise MaestraError(f"Task commit does not exist: {commit}")
        if head_commit(repo) != commit:
            raise MaestraError("Task commit must be the current HEAD when marked passed")
        if commit_tree(repo, commit) != candidate_tree:
            raise MaestraError("Task commit tree does not match the verified and reviewed candidate tree")
        dirty = product_status(repo)
        if dirty:
            raise MaestraError("Product working tree must be clean when marking a Task passed:\n" + "\n".join(dirty))
        message = commit_message(repo, commit)
        if commit_trailer(message, "Maestra-Run") != state["run_id"]:
            raise MaestraError("Task commit has a missing or mismatched Maestra-Run trailer")
        if commit_trailer(message, "Maestra-Task") != task_id:
            raise MaestraError("Task commit has a missing or mismatched Maestra-Task trailer")
        for other_id, other in tasks.items():
            if other_id != task_id and other.get("commit") == commit:
                raise MaestraError(f"Commit {commit} is already assigned to {other_id}")
        dependencies = task.get("depends_on", [])
        unmet = [dep for dep in dependencies if tasks.get(dep, {}).get("status") != "passed"]
        if unmet:
            raise MaestraError("Cannot pass Task before dependencies: " + ", ".join(unmet))
        task["commit"] = commit

    task["status"] = new_status
    task["updated_at"] = utc_now()
    if new_status in {"implementing", "verifying", "reviewing", "fixing"}:
        state["status"] = "running"
    elif new_status == "plan_gap":
        state["status"] = "plan_gap"
    if note:
        task.setdefault("notes", []).append({"at": utc_now(), "text": note})
    save_state(run_dir, state)
    return task


def mark_review_round(run_dir: Path, task_id: str, round_number: int) -> None:
    state = load_state(run_dir)
    try:
        task = state["tasks"][task_id]
    except (KeyError, TypeError) as exc:
        raise MaestraError(f"Unknown Task: {task_id}") from exc
    task["review_rounds"] = max(int(task.get("review_rounds", 0)), round_number)
    task["updated_at"] = utc_now()
    save_state(run_dir, state)
