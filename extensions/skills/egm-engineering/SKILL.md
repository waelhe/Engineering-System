---
name: egm-engineering
description: Orchestrate engineering work through EGM with risk classification, project context, knowledge retrieval, independent review, controlled implementation, verification and learning.
---

# EGM Engineering Orchestrator

Use this skill as the entry point for engineering tasks. It does not replace the upstream EGM design and review skills; it coordinates them with the canonical knowledge store and execution policies.

## Required intake

1. Identify the active project/repository and target ref from the workspace, not from memory.
2. Read the Core Engineering Charter and Task Classification and Risk Policy from the installed system resources.
3. Discover root and nested repository instructions, CI policy, code owners, ADRs and applicable technology profiles.
4. Classify the task T0–T3 using its highest credible impact. Escalate when a risk trigger appears.
5. For T1–T3, create or update an execution receipt and define the affected scope, write allowlist, checks and authority gates.
6. Use the knowledge retrieval skill to build a source-linked context pack before proposing a fix or design.

## Routing

- T0: answer the request or perform read-only investigation. Do not create ceremony for a simple inquiry.
- T1: use targeted investigation and verification. A design pipeline is unnecessary unless a design decision is genuinely open.
- T2: use upstream EGM brainstorm/draft/review for non-trivial feature and architecture decisions; resolve findings; require an implementation-readiness plan before code changes.
- T3: use the full relevant EGM review lenses, including security, data/concurrency, architecture and implementation readiness. Require human approval at the authority boundaries defined by policy.

## Execution

- Delegate design and review to upstream EGM skills and reviewers. Do not simulate a fresh Goldfish in the authoring context.
- Invoke the implementation skill only with an approved plan and explicit file allowlist.
- Invoke verification after implementation; do not treat a successful build alone as completion.
- Invoke the learning skill to triage newly discovered review, test, CI and incident signals.
- Keep independent work moving while asynchronous checks run, without bypassing required checks or dependencies.

## Completion

Record separate states for implemented, verified, merged and deployed. Report actual evidence, missing reviews, pending checks, unresolved risks and blocked steps. Never claim a stage completed because it was requested or because a tool was started.
