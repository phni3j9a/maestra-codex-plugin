---
schema: maestra-plan/v2
status: draft
approved_by: null
approved_at: null
spec_path: spec.md
---

# <Project / Change> Detailed Implementation Plan

## Architecture and implementation principles

- Durable architectural decisions that every Run/Task must preserve.
- Compatibility and migration principles.
- Explicit approaches that are prohibited (temporary hacks, duplicated pathways, etc.).

## Run R001 — <Integrated outcome>

### Goal

What becomes true after this Run.

### Acceptance criteria

- AC-001
- AC-002

### Run-level design

- Components/layers involved: ...
- Integration behavior: ...
- Compatibility/migration handling: ...

### Tasks

#### T001 — <Task title>

- **Objective:** ...
- **Depends on:** none
- **Satisfies:** AC-001
- **Target files/modules:**
  - `src/...` — modify because ...
  - `src/...` — create because ...
- **Implementation steps:**
  1. ...
  2. ...
  3. ...
- **Design decisions:**
  - ...
- **Boundaries:**
  - ...
- **Constraints / compatibility:**
  - ...
- **Non-goals:**
  - ...
- **Verification plan:**
  - existing/new tests to run or add;
  - behavior/invariant that each check proves.
- **Review focus:**
  - correctness or architecture risks Sol should examine.
- **Expected evidence:**
  - observable/test evidence required before commit.
- **Open questions:** none

#### T002 — <Task title>

Repeat the same fields. Do not leave design choices for Terra.

### Run integration verification plan

- Cross-Task tests/checks that must pass after all Task commits.
- Integration behavior and regressions to verify.

### Main Gate questions

- Does the implementation satisfy the intended user outcome rather than only tests?
- Did the implementation preserve the approved architecture?
- Did any local fix introduce a workaround that violates the Plan?
- Is the next Run still the correct plan?

## Run R002 — <Integrated outcome>

Repeat as needed.

## Final verification intent

Whole-change checks required after all Runs.

## Remaining implementation questions

**Must be empty before approval.** If a substantive implementation decision remains, resolve it with Main/user before approving the Plan.
