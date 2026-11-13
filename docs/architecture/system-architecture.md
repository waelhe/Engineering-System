# EGM Engineering Knowledge & Development System

**Status:** Proposed architecture baseline  
**Decision:** One system, one repository, one knowledge authority  
**Upstream:** Google EGM v0.1.1, pinned in the upstream lock.

## Purpose

Extend the Elephant–Goldfish Model from a design-and-review plugin into an evidence-backed engineering operating system. It manages the lifecycle of engineering work: intake, context acquisition, design, independent review, implementation, verification, and learning.

This is not a defect tracker with an AI layer, nor a collection of independent knowledge tools. Its knowledge model, workflows, policies, adapters, and verification mechanisms are one product and one source of truth.

## Principles

1. EGM is the workflow foundation. Preserve Elephant context, Goldfish isolation, review stages, document standards, and harness-aware behavior.
2. Knowledge is a first-class subsystem: structured, versioned, traceable, queryable, and governed.
3. Evidence precedes conclusions. Signals are not findings; findings are not root causes; AI suggestions are not approved rules.
4. One canonical record. Do not maintain a second defect-knowledge system. Legacy material is migrated into this model and retired as an operational authority only after reconciliation.
5. Progressive disclosure. Load the minimum relevant context first, then retrieve deeper records and raw evidence.
6. Independent review is a runtime property. A Goldfish verdict is independent only if the harness provides a genuinely fresh context and the system records how this was established.
7. Policies must be enforceable. Each important policy maps to a deterministic validator, a workflow receipt, or explicit human authorization.
8. No unnecessary infrastructure. Initial storage is Git-backed JSON/Markdown with deterministic indexes and standard-library tools. No database, broker, vector store, or search cluster is introduced without measured need.
9. Upstream is pinned; local extensions are explicit. Do not silently drift from EGM upstream or overwrite upstream-owned files with local changes.

## Logical components

| Component | Responsibility | Initial implementation |
|---|---|---|
| Knowledge Model | Entity types, states, relations, provenance | JSON Schema + policy |
| Knowledge Store | Canonical versioned records | Git-tracked JSON/Markdown |
| Knowledge Retrieval | Task-scoped progressive disclosure | Deterministic lexical/metadata retrieval |
| Knowledge Intake | Preserve external signals safely | File-based inbox and source adapters |
| Knowledge Reasoning | Investigate causes and propose patterns/rules | EGM skills and reviewed artifacts |
| EGM Workflow | Elephant, Goldfish, design and resolve | Pinned upstream EGM plus local skills |
| Execution & Verification | Receipts, tests, SHA and workflow proof | Python CLI + CI |
| Governance & Learning | Approval, enforcement, recurrence, migration | Policies, records and gates |

## Runtime topology

1. A human or coding agent invokes an EGM skill.
2. The task is classified into T0–T3.
3. A task context builder reads the project profile, relevant policies, and knowledge index.
4. Elephant receives a source-linked knowledge pack.
5. Goldfish reviewers receive only their designated context package in verified fresh sessions.
6. The executor follows an approved plan and write boundary.
7. Verification records are captured against exact commit SHAs and workflow runs.
8. The learning workflow proposes updates; validators check structure and relations; authorized reviewers approve knowledge changes.

No long-running service is required. Git history is the audit log; CI is the execution evidence source.

## Trust boundaries

External GitHub text, review comments, issue bodies, CI logs, artifacts, and model output are untrusted data. They may be stored as evidence with provenance, but they are never executable instructions. Intake must not checkout or execute untrusted PR code in privileged workflows, interpolate untrusted text into shell commands, or grant write-capable credentials to an untrusted event handler.

Knowledge changes are made through pull requests and checked by schema, reference, immutability, and policy validators. Human approval is required for architectural decisions, binding rules, accepted risks, and migration cutover.

## Failure behavior

- Missing or inaccessible source: mark evidence incomplete; never infer success.
- Stale SHA or workflow mismatch: verification fails.
- Missing independent reviewer capability: review is not_run or blocked, never passed.
- Duplicate source event: retain source identity and return the prior signal; do not create another signal.
- Similar but unproven root causes: keep separate findings and propose a pattern for review.
- Invalid relation: block knowledge-index generation and CI.
- Policy conflict: stop the affected transition and record the conflict.

## Quality attributes

Correctness, traceability, security boundaries, reproducibility, portability across agent harnesses, offline validation, low operational overhead, and reversible migration are first-order requirements.
