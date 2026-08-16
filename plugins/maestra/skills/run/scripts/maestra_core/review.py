from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import MaestraError
from .io import atomic_write_json, load_json, utc_now
from .schema import validate_review

ALLOWED_NEW_EXCEPTIONS = {"security", "data_loss", "fix_regression"}


def freeze_review(
    *,
    review: dict[str, Any],
    task_dir: Path,
    max_rounds: int,
    max_major_findings: int,
) -> dict[str, Any]:
    validate_review(review, max_major_findings=max_major_findings)
    round_number = review["round"]
    if round_number > max_rounds:
        raise MaestraError(f"Review round {round_number} exceeds max_rounds={max_rounds}")

    review_path = task_dir / f"review-round-{round_number}.json"
    if review_path.exists():
        raise MaestraError(f"Review round {round_number} is already recorded")

    freeze_path = task_dir / "finding-freeze.json"
    findings = review["findings"]

    if round_number == 1:
        if freeze_path.exists():
            raise MaestraError("Finding Freeze already exists before Round 1")
        frozen = {
            "schema_version": 1,
            "run_id": review["run_id"],
            "task_id": review["task_id"],
            "created_at": utc_now(),
            "finding_ids": [finding["id"] for finding in findings],
            "findings": [
                {
                    "id": finding["id"],
                    "severity": finding["severity"],
                    "category": finding["category"],
                }
                for finding in findings
            ],
        }
        atomic_write_json(freeze_path, frozen)
        atomic_write_json(review_path, review)
        return {"round": 1, "frozen_ids": frozen["finding_ids"], "new_exception_ids": []}

    if not freeze_path.exists():
        raise MaestraError("Round 2 requires an existing Finding Freeze from Round 1")
    frozen = load_json(freeze_path)
    frozen_ids = set(frozen.get("finding_ids", []))
    current_by_id = {finding["id"]: finding for finding in findings}
    missing = frozen_ids - set(current_by_id)
    if missing:
        raise MaestraError("Round 2 must evaluate every frozen Finding ID: " + ", ".join(sorted(missing)))

    new_ids: list[str] = []
    for finding_id, finding in current_by_id.items():
        if finding_id in frozen_ids:
            if finding.get("resolution") not in {"resolved", "unresolved", "not_applicable"}:
                raise MaestraError(f"Frozen Finding {finding_id} needs a Round 2 resolution")
            continue
        allowed = (
            finding.get("severity") == "critical"
            and finding.get("introduced_by_fix") is True
            and finding.get("exception") in ALLOWED_NEW_EXCEPTIONS
        )
        if not allowed:
            raise MaestraError(
                f"Round 2 introduced ordinary new Finding {finding_id}; Finding Freeze permits only critical fix-caused exceptions"
            )
        new_ids.append(finding_id)

    atomic_write_json(review_path, review)
    return {"round": 2, "frozen_ids": sorted(frozen_ids), "new_exception_ids": sorted(new_ids)}
