---
name: finish
description: Complete a Maestra project with risk-based final verification/review, Main Sol final semantic gate, and a user-facing report. Use only by direct explicit invocation or when Main routes here after every Run in an explicitly activated using-maestra workflow has passed its Gate.
---

# Maestra Finish — risk-based final review

Every Run already received Task reviews plus a fresh Run Integration Review. A second whole-branch Sol review is valuable for cross-Run risk, but should not be mandatory for trivial work.

## Preconditions

- All planned Runs are completed/gated.
- No unresolved `PLAN_GAP`, `REPLAN`, or `USER_DECISION` remains.
- The user has directly asked for final checking/completion, or the active `using-maestra` lifecycle has reached Finish. A standalone invocation does not activate that lifecycle.

## Always perform

1. Main rereads the approved Spec and Detailed Plan (these remain authoritative after `/compact`).
2. Run the final verification explicitly required by the Plan/Spec.
3. Check whole-change AC coverage, architecture coherence, migrations/docs/operations, branch/commit state, and residual risks.

## Decide whether whole-branch fresh Sol review is required

**Require it** when any is true:

- more than one substantive Run changed interacting code paths;
- security/privacy/data-loss-sensitive behavior changed;
- database/schema/data migration exists;
- public API or compatibility boundary changed;
- architecture was changed across multiple subsystems;
- a Run required remediation/replan after implementation began;
- Main sees material cross-Run integration risk;
- the approved Plan explicitly requires final independent review.

**May skip it** when all are true:

- one low-risk Run;
- Run Integration Review already covered the complete change;
- no migration/security/public-API/cross-cutting architecture risk;
- no remediation/replan occurred;
- final deterministic verification passes.

Record in the user report whether final Sol review was run or skipped and why.

## Conditional whole-branch reviewer

When required, read `references/final-reviewer.md`, build a compact packet, and spawn fresh:

```text
model: gpt-5.6-sol
reasoning_effort: xhigh
fork_turns: none
```

Reviewer is read-only and reports at most five critical/major findings. No style/speculative refactor findings.

## Blocking final findings

Main owns the repair plan. Do **not** ask Terra to invent a `FINAL_REWORK` design.

- Main Sol writes a bounded remediation Run into the Detailed Plan.
- User approves the material Plan change.
- Recommend `/compact`.
- Fresh Terra executes that approved remediation Run.
- Repeat final verification/review once as appropriate.

No unbounded final loop.

## Final report

Report:

- completed outcomes;
- verification performed;
- whether risk-based whole-branch Sol review ran;
- important design decisions;
- known limitations/deferred findings;
- commit/branch state;
- any remaining user action.
