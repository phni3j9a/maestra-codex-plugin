---
name: doctor
description: Verify Maestra prerequisites, exact Codex multi-agent routing, Git state, and version-bound runtime configuration before execution. Use only when the user explicitly invokes $maestra:doctor. This diagnostic must not activate the Maestra workflow or modify product code.
---

# Maestra Doctor

Doctor may create/update **Git-metadata runtime artifacts only**; it never changes product files.

Doctor is workflow-neutral. When invoked outside an already-active `using-maestra` workflow, report the result and return to normal Codex behavior; do not route to Spec, Plan, Run, Gate, or Finish.

## Initialize runtime metadata

Locate the sibling helper at `../run/scripts/maestra.py`.

If runtime config is missing, initialize Maestra at the checkout-specific Git metadata path:

```bash
python3 <run-skill>/scripts/maestra.py init --repo <repository-root>
```

This resolves `git rev-parse --git-path maestra`. It does not create `.maestra/` in the working tree and does not need `.git/info/exclude`.

## Static checks

Run:

```bash
python3 <run-skill>/scripts/maestra.py doctor --repo <repository-root> --json
```

Report every fail/warn. Do not silently repair product configuration.

## Live routing probe

Static version is not routing proof. Inspect the callable `spawn_agent` schema in the current session; Maestra requires `model`, `reasoning_effort`, and `fork_turns` overrides.

1. Immediately before spawning, capture an RFC3339 UTC threshold and retain its exact output:

```bash
date -u +%Y-%m-%dT%H:%M:%SZ
```

2. Spawn fresh Terra and retain its returned canonical agent path:
   - `gpt-5.6-terra`
   - `xhigh`
   - `fork_turns: "none"`
3. Terra spawns exactly two non-mutating fresh probes and returns both canonical child paths:
   - Luna `gpt-5.6-luna` / `max`
   - Sol `gpt-5.6-sol` / `xhigh`
   - both use `fork_turns: "none"`
4. Wait for and close all probes. Model self-claims and `list_agents` status alone are not routing proof.
5. Verify and record the proof directly from Codex rollout metadata:

```bash
python3 <run-skill>/scripts/maestra.py verify-routing-proof \
  --repo <repository-root> \
  --not-before <captured-threshold> \
  --terra-agent-path <returned-terra-path> \
  --luna-agent-path <returned-luna-path> \
  --reviewer-agent-path <returned-sol-reviewer-path>
```

The helper reads `${CODEX_HOME:-~/.codex}/sessions` by default. Use `--sessions-dir` only when the current Codex runtime stores rollouts elsewhere.

It must match one post-threshold rollout triple by exact agent paths, common root session, and parent-thread chain. For each route it checks:

- the parent's recorded `spawn_agent` arguments for exact model, effort, and `fork_turns: "none"`;
- the child's `session_meta` parent/path linkage;
- every child `turn_context.model` and `turn_context.effort` value.

The helper extracts metadata only. Do not print or copy rollout prompts, messages, summaries, or reasoning into the proof.

6. Read current versions:

```bash
codex --version
python3 <run-skill>/scripts/maestra.py --version
```

7. Run the static Doctor command again and report its final status.

The rollout helper writes proof schema v2 to Git metadata and binds it to the **current Codex semver and current Maestra version**. Upgrading either invalidates the old proof and requires Doctor again.

## Outcome semantics

- `pass`: every requested spawn and every observed child context match exactly.
- `fail`: rollout metadata affirmatively shows a mismatched model, effort, fork request, or parent chain.
- `unverified`: required rollout metadata is missing or cannot be matched unambiguously.

## Fail closed

Do not start `$maestra:run` unless the final recorded status is `pass`. Never silently substitute inherited Sol for Terra/Luna, and never convert missing rollout metadata into a successful proof.
