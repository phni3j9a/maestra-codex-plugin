---
name: spec
description: Turn an already-discussed software change into a concise, user-approvable Maestra specification. Use only by direct explicit invocation or when Main routes here from an explicitly activated using-maestra workflow. Do not execute implementation work or spawn implementation agents.
---

# Maestra Specification

Main remains the conversational owner. This Skill structures durable product/architecture requirements; it does not take over the conversation.

## Preconditions

- Discuss goals, constraints, and important tradeoffs normally with the user first.
- Require either direct explicit invocation or an active `using-maestra` lifecycle that has reached Spec; a standalone invocation does not activate that lifecycle.
- Do not require a separate execution approval.
- Do not modify product code or dispatch Terra/Luna/Reviewer.
- If Maestra runtime metadata is not initialized, initialize it with the run helper before writing the artifact.

## Procedure

1. Read `references/spec-template.md`.
2. Inspect only the repository information needed to make the specification concrete.
3. Resolve the artifact path with `git rev-parse --git-path maestra/spec.md` and create/update that file.
4. Give every acceptance criterion a stable ID (`AC-001`, `AC-002`, ...).
5. Separate requirements from implementation choices. Record architectural decisions only when they are part of the approved requirement or a durable constraint.
6. Explicitly list non-goals and unresolved **user/product** decisions.
7. Show the user the material decisions and ask for approval.
8. On approval, change the metadata to:

```yaml
status: approved
approved_by: user
approved_at: <RFC3339 timestamp>
```

9. Do not infer approval from silence, enthusiasm, or a request to continue discussing.

## Context discipline

Do not copy the complete conversation into the Spec. Preserve only durable decisions, requirements, constraints, and rationale needed by future agents.

The Spec should not carry detailed Task-level implementation mechanics. **Those are still Main-owned in Maestra v0.3, but they belong in the Detailed Plan rather than the Spec.**
