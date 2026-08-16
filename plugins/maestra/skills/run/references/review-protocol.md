# Review Adjudication and Convergence — Maestra v0.3

Reviewer output is a **proposal**, not an automatic instruction to Luna and not permission for Terra to redesign the Plan.

## Terra adjudication

For every Finding, choose exactly one:

- `ACCEPT` — correction is required and the approved Detailed Plan already determines the substantive implementation choice;
- `DEFER` — valid, non-blocking, explicitly outside this Task/Run;
- `REJECT` — unsupported, duplicate, pre-existing, preference-only, or contrary to approved design;
- `ESCALATE` — requires Main/user product, architecture, implementation, migration, or test-strategy decision.

Critical security or data-loss findings should normally be `ACCEPT` or `ESCALATE`.

If a Finding is valid but fixing it would require Terra to decide something absent from the Main Plan, do **not** manufacture a FixPacket. Record/raise `PLAN_GAP` and return control to Main.

Example adjudication:

```json
{
  "schema_version": 1,
  "run_id": "R001",
  "task_id": "T001",
  "round": 1,
  "decisions": [
    {
      "finding_id": "T001-F01",
      "decision": "ACCEPT",
      "reason": "The Main Plan already specifies the required provider boundary."
    }
  ]
}
```

Only `ACCEPT` findings whose correction is already determined by the approved Plan enter a FixPacket.

## Finding Freeze

- Round 1 freezes the Finding IDs.
- Round 2 checks accepted frozen finding resolution.
- A frozen Finding may be `resolved`, `unresolved`, or `not_applicable` with evidence.
- New ordinary findings in Round 2 are rejected by the helper.
- The only exception is a critical issue introduced by the accepted fix itself: `security`, `data_loss`, or `fix_regression`.

## Termination

A Task ends after at most two review rounds:

- pass and commit;
- block with unresolved accepted Finding;
- `PLAN_GAP` / escalate to Main;
- stop on unexpected mutation or verification failure.

Do not start Round 3 and do not loosen the approved criteria to force convergence.
