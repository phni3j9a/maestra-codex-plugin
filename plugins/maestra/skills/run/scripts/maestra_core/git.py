from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from .errors import MaestraError


def git_available() -> bool:
    return shutil.which("git") is not None


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    if not git_available():
        raise MaestraError("git executable was not found")
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git error"
        raise MaestraError(f"git {' '.join(args)} failed: {detail}")
    return completed


def repo_root(path: Path) -> Path:
    completed = run_git(path, "rev-parse", "--show-toplevel")
    return Path(completed.stdout.strip()).resolve()


def git_path(repo: Path, relative: str) -> Path:
    """Resolve a path in this checkout's Git metadata, including linked worktrees."""
    candidate = Path(relative)
    if not relative or candidate.is_absolute() or ".." in candidate.parts:
        raise MaestraError(f"Invalid Git metadata path: {relative!r}")
    raw = run_git(repo, "rev-parse", "--git-path", relative).stdout.strip()
    path = Path(raw)
    if not path.is_absolute():
        path = repo / path
    return path.resolve()


def head_commit(repo: Path) -> str:
    return run_git(repo, "rev-parse", "HEAD").stdout.strip()


def commit_exists(repo: Path, commit: str) -> bool:
    completed = run_git(repo, "cat-file", "-e", f"{commit}^{{commit}}", check=False)
    return completed.returncode == 0


def commit_message(repo: Path, commit: str) -> str:
    return run_git(repo, "show", "-s", "--format=%B", commit).stdout


def commit_trailer(message: str, key: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(key)}:\s*(\S+)\s*$", re.MULTILINE)
    matches = pattern.findall(message)
    if not matches:
        return None
    if len(set(matches)) != 1:
        raise MaestraError(f"Commit contains conflicting {key} trailers")
    return matches[-1]


def index_tree(repo: Path) -> str:
    """Return the tree object represented by the normal Git index."""
    return run_git(repo, "write-tree").stdout.strip()


def commit_tree(repo: Path, commit: str) -> str:
    return run_git(repo, "show", "-s", "--format=%T", commit).stdout.strip()


def staged_product_paths(repo: Path) -> list[str]:
    completed = run_git(repo, "diff", "--cached", "--name-only", "-z")
    return sorted(path for path in completed.stdout.split("\0") if path)


def unstaged_product_paths(repo: Path) -> list[str]:
    tracked = run_git(repo, "diff", "--name-only", "-z").stdout.split("\0")
    untracked = run_git(repo, "ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")
    return sorted({path for path in [*tracked, *untracked] if path})


def product_status(repo: Path) -> list[str]:
    """Return all product working-tree changes. Maestra state is outside the worktree."""
    completed = run_git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    return [line for line in completed.stdout.splitlines() if line]
