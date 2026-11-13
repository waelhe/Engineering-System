---
name: egm-implement
description: Implement an approved EGM plan within an explicit file allowlist, preserving project contracts and recording the actual work performed.
---

# EGM Implementation

This skill is the only local EGM skill authorized to change production source files. Upstream design and review skills remain design/review scoped.

## Preconditions

Do not begin source edits unless all are true:

1. The requested outcome is understood and the task is classified.
2. Current repository state, branch, target SHA and applicable instructions were inspected.
3. The design is approved where T2/T3 design gates apply.
4. The implementation plan passes the implementation-readiness standard.
5. The plan identifies exact files or a justified generated-output boundary.
6. Interfaces, data contracts, invariants, migration behavior, error handling and test cases are specified.
7. Required human authorization for security, money, destructive data, production or irreversible effects has been recorded.

If a precondition is absent, report the precise gap and do not guess a new architectural decision.

## Write boundary

- Treat the approved file list as an allowlist. Do not modify unrelated files.
- Do not edit an applied migration, public contract, security policy or production setting unless the plan explicitly covers it and the required approval exists.
- Prefer documented framework, build, lifecycle, generator and extension mechanisms.
- Do not add dependencies or services without a documented need and approved decision.
- Preserve backward compatibility where required and test alternate entry points.
- Do not hide a failure by weakening or deleting a test or guard.

## Execution

Implement in stable, testable increments. Run focused tests after each logical change. Record exact changed paths and commands. Continue unrelated work while checks run, but respect dependencies.

## Handoff

Stop before self-approval. Pass the resulting diff, commit SHA, test evidence, deviations and unresolved questions to the independent review and verification skills.
