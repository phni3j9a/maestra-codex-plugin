---
name: using-maestra
description: Activate and conduct the complete Maestra development workflow for the current task and thread. Use only when the user explicitly invokes $maestra:using-maestra; installing Maestra, ordinary development prompts, doctor, or direct phase-skill recovery must never activate this workflow.
---

# Using Maestra — explicit workflow router

This Skill is Maestra's only workflow entry. It activates Maestra for the task named in the invoking prompt, then keeps Main responsible for user dialogue, lifecycle, and phase routing.

## Activation boundary

- Treat activation as thread-local instruction state for the current development task.
- Do not activate from plugin installation, prompt similarity, `$maestra:doctor`, or a standalone phase-Skill invocation.
- Do not add a hook, session-wide instruction, persistent activation marker, database, daemon, or custom router.
- Before requirements are ready for a Spec, brainstorm normally with the user. Activation alone must not create runtime state, artifacts, or subagents.
- Stop routing when the workflow finishes, the user cancels Maestra, or the user changes to unrelated work without explicitly activating Maestra for it.

## Codex-native phase routing

Codex does not provide a nested Skill-invocation API. After this explicit entry Skill is selected, route deterministically through progressive disclosure:

1. Resolve this Skill's directory.
2. At each phase boundary, read the complete sibling protocol before acting:
   - Spec: `../spec/SKILL.md`
   - Plan: `../plan/SKILL.md`
   - Run: `../run/SKILL.md`
   - Gate: `../gate/SKILL.md`
   - Finish: `../finish/SKILL.md`
3. Follow that protocol as the authoritative instructions for the phase.

This exact-path load is an explicit route chosen by the already-activated workflow; it is not implicit matching against a user prompt. Keep every phase as an independent Skill and do not reproduce its detailed protocol here.

A direct phase-Skill invocation remains available for recovery or debugging, but it performs only that phase and does not activate this lifecycle unless `using-maestra` is already active in the thread.

## Lifecycle

1. **Brainstorm** — Main discusses goals, constraints, architecture, and tradeoffs normally. Do not rush to an artifact while material questions remain.
2. **Spec** — once the design discussion is mature enough to formalize, load `../spec/SKILL.md`, create the Spec, and stop for explicit user approval.
3. **Plan** — after Spec approval, load `../plan/SKILL.md`, create the Detailed Plan, and stop for explicit user approval.
4. **Execute** — Plan approval in this active workflow authorizes the approved Runs unless the user limits or pauses execution. Load `../run/SKILL.md` for exactly one Run.
5. **Gate** — after every completed Run or `PLAN_GAP`, load `../gate/SKILL.md`. On `CONTINUE`, route to the next approved Run without asking the user to type another Skill name. Pause for `REMEDIATE`, `REPLAN`, `USER_DECISION`, failed preconditions, or an explicit user pause.
6. **Finish** — when all approved Runs have passed their Gates, load `../finish/SKILL.md` and complete the risk-based finalization protocol.

Do not ask for an extra phase-selection ceremony. The mandatory approval boundaries are the Spec and Detailed Plan, plus any later material Plan revision or user decision required by an escalation.

## Preserved execution contract

Phase routing must not weaken the existing protocols: Main remains Sol/high; each Run gets fresh Terra/xhigh; each Task or accepted fix gets fresh Luna/max; each review gets fresh Sol/xhigh; every spawn uses `fork_turns: "none"`; artifact handoff, bounded review, Finding Freeze, candidate-tree binding, deterministic verification, one-Task-one-commit, Run Integration Review, Main Gate, risk-based Final Review, Git-metadata runtime state, and fail-closed routing remain authoritative.
