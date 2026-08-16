# Maestra Git Protocol

Git is a simple execution boundary, not a transactional database.

## Runtime artifacts

Maestra state lives outside the product working tree at the checkout-specific path resolved by:

```bash
git rev-parse --git-path maestra
```

Do not add `.maestra/` to the product repository. Linked worktrees naturally receive checkout-specific metadata paths.

## Task invariants

1. Start each Run from a clean product working tree.
2. Record the Run base `HEAD`.
3. Luna never commits.
4. Reviewer never mutates files or Git state.
5. Terra owns normal Git commits.
6. Stage only planned Task changes.
7. Verification and Review must reference the same staged `candidate_tree`.
8. Commit without restaging after PASS.
9. Runtime verifies the commit tree equals the verified/reviewed candidate tree.
10. One approved Task = one commit with:

```text
Maestra-Run: R001
Maestra-Task: T001
```

## Unexpected changes

Never auto-reset, auto-stash, or discard unknown user changes. Stop and report them.

An unexpected path that reveals a missing implementation/design decision is `PLAN_GAP`, not permission for Terra to expand scope.

## Failure / resume

- Failed verification: keep candidate uncommitted and apply only Task-local accepted fixes.
- Reviewer mutation: stop and escalate; do not auto-reset.
- `PLAN_GAP`: stop the Run; Main revises/reapproves Plan.
- Agent/session crash: inspect last completed Task commit and Git-metadata runtime state. Maestra v0.3 deliberately does not promise crash-atomic transaction recovery.
