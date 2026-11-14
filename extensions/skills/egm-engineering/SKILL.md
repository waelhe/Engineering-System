---
name: egm-engineering
description: Orchestrate engineering work through EGM with risk classification, project context, knowledge retrieval, independent review, controlled implementation, verification and learning.
---

# EGM Engineering Orchestrator

Use this skill as the entry point for engineering tasks. It coordinates upstream EGM design/review skills with the canonical knowledge store and execution policies.

## Required intake

1. Identify the active project/repository and target ref from the workspace, not from memory.
2. Read the Core Engineering Charter and Task Classification and Risk Policy.
3. Discover root and nested repository instructions, CI policy, code owners, ADRs and applicable technology profiles.
4. Classify the task T0–T3 using its highest credible impact. Escalate when a risk trigger appears.
5. For T1–T3, create/update an execution receipt and define affected scope, write allowlist, checks and authority gates.
6. Use egm-knowledge to build a source-linked context pack before proposing a fix or design.

## Routing

- T0: answer or research with only the relevant context.
- T1: targeted investigation and verification; no design pipeline unless a real design decision is open.
- T2: use upstream EGM brainstorm/draft/review for non-trivial feature and architecture decisions; resolve findings; require an implementation-readiness plan before source edits.
- T3: use the full relevant EGM review lenses, including security, data/concurrency, architecture and readiness. Require human approvals at the authority boundaries.

## Execution

- Delegate design and review to upstream EGM skills and reviewers. Do not simulate a fresh Goldfish in the authoring context.
- Invoke egm-implement only with an approved plan and explicit file allowlist.
- Invoke egm-verify after implementation; a successful build alone is not completion.
- Invoke egm-learn to triage new review, test, CI and incident signals.
- Continue independent work while asynchronous checks run, without bypassing required checks or dependencies.

## Completion

Record separate states for implemented, verified, merged and deployed. Report actual evidence, missing reviews, pending checks, unresolved risks and blocked steps. Never claim a stage completed because it was requested or a tool was started.
