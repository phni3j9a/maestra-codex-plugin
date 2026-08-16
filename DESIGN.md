# Maestra v0.3 Design

## 1. Design center

Maestra v0.3は、**最も知的負荷の高いplanningをMain Solから切り離さない**ことを中心に設計します。Context削減のためにplanning品質を下げるのではなく、Plan確定後を自然なcompact boundaryとし、その後のexecution detailだけを下位agentへ隔離します。

```text
Main Sol = Think & Decide
Terra    = Coordinate & Control
Luna     = Implement
Sol      = Inspect
```

## 2. Main-owned Detailed Plan

Main SolはSpec承認後、実装者へ渡せるレベルのDetailed Planを作ります。各Taskには少なくとも以下が必要です。

- purpose / covered requirements
- target files or modules
- implementation steps
- design decisions and invariants
- boundaries / constraints / non-goals
- verification plan
- review focus
- expected evidence
- `open_questions: []`

Runにはintegration verification planとMain Gate questionsが必要です。

Plan承認後は`/compact`を推奨します。実行開始時はcompact summaryではなくapproved Spec/Planを再読込します。

## 3. Responsibility boundaries

### Main / Sol high

Owns:
- user dialogue and requirement clarification
- specification
- architecture
- **all substantive implementation planning**
- Run/Task decomposition and dependency order
- target components/files at planning granularity
- implementation strategy and design decisions
- verification strategy and review focus
- user approvals
- semantic gate, replanning, final report

### Orchestrator / Terra xhigh

Owns exactly one Run:
- execute approved Task order
- mechanically translate Plan fields into TaskPackets
- resolve exact command spelling from project scripts/conventions
- spawn Luna and Sol with fresh context
- authoritative deterministic verification
- reviewer finding adjudication
- one-task-one-commit Git boundary
- Run integration verification/review
- concise RunReport

Terra does **not** own architecture, implementation strategy, Task decomposition, migration design, or test strategy invention.

### `PLAN_GAP`

When execution needs a substantive decision not present in the approved Plan, Terra must stop and emit `PLAN_GAP`. Examples:

- choosing between two architectures
- adding an unplanned component or persistence layer
- changing public API or migration strategy
- moving responsibility between layers
- selecting a materially different testing approach
- broadening Task purpose beyond the approved Plan

Main then chooses `REPLAN` or `USER_DECISION`; Terra may not continue by guessing. A revised Plan is re-approved, and `/compact` is recommended again before resuming.

### Implementer / Luna max

Owns one Task or one accepted FixPacket. Luna follows the approved implementation steps/design decisions, does not commit, does not redesign the Plan, and reports scope/design gaps rather than improvising.

### Reviewer / Sol xhigh

Receives a fresh context and reviews the candidate against Spec + Detailed Plan + verification evidence. Reviewer may identify a missing planning decision, but it does not supply a replacement architecture. Such a finding becomes an escalation to Main.

## 4. Context contracts

### Event-driven coordination waits

Both orchestration boundaries wait on mailbox events rather than polling. Main waits for Terra, and Terra waits for each direct Luna/Reviewer child, using `wait_agent` with `timeout_ms: 3600000`; completion and messages return early. Healthy Runs do not call `list_agents`. After a real 60-minute timeout, Main checks lightweight Run state and Terra checks Task-local process evidence before either performs at most one path-scoped agent-tree inspection. This prevents repeated context ingestion of completed descendant payloads without delaying useful completion signals.

### Main → Terra

- approved Spec path
- approved Detailed Plan path
- one RunPacket copied from the Detailed Plan
- repository/base commit
- review budget and artifact path

Not included: full user conversation, discarded alternatives, prior agent transcripts.

### Terra → Luna

- one TaskPacket that preserves Main-owned purpose, targets, steps, decisions, constraints, verification intent
- mechanical repository context required to perform it

### Terra → Reviewer

- Task contract
- candidate diff/tree
- verification result
- applicable Spec/Plan excerpts
- review rubric / frozen finding IDs

Not included: Luna transcript or private reasoning.

### Terra → Main

- RunReport
- integration review summary
- residual risk
- explicit PLAN_GAP/escalations

## 5. Review convergence

Round 1 freezes stable Finding IDs. Terra adjudicates:

- `ACCEPT` — required by approved Task/Plan
- `DEFER` — valid but explicitly outside current scope
- `REJECT` — unsupported, duplicate, preference-only, or contrary to approved design
- `ESCALATE` — needs Main/user planning or product decision

Round 2 primarily checks accepted frozen findings. New ordinary findings are prohibited; only fix-introduced critical security/data-loss/clear regression findings may be added. No Round 3.

An accepted fix may repair implementation **within already-approved design**. If the repair itself requires a new design choice, it becomes `PLAN_GAP`/`ESCALATE`, not a Terra-authored repair plan.

## 6. Thin deterministic core

The helper intentionally enforces only boundaries that should not rely on model obedience:

- configuration and exact model routes
- Detailed RunPacket schema completeness
- rollout-backed routing proof bound to exact spawn arguments, observed child model/effort, and Codex + Maestra versions
- runtime artifacts under Git metadata
- PLAN_GAP terminal state for Terra
- lightweight Task/Run state
- Finding Freeze
- verification/review candidate-tree identity
- commit trailer/tree identity
- mandatory Run integration evidence
- Main Gate transition rules

It does not implement a scheduler, repository lease, approval hash ledger, fsync/CAS transaction engine, exact-tree `commit-tree` workflow, or full crash-atomic recovery.

## 7. Git and runtime boundary

Runtime state is resolved with:

```text
git rev-parse --git-path maestra
```

so Maestra state never pollutes product diffs and linked worktrees get checkout-specific metadata.

Product invariants:
- Run starts from a clean product working tree
- Luna never commits
- Reviewer never mutates repository state
- Terra stages intended Task files only
- Verification and Review bind to staged `candidate_tree`
- Terra commits one accepted Task at a time
- Run integration evidence binds to final Run tree
- unexpected mutations stop rather than auto-reset user work

## 8. Routing safety

```text
Main  → Terra: gpt-5.6-terra / xhigh / fork_turns:none
Terra → Luna : gpt-5.6-luna  / max   / fork_turns:none
Terra → Sol  : gpt-5.6-sol   / xhigh / fork_turns:none
```

Silent model fallback is a failure. `$maestra:doctor` performs the live routing probe, then the deterministic helper matches the post-threshold Codex rollouts by canonical agent path, root session, and parent-thread chain. It verifies recorded `spawn_agent` model/effort/`fork_turns` arguments against each child `turn_context.model`/`effort`; prompts and reasoning are never copied into proof evidence. An observed mismatch is `fail`, while missing or ambiguous rollout metadata is `unverified`. Proof is invalidated when Codex or Maestra version changes.

## 9. Final review

Run-level Integration Review is always required. Whole-branch Final Sol Review is **risk-based**: required for cross-Run/cross-cutting, security, migration/public API, or remediation-heavy changes; optional for a low-risk single Run whose Task and Integration Reviews already cover the final tree. Main always performs the final semantic check.

## 10. Explicit activation and phase routing

Maestra is fully opt-in. All seven Skills set `policy.allow_implicit_invocation: false`, and only an explicit `$maestra:using-maestra` invocation activates the workflow for the current task/thread. Installation, an ordinary development prompt, Doctor, or direct recovery invocation of a phase Skill does not activate the lifecycle. Maestra adds no SessionStart hook, global instruction injection, or persistent activation marker.

Codex currently exposes explicit user Skill selection but no nested Skill-invocation API. The selected `using-maestra` router therefore uses Codex-native progressive disclosure: at each phase boundary Main resolves and reads the complete sibling `spec`, `plan`, `run`, `gate`, or `finish` `SKILL.md`, then follows that independent protocol. This is exact-path routing from an explicitly selected workflow, not implicit prompt matching.

The router owns only activation, lifecycle, and Main phase transitions. It does not duplicate phase instructions or alter the deterministic runtime core. Spec and Plan approval remain mandatory; after Plan approval, Main advances through approved Runs, Main Gates, and Finish without requiring a Skill command at every phase. Escalations, material replans, failed preconditions, and explicit user pauses still stop the flow.
