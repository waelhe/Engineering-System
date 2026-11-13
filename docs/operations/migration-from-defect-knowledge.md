# Migration: Existing Defect Knowledge to the Unified EGM Store

**Status:** Planned; no source records migrated by this document.

## Source boundary

The current historical material is in waelhe/app-java-v3, primarily docs/governance/defect-knowledge/, together with associated CI validators, intake workflows and PR #834 changes. PR #834 is not assumed merged or verified by this migration plan; every source ref and source revision must be re-read before import.

## Mapping

| Legacy artifact | Canonical destination |
|---|---|
| Evidence ledger | Cases + Evidence; preserve original identifiers and source refs |
| Pattern catalog | Patterns; each Pattern links to supporting Cases and retains verified/hypothesis distinction |
| Rulebook | Rules; retain scope, rationale, source and approval state |
| Enforcement map | Controls + Rule-to-Control relations + verification history |
| Change protocol | Project/task policies or execution receipts, not defect records |
| Review protocol | Shared review policy, with project-specific addenda where needed |
| Review findings index | Signals/Findings after individual adjudication; comments remain Signals until triaged |
| Per-PR receipts | Execution Receipts and Verifications; preserve exact tested SHA and workflow evidence |
| Intake scripts/workflows | Re-implement adapters against this model; do not preserve old schemas as a second store |
| Agent protocol/skill | EGM Core Charter and project/domain profiles after contradiction review |

## Migration controls

1. Snapshot source repository refs, branch heads, PR states and file digests.
2. Inventory every record and references before transformation.
3. Preserve original identifiers in legacy_ids and exact source URLs/SHAs.
4. Convert only records whose structure and provenance are understood.
5. Mark uncertain claims as suspected/needs_triage; never upgrade confidence.
6. Deduplicate canonical entities without deleting source observations.
7. Compare source and destination counts by record class and reference graph.
8. Run validators and human sample review of every entity family.
9. Perform dry-run import and publish a reconciliation report.
10. Cut over only after approval; then mark the old system archived/non-authoritative.

## Prohibited shortcuts

- Do not bulk-copy Markdown and call it a migration.
- Do not treat PR comments as confirmed defects.
- Do not assume all statuses called fixed were proven against the right SHA.
- Do not collapse cases because symptoms or fingerprints match without causal review.
- Do not discard historical evidence, open findings or unresolved review threads.
