---
name: run
description: Execute exactly one approved Maestra Run using a fresh Terra execution orchestrator. Use only by direct explicit invocation or when Main routes here from an explicitly activated using-maestra workflow. Terra may coordinate, verify, adjudicate review, and commit, but must return PLAN_GAP instead of making missing design decisions.
---

# Maestra Run — execute Main's Plan, do not plan again

Execute **one approved Run only**. Main remains the user-facing owner and the sole owner of substantive implementation planning.

## Required references

Before execution, read:

- `references/orchestrator.md`
- `references/artifact-contracts.md`
- `references/review-protocol.md`
- `references/git-protocol.md`

Do not copy the user's full conversation into the RunPacket.

## Preconditions

1. Maestra runtime metadata is initialized in Git metadata (`git rev-parse --git-path maestra`).
2. `spec.md` exists there and is explicitly approved.
3. `plan.md` exists there and is explicitly approved.
4. The approved Plan is a **detailed v0.3 Plan**: architecture, Task decomposition, target files/modules, implementation steps, design decisions, verification strategy, review focus, and open questions are resolved by Main Sol.
5. The user has explicitly authorized the selected approved Run. In an active `using-maestra` lifecycle, explicit Plan approval authorizes all approved Runs unless the user limits or pauses execution. For standalone direct invocation, Plan approval plus a request to execute is sufficient. There is no third execution-approval ceremony.
6. `$maestra:doctor` has a current version-bound routing proof, unless the user explicitly accepts an experimental unverified run.
7. `HEAD` equals the selected Run base commit.
8. Product working tree is clean. Maestra runtime artifacts are outside the working tree.
9. No earlier Run is waiting on Main Gate or `PLAN_GAP` resolution.

Stop on a failed precondition. Do not silently downgrade models, inherit Main's Sol model, discard user changes, or invent approval.

## Main procedure

1. Resolve the selected Run from the approved Detailed Plan.
2. Build **RunPacket schema v2 by copying Main-owned planning decisions**, not by asking Terra to fill them. Every Task must include:
   - objective and linked ACs;
   - dependencies;
   - target files/modules;
   - implementation steps;
   - design decisions;
   - boundaries, constraints, compatibility requirements, and non-goals;
   - verification plan;
   - review focus and expected evidence;
   - `open_questions: []`.
3. Include Run-level integration verification plan and Main Gate questions.
4. Save the packet under the resolved Maestra Git-metadata directory and initialize the Run:

```bash
python3 <this-skill>/scripts/maestra.py create-run \
  --repo <repository-root> \
  --packet <run-packet.json>
```

The helper rejects an incomplete detailed plan before Terra is spawned.

5. Spawn exactly one fresh Terra execution orchestrator:

```text
model: gpt-5.6-terra
reasoning_effort: xhigh
fork_turns: none
```

6. Give Terra only:
   - repository root;
   - resolved `runs/<RUN_ID>/run-packet.json`;
   - absolute paths to the four Run protocol references;
   - instruction to execute exactly that Run and return a concise completion/escalation marker.
7. After Terra is spawned, Main uses event-driven waiting:
   - call `wait_agent` with `timeout_ms: 3600000`; mailbox updates and Terra completion return early, so do not use short polling waits;
   - Do not call `list_agents` during normal Run execution;
   - if the 60-minute wait times out, run `maestra.py status --repo <repository-root> --json` first;
   - if Run state progressed, wait for another `3600000` ms;
   - if state is unchanged or inconsistent, or the user explicitly requests agent-level status, call `list_agents` at most once per timeout investigation scoped to the current Run path, then wait again or escalate from concrete evidence;
   - never repeatedly import completed descendant `last_task_message` payloads into Main context, and do not treat one timeout as a failure.
8. Main does **not** dispatch Luna or Reviewer directly.
9. Terra may resolve mechanical execution details (for example the exact package-script command corresponding to the Plan's test strategy), but may not choose architecture, add unplanned components, invent a migration, or select a different test strategy.
10. If Terra discovers a missing substantive decision, it must record `PLAN_GAP` and stop. Main then revises the Plan, obtains user approval, and recommends `/compact` again before resuming through a newly approved Run.
11. If the Run completes, Terra must record Run-level deterministic verification plus one fresh Sol Integration Review before `complete-run` succeeds.
12. When Terra returns `RUN_READY_FOR_GATE`, **Main resolves and reads `../gate/SKILL.md` completely, then performs that semantic Gate in the same interaction**. The user does not need to type `$maestra:gate` after every Run. The standalone Gate Skill remains available for recovery/explicit reruns.
13. Follow the Gate routing decision. In an active `using-maestra` lifecycle, `CONTINUE` routes to the next approved Run or Finish without another Skill command; a standalone Run returns control to the user after Gate.

## Context firewall

Main must not load by default:

- Luna transcripts;
- Reviewer transcripts;
- raw routine test logs;
- rejected minor findings;
- complete Task diffs.

Main reads the approved Spec/Plan, RunReport, integration evidence, and only concrete escalations. This remains true even after `/compact`; Spec/Plan artifacts are the Source of Truth.

Routine `list_agents` polling is outside this firewall because it can copy completed Luna/Reviewer final payloads into Main repeatedly. Use the event-driven wait policy above instead.

## Routing invariant

Every subagent spawn uses `fork_turns: "none"`.

- Main → Terra: `gpt-5.6-terra`, `xhigh`
- Terra → Luna: `gpt-5.6-luna`, `max`
- Terra → Reviewer: `gpt-5.6-sol`, `xhigh`

If any requested route is unavailable or cannot be verified, stop the Run. A silent fallback is a routing failure.
