# Changelog

## Unreleased

- Made Main→Terra and Terra→Luna/Reviewer waits event-driven with an explicit 60-minute timeout that returns early on mailbox updates.
- Prohibited short polling and routine `list_agents` calls during healthy Runs.
- Added staged timeout diagnostics: lightweight Maestra status for Main, Task-local evidence for Terra, and a single path-scoped `list_agents` call only when liveness remains unclear.
- Added regression coverage for both orchestration layers.

## 0.3.2 — 2026-08-15

Rollout-backed Doctor verification release.

- Added deterministic `verify-routing-proof` support for Codex rollout metadata.
- Bound each route to the recorded parent/child thread chain, exact `spawn_agent` arguments, and observed child `turn_context.model` / `turn_context.effort`.
- Distinguished affirmative routing mismatches (`fail`) from unavailable or ambiguous metadata (`unverified`).
- Kept prompts, messages, summaries, and reasoning out of routing evidence.
- Added regression coverage for successful routing, observed model mismatch, and missing rollout metadata.

## 0.3.1 — 2026-08-15

Explicit opt-in routing release.

- Added `$maestra:using-maestra` as the only full-workflow entry.
- Set all seven Maestra Skills to `policy.allow_implicit_invocation: false`.
- Kept Spec, Plan, Run, Gate, and Finish independent; Main now loads each exact sibling `SKILL.md` after explicit activation instead of requiring a user command at every phase.
- Made Doctor and standalone phase recovery workflow-neutral.
- Added no hooks, session-wide injection, activation database, or custom router runtime.
- Preserved v0.3 context isolation, exact routes, Finding Freeze, bounded review, candidate-tree/commit binding, Run Integration Review, Main Gate, and risk-based Final Review.
- Expanded layout, metadata, hook-absence, validator, and both-ZIP packaging coverage.

## 0.3.0 — 2026-08-15

Planning ownership release.

- Main Sol now owns the **full detailed implementation Plan**, including architecture, Run/Task decomposition, target components, implementation steps, design decisions, verification strategy, and review focus.
- Plan approval is the natural context boundary; `/compact` is recommended immediately afterward, and execution re-reads approved Spec/Plan artifacts instead of relying on the compact summary.
- RunPacket schema v2 requires detailed Task fields and rejects unresolved `open_questions` before Terra is spawned.
- Added fail-closed `PLAN_GAP`: Terra must stop instead of inventing missing architecture, implementation strategy, migration, or test strategy. Main resolves the gap through `REPLAN` or `USER_DECISION`.
- Terra is now explicitly execution-only: sequencing, exact command resolution, verification, reviewer lifecycle/adjudication, Git commits, integration review, and RunReport.
- Runtime artifacts moved out of the product tree to `git rev-parse --git-path maestra`, including linked-worktree support.
- Routing proof schema v2 binds successful Doctor results to both Codex version and Maestra version.
- Run completion now mechanically requires passing Run-level deterministic verification and fresh Sol Integration Review bound to the same candidate tree.
- Normal `$maestra:run` flows directly into the Main semantic gate; `$maestra:gate` remains available for recovery/explicit invocation.
- Whole-branch final Sol review is risk-based rather than mandatory for every low-risk single-Run change.
- Retained Terra review adjudication, Finding Freeze, maximum two Task review rounds, and one-Task-one-commit candidate-tree protection.
- Added/updated regression coverage for detailed Plan validation, PLAN_GAP, integration gating, version-bound routing proof, and linked worktrees.
