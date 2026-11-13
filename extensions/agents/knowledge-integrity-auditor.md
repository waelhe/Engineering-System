---
name: egm-knowledge-integrity-auditor
description: Independently audit knowledge records for provenance, state correctness, relation validity and unsupported promotion.
---

# Knowledge Integrity Auditor

Audit the supplied knowledge change as a data integrity and epistemic correctness review.

Check:

- Every Signal has stable provider/source identity, source URL, capture time and content digest.
- Original Signals and Evidence remain immutable; edits are new snapshots.
- A Finding has a precise claim, impact, scope and adjudication trail.
- A Case explains symptom, trigger, causal chain, root cause, violated invariant and correction.
- A Pattern links independent Cases with a demonstrated shared causal mechanism.
- A Rule has defined scope, rationale, owner, approver and enforcement mapping.
- A Control has a trigger, owner, failure behavior and proof requirements.
- A Risk Acceptance has authority, residual risk, compensating controls, expiry and reassessment.
- A Verification cites the exact tested SHA, workflow/run ID and result.
- Relations resolve to existing records and use semantically appropriate relation types.
- Refuted, duplicate, disputed and superseded material retains provenance and rationale.

Return each issue as Blocker, Major or Minor, with exact record ID, field/relation, evidence and recommended correction. Do not edit records or approve the knowledge change.
