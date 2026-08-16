# Maestra v0.3 Acceptance Checklist

## Explicit activation

- [ ] Installing Maestra does not change ordinary Codex behavior.
- [ ] All seven Skills set `policy.allow_implicit_invocation: false`.
- [ ] `$maestra:using-maestra` is the only full-workflow entry.
- [ ] Doctor and standalone phase recovery do not activate the lifecycle.
- [ ] No SessionStart hook, hooks.json, global instruction injection, or persistent activation marker exists.
- [ ] The router loads independent sibling phase Skills by exact path and does not duplicate their protocols.
- [ ] Spec and Plan require explicit user approval; later phase names do not require manual re-entry.

## Product intent

- [ ] Main remains the user-facing owner of intent, Spec, Detailed Plan, semantic gates, and reporting.
- [ ] Terra is execution-only and cannot silently become the implementation planner.
- [ ] Luna implements one bounded Task/FixPacket at a time.
- [ ] Sol reviewer receives a fresh context independent of Luna transcript.

## Detailed planning

- [ ] Plan Skill states that Main Sol owns architecture and all substantive implementation planning.
- [ ] Each RunPacket Task requires target files/modules, implementation steps, design decisions, verification plan, review focus, expected evidence, and empty open questions.
- [ ] Coarse/incomplete RunPackets fail before Terra spawn.
- [ ] `/compact` is recommended after Plan approval, and Run re-reads approved Spec/Plan artifacts.

## PLAN_GAP

- [ ] Terra instructions explicitly forbid inventing missing architecture/implementation/test strategy.
- [ ] Runtime supports `report-plan-gap` and stores `plan-gap.json`.
- [ ] PLAN_GAP stops the Run.
- [ ] Main Gate allows only REPLAN or USER_DECISION from PLAN_GAP.

## Context and routing

- [ ] Main→Terra, Terra→Luna, and Terra→Sol use exact model/effort and `fork_turns:none`.
- [ ] No silent model fallback is allowed.
- [ ] Doctor matches post-threshold rollout parentage, recorded spawn arguments, and observed child `turn_context` model/effort without copying prompt content.
- [ ] Missing/ambiguous rollout metadata is `unverified`; an affirmatively observed mismatch is `fail`.
- [ ] Doctor routing proof is bound to Codex + Maestra versions.
- [ ] Main and Terra use 60-minute event-driven child waits that return early on mailbox updates.
- [ ] Healthy Runs do not short-poll or routinely call `list_agents`; timeout diagnostics are lightweight and path-scoped.

## Review convergence

- [ ] Reviewer findings pass through Terra adjudication.
- [ ] Only accepted findings reach Luna.
- [ ] Round 1 freezes finding IDs.
- [ ] Maximum Task review rounds is two.
- [ ] Round 2 rejects ordinary new findings and only permits fix-introduced critical exceptions.

## Git/evidence

- [ ] Runtime artifacts resolve under `git rev-parse --git-path maestra` and do not create product `.maestra/`.
- [ ] Linked worktree runtime is checkout-specific.
- [ ] Verification and Review bind to the same staged candidate tree.
- [ ] Accepted Task commit tree must equal reviewed candidate tree and include Maestra Run/Task trailers.
- [ ] Run completion requires passing Run-level verification + fresh Sol Integration Review on the final Run tree.

## Main gate / finish

- [ ] Normal Run completion automatically hands back to Main semantic gate.
- [ ] Main checks requirements, architecture, hacks, deviations, and remaining plan validity rather than repeating Task review.
- [ ] Whole-branch Final Sol review is risk-based, while Main final semantic check is always performed.

## Packaging

- [ ] Plugin validator passes.
- [ ] All regression test groups pass.
- [ ] Plugin-only ZIP contains one `maestra/` root and seven Skills plus all seven `agents/openai.yaml` files.
- [ ] Source/Plugin ZIP generation is reproducible.
