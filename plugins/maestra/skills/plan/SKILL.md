---
name: plan
description: Create the full detailed implementation plan for an approved Maestra specification in Main Sol. Use only by direct explicit invocation or when Main routes here from an explicitly activated using-maestra workflow. Main owns architecture, implementation strategy, Task decomposition, target files, and verification strategy; Terra must not fill planning gaps.
---

# Maestra Detailed Plan — Main Sol owns the design

The Plan is the final implementation-design artifact before execution. **Main Sol owns all substantive planning.** Terra later coordinates execution but may not invent missing architecture, implementation strategy, file ownership, or test strategy.

## Preconditions

- The approved Spec exists in Maestra Git metadata (`git rev-parse --git-path maestra/spec.md`).
- The user has directly asked to create/revise the Plan, or an active `using-maestra` lifecycle has reached Plan after explicit Spec approval. A standalone invocation does not activate that lifecycle.
- No Terra/Luna/Reviewer implementation agent may be spawned from this Skill.

## Procedure

1. Read the approved Spec and `references/plan-template.md`.
2. Inspect the repository deeply enough to make implementation decisions with confidence: architecture, existing abstractions, relevant files, tests, build commands, migration constraints, and project conventions.
3. Create or update the resolved Maestra Plan path (`git rev-parse --git-path maestra/plan.md`).
4. Split work into coherent Runs. Each Run must produce an integrated result that Main can judge semantically.
5. Inside each Run, define ordered Tasks with stable IDs (`T001`, `T002`, ...).
6. For **every Task**, Main must decide and write:
   - objective and linked acceptance criteria;
   - dependency order;
   - target files / modules expected to change or be created;
   - concrete implementation steps;
   - durable design/API/data-model decisions;
   - boundaries, constraints, compatibility requirements, and non-goals;
   - verification strategy and tests that must prove correctness;
   - review focus and expected evidence;
   - any migration/documentation/operational work required.
7. Resolve all implementation-relevant open questions before approval. Each Task must end with `Open questions: none` (represented as `open_questions: []` in the RunPacket).
8. Define Run-level integration verification and Main Gate questions.
9. Define final verification intent for the whole change.
10. Present material implementation and sequencing decisions to the user.
11. On explicit approval, update metadata:

```yaml
status: approved
approved_by: user
approved_at: <RFC3339 timestamp>
```

12. After Plan approval, recommend **`/compact` before execution**. The approved Spec and Plan remain the Source of Truth after compaction; conversation summary is not authoritative. In an active `using-maestra` lifecycle, Main resumes by loading `../run/SKILL.md`; the user need not type `$maestra:run`.

## Planning boundary

Main must not deliberately leave a substantive choice for Terra merely to save context. Examples that belong in this Plan:

- which abstraction / architectural pattern to use;
- which layer owns the new behavior;
- public API or data-model shape;
- migration/compatibility strategy;
- expected new/modified files or modules;
- what tests/verification prove the Task;
- whether a workaround is acceptable or prohibited.

Terra may resolve only mechanical execution details such as the exact command spelling from package scripts, current line numbers, or the exact path of an already-planned module when repository inspection makes it unambiguous.

If Terra discovers that a substantive decision is absent, it must return `PLAN_GAP`; it must not make the decision itself.

## Task sizing

A Task should fit one focused Luna implementation context and one Task commit. Split a Task when it combines unrelated responsibilities, but **do not make Tasks so tiny that architectural intent becomes distributed across many implicit choices**.

Prefer sequential Tasks in v0.3. Parallel writes remain out of scope unless a later version introduces an explicit parallel-execution contract.
