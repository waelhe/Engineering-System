# Knowledge Governance and Learning Policy

## Admission

- Every incoming event is a Signal with provider, source identity, capture time, project scope and content digest.
- Duplicate delivery is idempotent, but original source provenance remains queryable.
- Human triage and machine classification are separate fields. A classifier can recommend, never silently decide.
- Evidence is admitted only with traceable source and explicit scope.
- Findings require a claim, impact, status, evidence and adjudication trail.
- Cases require causal analysis, not only an error description.
- Patterns require linked independent Cases and a shared causal mechanism.
- Rules require a defined invariant, scope, rationale, owner/approver and enforcement mapping.
- Risk acceptance requires authorized approver, residual risk, compensating controls, expiry and reassessment.

## Lifecycle and history

Append-only source records are never overwritten. Mutable entities carry state-transition history through versioned Git changes and explicit supersession. Reopening a case preserves earlier closure proof.

## Promotion gates

| Promotion | Minimum evidence |
|---|---|
| Signal -> Evidence | Valid source identity, integrity, scope and triage |
| Evidence -> Finding | Specific claim and corroborating evidence or authorized policy-gap disposition |
| Finding -> Case | Reconstructed cause, trigger, invariant and alternatives considered |
| Case -> Pattern | Multiple independent cases with shared causal explanation |
| Pattern -> Rule | Explicit scope, approval and enforceability |
| Rule -> Control | Tested mechanism, owner, trigger and failure behavior |
| Control -> Proven | Successful verification on an identified revision/environment |

## Learning quality

Every confirmed Case asks: Are there sibling entry points or alternate paths? Are other modules using the same mechanism? Which invariant was not protected? Can a test/guard/static recipe catch it earlier? Did the existing guard fail, and why? What evidence would show non-recurrence?

Retain refuted hypotheses and false positives with rationale because they prevent repeated investigation.
