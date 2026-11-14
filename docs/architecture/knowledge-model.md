# Knowledge Model

**Status:** Proposed canonical model  
**Contract:** schemas/knowledge-record.schema.json

## Distinguish observations from accepted knowledge

An external event first enters as a **Signal**. A signal can be duplicated, incomplete, misleading, malicious, or unrelated. Triage may attach one or more immutable **Evidence** records to a **Finding**. Investigation may establish a **Case** with a supported causal explanation. Repeated cases may justify a **Pattern**. Approved **Rules**, **Decisions**, and **Controls** constrain future work.

A raw model response must never be promoted directly into a verified Finding, Pattern, or Rule.

## Canonical entities

| Entity | Meaning | Mutation model |
|---|---|---|
| Project | Repository, product, modules, technology and policy profile | Versioned |
| Signal | Untriaged event received from GitHub, CI, tests, incident or human | Append-only |
| Evidence | Validated pointer or retained artifact supporting a claim | Append-only; corrections are new records |
| Finding | Investigated issue, defect, gap or risk with explicit disposition | State transitions |
| Case | Reconstructed episode: symptom, trigger, causal chain, invariant, correction and proof | Versioned |
| Pattern | Causal mechanism supported by linked Cases, not merely matching text | Versioned |
| Decision | Approved engineering choice, rationale and alternatives | Supersedable |
| Rule / Invariant | Normative constraint future work must preserve | Approved versions |
| Control | Test, check, guard, review or process enforcing a rule | Versioned |
| Action | Tracked remediation/prevention work with owner and measurable acceptance | State transitions |
| Risk Acceptance | Explicit, bounded, expiring authorization to retain a known risk | Immutable decision + lifecycle |
| Verification | Evidence that a fix/control was exercised against exact code and environment, or that an approved alternate operational proof was satisfied | Append-only |

## Finding closure proof modes

A closed Finding declares one explicit `closure_mode`:

- `code_defect`: the linked Action must have a successful Verification whose workflow and target-inclusion proof bind the same tested SHA; the proof URL is retained as a source.
- `alternate_proof`: for a non-code or non-reproducible case, the Finding records an approved same-project Decision or Control, source-linked operational Evidence, a same-owner Action with measurable acceptance, and the test limitation. If residual risk remains, a reassessment date is required.

A general Verification record is not required to contain target-branch inclusion merely because it verifies an operational Control. Target inclusion is a closure requirement for reproducible code defects.

## State dimensions are separate

Do not collapse epistemic confidence, workflow lifecycle, and approval into one status.

### Assessment
- observed: source event or behavior directly observed.
- suspected: causal interpretation plausible but unproven.
- verified: claim supported by sufficient evidence for its stated scope.
- refuted: evidence disproves the claim.
- superseded: a later verified record replaces this claim for current use.

### Lifecycle
new, untriaged, triaging, investigating, action_required, resolved_pending_proof, open, closed, reopened, active, expired, withdrawn.

### Approval
not_required, proposed, in_review, approved, rejected, withdrawn.

An accepted risk is its own entity; it is not a synonym for a fixed defect or a verified fact.

## Required provenance

Every durable record includes a stable identifier, project scope, record type, title, timestamps, actor, source references, and relations. Claims cite evidence IDs or explicitly state why they are decisions rather than empirical facts.

A GitHub/CI evidence reference carries, where applicable: repository and PR/issue number; workflow name and run ID; tested commit SHA and branch/ref; conclusion and timestamp; canonical source URL; exact check/test/scenario and affected path; artifact digest.

Do not copy secrets, credentials, private payloads, or unnecessary personal data into the knowledge store.

## Relation semantics

- Signal supports or challenges Evidence/Finding.
- Evidence supports or refutes a Claim/Case.
- Finding reconstructed_as Case.
- Case exhibits Pattern.
- Pattern motivates Rule.
- Decision constrains Project/Module/Rule.
- Rule enforced_by Control.
- Control verified_by Verification.
- Finding/Case resolved_by Action.
- Action proven_by Verification.
- Recurrence reopens a closed Finding/Case.

The validator checks references and allowed relation types. Similarity alone never creates a causal relation.

## Root-cause quality

A Case should distinguish:
1. observed symptom and impact;
2. trigger and preconditions;
3. original assumption or missing control;
4. causal chain;
5. violated invariant or contract;
6. root cause and contributing factors;
7. correction and preventive actions;
8. verification evidence;
9. recurrence risk and search scope.

"Missing test" is usually a contributing control gap, not automatically the root cause.

## Immutability

Signals and Evidence are append-only. If an external event is edited, create a new observation/version and retain the previous source digest. Findings, Cases, Patterns, Decisions, and Rules may evolve, but state changes preserve history through Git commits and explicit supersession. Never delete a false positive or duplicate source; change its disposition and link it to the canonical record.
