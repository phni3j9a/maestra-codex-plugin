# Maestra Artifact Contracts — v0.3

Runtime artifacts live under the checkout's Git metadata path resolved by:

```bash
git rev-parse --git-path maestra
```

They do not appear in product diffs.

## Approved Spec / Plan

Logical artifact names inside the runtime root:

- `spec.md`
- `plan.md`

Both require frontmatter:

```yaml
status: approved
approved_by: user
approved_at: <RFC3339>
```

The Plan is `maestra-plan/v2`: a **Main-owned detailed implementation plan**. It is authoritative after `/compact`.

## RunPacket schema v2

Main creates one packet per approved Run by copying the detailed decisions from the approved Plan. Terra may not add missing design.

```json
{
  "schema_version": 2,
  "run_id": "R001",
  "title": "Run title",
  "goal": "Integrated outcome",
  "spec_path": "spec.md",
  "plan_path": "plan.md",
  "base_commit": "40-char Git SHA",
  "acceptance_criteria": ["AC-001"],
  "architectural_invariants": ["durable invariant"],
  "non_goals": ["explicit exclusion"],
  "integration_verification_plan": ["What must be proven across Tasks"],
  "main_gate_questions": ["Semantic question Main must answer"],
  "tasks": [
    {
      "id": "T001",
      "title": "Task title",
      "objective": "bounded result",
      "depends_on": [],
      "acceptance_criteria": ["AC-001"],
      "target_files": ["src/auth/provider.ts", "tests/auth/provider.test.ts"],
      "implementation_steps": ["Define the approved interface", "Migrate the existing implementation"],
      "design_decisions": ["Caller depends on AuthProvider rather than concrete API-key implementation"],
      "boundaries": ["auth subsystem"],
      "constraints": ["preserve public API"],
      "non_goals": ["unrelated refactor"],
      "verification_plan": ["Existing auth regression tests", "New provider contract tests"],
      "review_focus": ["abstraction leakage", "backward compatibility"],
      "expected_evidence": ["auth regression suite passes"],
      "open_questions": []
    }
  ],
  "models": {
    "orchestrator": {"model": "gpt-5.6-terra", "reasoning_effort": "xhigh"},
    "implementer": {"model": "gpt-5.6-luna", "reasoning_effort": "max"},
    "reviewer": {"model": "gpt-5.6-sol", "reasoning_effort": "xhigh"}
  },
  "review": {
    "max_rounds": 2,
    "max_major_findings": 5,
    "finding_freeze": true,
    "minor_findings_block": false
  }
}
```

The runtime rejects `open_questions != []` and missing detailed fields before Terra is spawned.

## TaskPacket

Terra creates TaskPackets by mechanically concretizing the RunPacket. It may add execution-only facts:

- confirmed existing file paths corresponding to planned targets;
- exact writable paths/globs constrained by planned targets;
- exact argv/cwd/timeout corresponding to Main's verification strategy;
- repository facts needed by Luna.

It may **not** add architecture, new implementation steps, new components, or a different verification strategy. Missing substantive decisions produce `PLAN_GAP`.

## PlanGap

```json
{
  "schema_version": 1,
  "run_id": "R001",
  "task_id": "T001",
  "reason": "Execution requires an implementation decision absent from the approved Plan",
  "missing_plan_elements": ["Choose ownership/API for X"],
  "evidence": ["Repository fact that exposed the gap"],
  "requested_main_action": "Revise Plan and obtain user approval"
}
```

`task_id` may be `null` or `INTEGRATION` for a Run-level gap.

## VerificationResult

```json
{
  "schema_version": 1,
  "run_id": "R001",
  "task_id": "T001",
  "candidate_tree": "40-char Git tree SHA",
  "status": "pass | fail | blocked",
  "commands": [
    {
      "argv": ["python3", "-m", "pytest"],
      "cwd": ".",
      "exit_code": 0,
      "duration_seconds": 1.2,
      "log_path": "<Git metadata>/maestra/runs/R001/tasks/T001/logs/test.log"
    }
  ],
  "summary": ["factual result"]
}
```

For Run-level verification use `task_id: "INTEGRATION"`.

## ReviewProposal

Reviewer output is immutable evidence; Terra's adjudication is stored separately. `candidate_tree` must match the recorded verification and current staged/HEAD tree as appropriate.

## Run integration evidence

Before Run completion, the helper requires:

- `integration-verification.json` with `task_id: INTEGRATION`, status `pass`;
- `integration-review.json` from a fresh Sol reviewer, `task_id: INTEGRATION`, round `1`, verdict `PASS`;
- both bound to the current product tree.

## RunReport

Compact Terra → Main handoff containing:

- Run ID, goal, base/head commits, completion status;
- Tasks and commit SHAs;
- AC evidence;
- verification summary;
- Integration Review verdict;
- accepted/deferred/rejected/escalated Finding counts;
- architectural decisions preserved;
- concrete residual risks;
- any `PLAN_GAP` / deviation;
- Main Gate questions copied from the approved Plan.

Do not include full transcripts or routine logs.
