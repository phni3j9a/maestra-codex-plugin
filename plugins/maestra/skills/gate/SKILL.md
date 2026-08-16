---
name: gate
description: Perform the Main Sol semantic and architectural gate after a Maestra Run or PLAN_GAP. Use only by direct explicit invocation or when Main routes here from an explicitly activated using-maestra workflow or Run. Direct invocation is for recovery/re-evaluation and does not activate the workflow.
---

# Maestra Main Gate

Main evaluates whether the team built the **right thing** and whether the approved Detailed Plan remains valid. This is not another local code-review pass.

## Invocation

Normal active flow: Main completes the Run protocol → resolves and reads this independent Skill → executes the Gate in the same interaction. The user should not need to type `$maestra:gate` after each Run.

Standalone invocation is retained for recovery/re-evaluation and returns to normal Codex behavior afterward unless `using-maestra` was already active.

## Inputs

Resolve Maestra runtime paths from `git rev-parse --git-path maestra`, then read only:

- approved `spec.md`;
- approved `plan.md`;
- selected Run `run-packet.json`;
- `run-report.md` and `integration-review.json` when Run completed;
- `plan-gap.json` when Terra returned `PLAN_GAP`;
- concise Git evidence such as `git diff <base>..<head> --stat`.

Do not read every Task transcript by default.

## Evaluate completed Run

1. Are linked ACs satisfied in substance?
2. Did implementation preserve Main's approved architectural/implementation decisions?
3. Did any workaround merely satisfy tests while violating the Plan?
4. Did scope creep/unapproved behavior occur?
5. Are deferred findings safe?
6. Is the next approved Run still correct?
7. Does the user need to decide a tradeoff?

## Evaluate PLAN_GAP

`PLAN_GAP` means Terra correctly refused to design. Main must inspect the missing elements and repository evidence, then choose:

- `REPLAN` — Main Sol revises the Detailed Plan and asks for user approval;
- `USER_DECISION` — product/architecture choice must be discussed with the user first.

Do not tell Terra to “use its judgment” for a recorded Plan gap.

## Decision

- `CONTINUE` — completed Run is sound. In an active `using-maestra` lifecycle, load `../run/SKILL.md` for the next approved Run, or `../finish/SKILL.md` when no Runs remain; otherwise return control to the user.
- `REMEDIATE` — Main authors a bounded remediation Run in the Plan; obtain user approval when Plan materially changes.
- `REPLAN` — approved Detailed Plan is no longer valid; revise in Main Sol and obtain user approval.
- `USER_DECISION` — user decision required.

For a Run in `plan_gap`, only `REPLAN` or `USER_DECISION` are valid runtime decisions.

Record:

```bash
python3 <run-skill>/scripts/maestra.py record-gate \
  --repo <repo> --run <R001> --decision <DECISION> --note <short-note>
```

When Plan is revised/approved, recommend `/compact` again before further execution. Never auto-start the next Run.
