# Legacy Knowledge Migration Policy

This policy governs conversion of the former defect-knowledge system in \`waelhe/app-java-v3\` into the unified EGM store.

## Provenance

- Main baseline: \`f92873c947e94c76ed3e7ea211db40a985ea3d63\`.
- Candidate source: PR #834 head \`f49bd15d186cf8be50c04e848b197faab3dfb47d\`.
- The candidate is not merged. Every imported record retains this exact source revision and a GitHub permalink to the original source section.
- A source document saying \`[VERIFIED]\` is recorded as a legacy classification, not silently promoted to an EGM-approved rule or a newly verified root cause.

## Conversion rules

1. Preserve source IDs (E-xx, Pn, A/B/C/D IDs, finding IDs) in \`legacy_id\`.
2. Preserve the complete source case/rule/pattern excerpt in \`legacy_excerpt\`.
3. Preserve exact source URLs, commit SHA, PR/issue numbers, source timestamps and source document line anchors.
4. Keep epistemic assessment, operational lifecycle and approval separate.
5. Map \`fixed-main\` and equivalent source claims to \`resolved_pending_proof\`, not \`closed\`, until the new system has the named regression test, an API-verified successful run on the tested SHA, and target-branch inclusion.
6. Map fixes on open PRs and candidate-only fixes to \`open\`.
7. Preserve suspected findings as \`suspected\` and \`investigating\`; do not convert them to confirmed defects.
8. Do not count review comments as defects. Preserve their aggregate counts as evidence with an explicit counting policy.
9. Do not create duplicate Cases from \`separateHistoricalCases\` when the same E-ID already exists in the evidence ledger. Attach the additional issue/PR source to the existing Case.
10. Keep human decisions, capability gaps, accepted risks and code defects as distinct classifications.
11. Import binding rules and enforcement controls as proposed until their owner and current control proof are explicitly reviewed under the unified governance process.
12. A rerun of the same batch must be deterministic. Existing records are not overwritten when their content differs; the migration must stop and require reconciliation.

## Cutover

The unified store becomes the sole operational knowledge authority only after:
- source and destination record counts reconcile by entity class;
- every migrated record resolves all relations;
- imported source excerpts and exact source revisions are retained;
- no source signal or case is dropped or silently duplicated;
- a sample from each entity family receives independent review;
- the legacy operational workflows are explicitly retired or redirected after a reviewed cutover.

Until then, the old repository remains the source of historical evidence and the unified records are a provenance-linked migration candidate.
