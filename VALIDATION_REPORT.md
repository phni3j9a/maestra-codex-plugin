# Maestra v0.3.2 Validation Report

**Validation date:** 2026-08-16  
**Target:** Codex CLI 0.147.0 portable Agent Plugin  
**Result:** PASS for Skill/plugin validation, 33 regression tests, explicit-only metadata, hook absence, event-driven orchestration waits, existing runtime invariants, and release packaging. The new cachebuster still requires a fresh-thread Doctor run before the next Maestra execution.

## Explicit opt-in behavior validated

- Seven independent Skills exist: `using-maestra`, `doctor`, `spec`, `plan`, `run`, `gate`, and `finish`.
- All seven `agents/openai.yaml` files set `policy.allow_implicit_invocation: false`.
- `using-maestra` is the only full-workflow entry and creates no activation artifact, subagent, or runtime state during brainstorming.
- Doctor and standalone phase recovery do not activate the lifecycle.
- No `hooks/`, `hooks.json`, manifest hook declaration, SessionStart injection, persistent activation marker, or custom router runtime exists.
- The router references exact independent sibling `SKILL.md` paths and does not copy phase protocols into itself.
- Spec and Plan retain explicit user approval boundaries; active workflow routing continues through Run, Gate, later Runs, and Finish without repeated phase commands.

## Existing v0.3 invariants retained

- Exact configured models remain Main Sol/high, Terra/xhigh, Luna/max, and Sol reviewer/final reviewer xhigh.
- Every execution/review spawn remains `fork_turns:none` and context-isolated.
- Main owns the Detailed Plan; incomplete planning fails closed with `PLAN_GAP`.
- Runtime state remains under `git rev-parse --git-path maestra`.
- Doctor now binds each route to the recorded spawn arguments, rollout parent chain, and observed child model/effort before binding the proof to Codex + Maestra versions.
- Missing/ambiguous rollout evidence is `unverified`; an affirmatively observed mismatch is `fail`.
- Routing evidence excludes prompt, message, summary, and reasoning content.
- Finding Freeze, maximum two review rounds, late-finding restrictions, and Terra adjudication remain enforced.
- Verification, independent Review, Task commit, and Run integration evidence remain candidate-tree bound.
- One Task remains one commit with required Maestra trailers.
- Run completion still requires deterministic Run-level verification plus fresh Sol Integration Review.
- Main Semantic Gate and risk-based Final Review remain unchanged in substance.
- Main→Terra and Terra→Luna/Reviewer now use explicit 60-minute `wait_agent` calls that return early on mailbox updates.
- Healthy Runs prohibit short polling and routine `list_agents`; real timeouts use lightweight state/evidence before a single path-scoped agent-tree inspection.

## Automated tests

```text
python3 -m pytest -q
33 passed
```

Coverage includes event-driven hour waits at both orchestration layers, successful rollout routing proof, observed model mismatch, missing rollout metadata, explicit parent mismatch, prompt-content exclusion, the seven-Skill layout, metadata policy, unique workflow entry, hook absence, plugin/source ZIP contents, and the existing negative/runtime tests for coarse planning, open questions, dirty trees, stale routing proof, Finding Freeze, review rounds, candidate-tree mutation, PLAN_GAP gate misuse, missing Integration Review, linked worktrees, and commit trailers.

## Validators and static checks

- Skill Creator `quick_validate.py`: PASS for 7/7 Skills.
- `tools/validate_plugin.py`: PASS; 7/7 explicit-only Skills, two default prompts, 7.9 brand contrast.
- Plugin Creator `validate_plugin.py`: PASS.
- Source/bundled documentation byte parity tests: PASS.
- Release builder and plugin/source ZIP regression tests: PASS.

## Live Doctor routing validation

The prior 2026-08-15 v0.3.2 build was exercised with authenticated `codex-cli 0.147.0` and a fresh post-threshold probe tree:

```text
Main  -> Terra: gpt-5.6-terra / xhigh / fork_turns:none
Terra -> Luna : gpt-5.6-luna  / max   / fork_turns:none
Terra -> Sol  : gpt-5.6-sol   / xhigh / fork_turns:none
```

The deterministic helper selected the common root session, verified all three `parent_thread_id` / `agent_path` links, matched each recorded `spawn_agent` call, and confirmed every child `turn_context.model` / `effort`. All three routes recorded `verified: true`; final `routing_proof` status was `pass`.

A separate fresh-context forward test used that installed Doctor against the earlier raw probe and independently returned routing `pass`, no product changes, and only the pre-existing untracked-worktree warning. This remains historical evidence only: the new cachebuster intentionally invalidates the version-bound proof, so `$maestra:doctor` must be run from a new thread before the next execution.

## Packaging

- Runtime/release base version: `0.3.2`.
- Installed/plugin build version: `0.3.2+codex.20260815151220`.
- Plugin ZIP: one `maestra/` root, 44 members, 7 Skills, 69,800 bytes.
- Source ZIP: one `maestra-codex-plugin-v0.3.2+codex.20260815151220/` root.
- Both archives include `using-maestra/SKILL.md` and its `agents/openai.yaml`.
- All seven Skill metadata files are present in plugin-only and source distributions.
- Final archive hashes are emitted beside the archives in `SHA256SUMS.txt` to avoid a self-referential source-archive hash inside this report.

## Not validated

- A full real project lifecycle from `$maestra:using-maestra` through Spec, both approvals, multiple Runs, Gates, and Finish was not executed end-to-end.
- The updated cachebuster's live Doctor probe was not run in this editing thread; plugin reload and routing verification require a new thread.

## Release decision

The updated v0.3.2 plugin is installed and all static/regression/package checks pass on Codex 0.147.0. Normal Codex prompts remain outside Maestra; start a new thread, rerun `$maestra:doctor`, and begin verified Maestra execution only after explicit `using-maestra` activation and a current routing proof.
