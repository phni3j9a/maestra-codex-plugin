# Maestra v0.3

Maestra keeps **thinking and design in Main Sol** while isolating execution noise in fresh subagents.

> **Installing Maestra does not change normal Codex behavior. Maestra is activated only by explicitly invoking `$maestra:using-maestra`.**

```text
Main Sol/high       — user dialogue, Spec, full Detailed Plan, semantic gates
Terra/xhigh         — one-Run execution coordination only
Luna/max            — bounded implementation
Sol/xhigh           — independent review
```

## v0.3 planning boundary

`$maestra:plan` produces the complete implementation Plan in Main: architecture, Run/Task decomposition, target files/modules, implementation steps, design decisions, verification strategy, review focus, and Run gate questions. After user approval, `/compact` is recommended.

Execution then re-reads approved Spec/Plan artifacts. Terra may resolve mechanical details such as exact package-script commands, but **must return `PLAN_GAP` rather than infer missing substantive design**.

## Opt-in activation

All seven Skills have `allow_implicit_invocation: false`:

- `$maestra:using-maestra` — the only workflow entry
- `$maestra:doctor`
- `$maestra:spec`
- `$maestra:plan`
- `$maestra:run`
- `$maestra:gate` (normally reached automatically from `run`)
- `$maestra:finish`

Ordinary prompts never start Maestra or create its state/artifacts/subagents. Doctor is workflow-neutral: a standalone Doctor run reports diagnostics and returns to normal Codex behavior. No hooks or persistent activation marker are used.

After explicit activation, Main brainstorms normally, then loads each independent sibling phase protocol by exact `SKILL.md` path. Codex has no nested Skill-invocation API, so this deterministic progressive-disclosure route keeps every phase independent and explicit-only without requiring the user to type every phase name.

The managed lifecycle is Brainstorm → Spec → explicit approval → Plan → explicit approval → Run → Gate → next Run → Finish. Direct phase invocation remains available for recovery/debugging but does not activate the full lifecycle.

Typical use requires only these commands:

```text
$maestra:doctor                  # optional, first-time/version check
$maestra:using-maestra

Add OAuth login support. I want to discuss the design first.
```

Main then manages Brainstorm → Spec approval → Plan approval → Runs/Gates → Finish.

## Context/routing

```text
Main  -> Terra : gpt-5.6-terra / xhigh / fork_turns:none
Terra -> Luna  : gpt-5.6-luna  / max   / fork_turns:none
Terra -> Sol   : gpt-5.6-sol   / xhigh / fork_turns:none
```

Main→Terra and Terra→Luna/Reviewer waits are event-driven with `wait_agent(timeout_ms: 3600000)`. Mailbox updates and completion return early. Healthy Runs do not use short polling or routine `list_agents`; a real timeout first checks lightweight Run/Task evidence and permits at most one path-scoped agent-tree inspection when liveness remains unclear.

Doctor is fail-closed. It verifies the recorded spawn arguments, parent/child rollout chain, and observed child model/effort before binding the proof to current Codex + Maestra versions. Model self-claims alone never pass.

## Runtime state

Maestra does not create product `.maestra/`. Runtime artifacts live under:

```bash
git rev-parse --git-path maestra
```

This also gives linked worktrees checkout-specific state.

## Execution safety

- Main Detailed Plan must pass schema-v2 completeness checks before Terra is spawned.
- `PLAN_GAP` stops execution and only Main may resolve it through replanning/user decision.
- Reviewer findings are mediated by Terra; accepted fixes stay inside approved design.
- Maximum two Task review rounds with Finding Freeze.
- Verification/Review/commit are bound to the same candidate tree.
- Run completion requires passing Run-level verification + fresh Sol Integration Review.
- Whole-branch Final Sol review is risk-based; Main final semantic check is always required.

See bundled docs for design, troubleshooting, migration, and acceptance criteria.
