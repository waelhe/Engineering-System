# Knowledge Lifecycle and Closed-Loop Learning

~~~mermaid
flowchart TD
  A[External source or agent observation] --> B[Signal inbox]
  B --> C[Normalize and deduplicate identical source snapshots]
  C --> D[Triage: relevant, duplicate, noise, security]
  D --> E[Evidence record]
  E --> F[Finding investigation]
  F --> G{Claim supported?}
  G -->|No| H[Refute or keep suspected]
  G -->|Yes| I[Reconstruct Case]
  I --> J[Search sibling paths and historical cases]
  J --> K[Propose Pattern, Rule and Actions]
  K --> L[Independent review and human approval]
  L --> M[Control implementation]
  M --> N[Verification on exact SHA and environment]
  N --> O{Proof valid?}
  O -->|No| P[Keep open / reopen]
  O -->|Yes| Q[Close with evidence]
  Q --> R[Monitor for recurrence]
  R -->|same causal mechanism reappears| F
~~~

## Intake

Sources include GitHub issue and PR comments, formal review submissions, CodeRabbit/Copilot findings, CI failures, unit/integration/property/fuzz tests, production incidents, security scans, and human reports.

Intake deduplicates at the immutable snapshot level. The Signal ID is project-scoped and binds `project_id`, source identity (`provider:repository:source_id`), and a SHA-256 digest of the supplied body. Redelivery of that same project/source/body snapshot returns the existing Signal; a changed body creates a new immutable snapshot. Title-only changes do not create a new snapshot because title is retained metadata, not part of the digest. For the GitHub review collector, the supplied body is a serialized snapshot of review/comment fields (including `updated_at`, path/line and commit metadata), not merely the human comment text. A changed `updated_at` creates a new snapshot only when the serialized payload fits within the 250,000-character intake limit. When the payload exceeds that limit, the collector truncates the serialized body before intake computes its digest; fields beyond the truncation boundary (including `updated_at` when it falls there) do not contribute to the digest. A timestamp-only change in that omitted portion can therefore return the existing Signal. Untrusted content is stored as data; intake does not create a confirmed defect or alter a human triage decision.

## Investigation

The investigator searches relevant code paths, alternate entry points, consumers, tests, recent changes, and historical sibling cases. The result separates facts, hypotheses, decisions, and unknowns. A single reviewer comment is a signal until corroborated or accepted by an authorized human as a non-code policy gap.

## Learning

A confirmed Case may produce:
- a new or updated Pattern when causal similarity is demonstrated across independent cases;
- a proposed Rule or Invariant when future work must preserve a property;
- Actions with a responsible owner and measurable acceptance criterion;
- a Control (regression/property test, fuzzer corpus, static rule, CI guard, or review procedure);
- Verification records linking the control and repair to the tested commit/environment.

A new Pattern does not automatically imply a universal Rule. Rules require scope, rationale, owner/approver, exceptions, and an enforcement strategy.

## Closure and recurrence

A code defect is not closed because a commit exists. Closure requires a reproducer or justified alternative, a regression test where feasible, successful verification tied to the intended SHA, proof that the fix reached the target branch, and a recurrence policy.

If the same causal mechanism appears again, link the new evidence to the prior Case/Pattern and reopen the durable Finding or create a linked recurrence Finding. Preserve prior closure evidence; do not rewrite history.

For intermittent, external, organizational, or architectural problems where a deterministic regression test is not reasonable, define an alternate proof contract before closure: accepted design decision, control owner, operational evidence, review outcome, test limitation, and reassessment date if residual risk remains.
