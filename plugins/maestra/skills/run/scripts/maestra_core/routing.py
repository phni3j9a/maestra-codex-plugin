from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .errors import MaestraError


@dataclass(frozen=True)
class RolloutMeta:
    path: Path
    thread_id: str
    session_id: str
    parent_thread_id: str | None
    agent_path: str | None
    timestamp: str
    thread_source: str | None
    source: dict[str, Any]


def default_sessions_dir() -> Path:
    configured = os.environ.get("CODEX_HOME")
    codex_home = Path(configured).expanduser() if configured else Path.home() / ".codex"
    return (codex_home / "sessions").resolve()


def parse_rfc3339(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MaestraError(f"{field} must be an RFC3339 timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise MaestraError(f"{field} must include a timezone: {value}")
    return parsed.astimezone(timezone.utc)


def validate_agent_paths(terra: str, luna: str, reviewer: str) -> None:
    values = {"terra": terra, "luna": luna, "reviewer": reviewer}
    for label, value in values.items():
        if not value.startswith("/") or value.endswith("/") or "//" in value:
            raise MaestraError(f"{label} agent path must be a canonical absolute task path: {value}")
    if len(set(values.values())) != len(values):
        raise MaestraError("Routing probe agent paths must be distinct")
    if luna.rsplit("/", 1)[0] != terra:
        raise MaestraError("Luna probe must be a direct child of the Terra probe")
    if reviewer.rsplit("/", 1)[0] != terra:
        raise MaestraError("Reviewer probe must be a direct child of the Terra probe")


def _json_lines(path: Path) -> Iterator[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    # A live root rollout may have an incomplete trailing line while Doctor reads it.
                    continue
                if isinstance(item, dict):
                    yield item
    except OSError:
        return


def _read_meta(path: Path) -> RolloutMeta | None:
    for item in _json_lines(path):
        if item.get("type") != "session_meta" or not isinstance(item.get("payload"), dict):
            continue
        payload = item["payload"]
        thread_id = payload.get("id")
        session_id = payload.get("session_id")
        timestamp = payload.get("timestamp") or item.get("timestamp")
        if not all(isinstance(value, str) and value for value in (thread_id, session_id, timestamp)):
            return None
        parent = payload.get("parent_thread_id")
        agent_path = payload.get("agent_path")
        source = payload.get("source")
        return RolloutMeta(
            path=path,
            thread_id=thread_id,
            session_id=session_id,
            parent_thread_id=parent if isinstance(parent, str) else None,
            agent_path=agent_path if isinstance(agent_path, str) else None,
            timestamp=timestamp,
            thread_source=payload.get("thread_source") if isinstance(payload.get("thread_source"), str) else None,
            source=source if isinstance(source, dict) else {},
        )
    return None


def _read_details(meta: RolloutMeta) -> dict[str, Any]:
    contexts: list[dict[str, str | None]] = []
    spawn_calls: list[dict[str, str | None]] = []
    for item in _json_lines(meta.path):
        payload = item.get("payload")
        if item.get("type") == "turn_context" and isinstance(payload, dict):
            contexts.append({
                "turn_id": payload.get("turn_id") if isinstance(payload.get("turn_id"), str) else None,
                "model": payload.get("model") if isinstance(payload.get("model"), str) else None,
                "effort": payload.get("effort") if isinstance(payload.get("effort"), str) else None,
            })
            continue
        if (
            item.get("type") == "response_item"
            and isinstance(payload, dict)
            and payload.get("type") == "function_call"
            and payload.get("name") == "spawn_agent"
        ):
            raw_arguments = payload.get("arguments")
            try:
                arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            except json.JSONDecodeError:
                arguments = None
            if isinstance(arguments, dict):
                spawn_calls.append({
                    "task_name": arguments.get("task_name") if isinstance(arguments.get("task_name"), str) else None,
                    "model": arguments.get("model") if isinstance(arguments.get("model"), str) else None,
                    "reasoning_effort": arguments.get("reasoning_effort") if isinstance(arguments.get("reasoning_effort"), str) else None,
                    "fork_turns": arguments.get("fork_turns") if isinstance(arguments.get("fork_turns"), str) else None,
                })
    return {"contexts": contexts, "spawn_calls": spawn_calls}


def _spawn_source_state(child: RolloutMeta, parent: RolloutMeta) -> tuple[str, str]:
    if child.parent_thread_id is None:
        return "unverified", "session_meta.parent_thread_id is missing"
    if child.parent_thread_id != parent.thread_id:
        return "fail", f"parent_thread_id {child.parent_thread_id!r} does not match {parent.thread_id}"
    subagent = child.source.get("subagent")
    thread_spawn = subagent.get("thread_spawn") if isinstance(subagent, dict) else None
    if not isinstance(thread_spawn, dict):
        return "unverified", "session_meta.source.subagent.thread_spawn is missing"
    observed_parent = thread_spawn.get("parent_thread_id")
    observed_path = thread_spawn.get("agent_path")
    if observed_parent is None or observed_path is None:
        return "unverified", "thread_spawn metadata omits parent_thread_id or agent_path"
    if observed_parent != parent.thread_id or observed_path != child.agent_path:
        return "fail", "thread_spawn metadata does not match the selected parent/agent path"
    if child.thread_source is None:
        return "unverified", "session_meta.thread_source is missing"
    if child.thread_source != "subagent":
        return "fail", f"thread_source is {child.thread_source!r}, expected 'subagent'"
    return "pass", f"parent {parent.thread_id} -> child {child.thread_id}"


def _context_state(details: dict[str, Any], expected: dict[str, str]) -> tuple[str, str]:
    contexts = details["contexts"]
    if not contexts:
        return "unverified", "turn_context is missing"
    incomplete = [item for item in contexts if item.get("model") is None or item.get("effort") is None]
    if incomplete:
        return "unverified", "turn_context omits model or effort"
    observed = {(item["model"], item["effort"]) for item in contexts}
    expected_pair = (expected["model"], expected["reasoning_effort"])
    if observed != {expected_pair}:
        rendered = ", ".join(f"{model}/{effort}" for model, effort in sorted(observed))
        return "fail", f"observed turn_context {rendered}; expected {expected_pair[0]}/{expected_pair[1]}"
    return "pass", f"turn_context {expected_pair[0]}/{expected_pair[1]}"


def _call_state(parent_details: dict[str, Any], child: RolloutMeta, expected: dict[str, str]) -> tuple[str, str]:
    task_name = child.agent_path.rsplit("/", 1)[-1] if child.agent_path else None
    calls = [item for item in parent_details["spawn_calls"] if item.get("task_name") == task_name]
    if not calls:
        return "unverified", f"spawn_agent call for {task_name!r} is missing"
    if len(calls) != 1:
        return "fail", f"found {len(calls)} spawn_agent calls for {task_name!r}; expected exactly one"
    call = calls[0]
    wanted = {
        "model": expected["model"],
        "reasoning_effort": expected["reasoning_effort"],
        "fork_turns": "none",
    }
    observed = {key: call.get(key) for key in wanted}
    if observed != wanted:
        return "fail", f"spawn_agent arguments {observed!r}; expected {wanted!r}"
    return "pass", f"spawn_agent requested {wanted['model']}/{wanted['reasoning_effort']} with fork_turns=none"


def _route_state(
    *,
    parent: RolloutMeta,
    child: RolloutMeta,
    parent_details: dict[str, Any],
    child_details: dict[str, Any],
    expected: dict[str, str],
) -> dict[str, Any]:
    checks = [
        _spawn_source_state(child, parent),
        _call_state(parent_details, child, expected),
        _context_state(child_details, expected),
    ]
    state = "fail" if any(item[0] == "fail" for item in checks) else "pass" if all(item[0] == "pass" for item in checks) else "unverified"
    return {
        "state": state,
        "verified": state == "pass",
        "detail": "; ".join(item[1] for item in checks),
    }


def _unverified_result(detail: str) -> dict[str, Any]:
    return {
        "status": "unverified",
        "routes": {
            "main_to_terra": {"state": "unverified", "verified": False, "detail": detail},
            "terra_to_luna": {"state": "unverified", "verified": False, "detail": detail},
            "terra_to_reviewer": {"state": "unverified", "verified": False, "detail": detail},
        },
        "evidence": [detail],
        "rollouts": {},
    }


def verify_rollout_routing(
    *,
    sessions_dir: Path,
    not_before: str,
    terra_agent_path: str,
    luna_agent_path: str,
    reviewer_agent_path: str,
    expected_models: dict[str, dict[str, str]],
) -> dict[str, Any]:
    validate_agent_paths(terra_agent_path, luna_agent_path, reviewer_agent_path)
    threshold = parse_rfc3339(not_before, field="not_before")
    sessions_dir = sessions_dir.expanduser().resolve()
    if not sessions_dir.is_dir():
        return _unverified_result(f"Codex sessions directory is unavailable: {sessions_dir}")

    requested_paths = [terra_agent_path, luna_agent_path, reviewer_agent_path]
    metas: list[RolloutMeta] = []
    for path in sorted(sessions_dir.rglob("rollout-*.jsonl")):
        if path.is_symlink() or not path.is_file():
            continue
        meta = _read_meta(path)
        if meta:
            metas.append(meta)

    candidates: dict[str, list[RolloutMeta]] = {path: [] for path in requested_paths}
    for meta in metas:
        if meta.agent_path not in requested_paths:
            continue
        try:
            observed_at = parse_rfc3339(meta.timestamp, field=f"session timestamp in {meta.path.name}")
        except MaestraError:
            continue
        if observed_at >= threshold:
            candidates[meta.agent_path].append(meta)

    triples: list[tuple[RolloutMeta, RolloutMeta, RolloutMeta]] = []
    for terra in candidates[terra_agent_path]:
        for luna in candidates[luna_agent_path]:
            for reviewer in candidates[reviewer_agent_path]:
                if (
                    luna.session_id == terra.session_id
                    and reviewer.session_id == terra.session_id
                ):
                    triples.append((terra, luna, reviewer))
    if not triples:
        counts = {path: len(items) for path, items in candidates.items()}
        return _unverified_result(f"No post-{not_before} rollout triple matches the requested agent paths and root session: {counts}")

    triples.sort(key=lambda item: parse_rfc3339(item[0].timestamp, field="Terra session timestamp"))
    terra, luna, reviewer = triples[-1]
    roots = [meta for meta in metas if meta.thread_id == terra.session_id]
    if len(roots) != 1:
        return _unverified_result(f"Expected one root rollout for session {terra.session_id}, found {len(roots)}")
    root = roots[0]

    root_details = _read_details(root)
    terra_details = _read_details(terra)
    luna_details = _read_details(luna)
    reviewer_details = _read_details(reviewer)
    routes = {
        "main_to_terra": _route_state(
            parent=root,
            child=terra,
            parent_details=root_details,
            child_details=terra_details,
            expected=expected_models["orchestrator"],
        ),
        "terra_to_luna": _route_state(
            parent=terra,
            child=luna,
            parent_details=terra_details,
            child_details=luna_details,
            expected=expected_models["implementer"],
        ),
        "terra_to_reviewer": _route_state(
            parent=terra,
            child=reviewer,
            parent_details=terra_details,
            child_details=reviewer_details,
            expected=expected_models["reviewer"],
        ),
    }
    status = "fail" if any(item["state"] == "fail" for item in routes.values()) else "pass" if all(item["verified"] for item in routes.values()) else "unverified"
    evidence = [
        f"Selected Codex session {root.thread_id} after probe threshold {not_before}.",
        f"main_to_terra: {routes['main_to_terra']['detail']} ({terra.path.name}).",
        f"terra_to_luna: {routes['terra_to_luna']['detail']} ({luna.path.name}).",
        f"terra_to_reviewer: {routes['terra_to_reviewer']['detail']} ({reviewer.path.name}).",
    ]
    return {
        "status": status,
        "routes": routes,
        "evidence": evidence,
        "rollouts": {
            "root": str(root.path),
            "terra": str(terra.path),
            "luna": str(luna.path),
            "reviewer": str(reviewer.path),
        },
    }
