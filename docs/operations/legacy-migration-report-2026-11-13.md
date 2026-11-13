# app-java-v3 Defect Knowledge Migration Report — 2026-11-13

**Status:** Candidate import created; no cutover and no source deletion.  
**Source main baseline:** \`f92873c947e94c76ed3e7ea211db40a985ea3d63\`  
**Source candidate:** \`app-java-v3 PR #834 @ f49bd15d186cf8be50c04e848b197faab3dfb47d\`

## Imported entity families

The source corpus is normalized into the canonical knowledge model. IDs are preserved in \`legacy_id\`; full source section text and exact GitHub line permalinks are preserved.

| Source family | Records | Destination |
|---|---:|---|
| Evidence ledger cases E-01…E-52 | 52 | Cases |
| Causal patterns P1…P15 | 15 | Patterns |
| Engineering rules A1…A6, B1…B8, C1…C4 | 18 | Rules |
| Automated controls D1…D12 | 12 | Controls |
| Individually adjudicated review findings | 39 | Findings |
| Capability/decision gaps ISSUE-774…ISSUE-782 | 7 | Findings with explicit gap classification |
| Repair-PR review reconciliations | 5 | Evidence records |
| Aggregate audit/review/adversarial snapshots | 5 | Evidence records |
| Project profiles | 1 | Projects |

The 29 \`separateHistoricalCases\` entries E-24…E-52 overlap existing ledger Cases. They were not duplicated. Their source issue/PR URLs and branch-aware dispositions were attached to the corresponding Case records.

## Disposition mapping

- The source label \`[VERIFIED]\` is preserved in \`legacy_assessment\`; the imported record is not automatically EGM-approved.
- \`fixed-main\` is mapped to \`resolved_pending_proof\` until the unified store has the exact regression, successful Actions run, tested SHA, and target-branch inclusion evidence.
- Findings on open or candidate-only PRs remain \`open\`.
- Suspected records remain \`suspected\` and \`investigating\`.
- Rule and Control records remain \`proposed\`; human approval and current enforcement verification are outstanding.
- D11/D12 and G8–G10 are marked as candidate-only in source PR #834, not as mainline controls.

## Counting policy and limits preserved

The source's 715-PR / 14,575-workflow-run / 2,569-failure historical audit is evidence of repository activity, not 2,569 defects.

The six commerce review shards #806–#811 contained 653 review threads and 682 inline CodeRabbit comments in the measured snapshot. Those are raw review signals, not 682 unique defects.

The 19 CodeRabbit fingerprints across repair PRs #819/#821/#822/#823/#829 were retained as five evidence reconciliations; their E-33…E-49 cases remain distinct from the 39 adjudicated findings.

The 34 findings from ADV-2026-11-10 (32 confirmed, 2 suspected) plus W7/W8 and G8–G10 are preserved with their original source report/status. The 7 capability/decision gaps remain separate from defects.

## Outstanding before cutover

1. Re-verify source status and workflow evidence for every finding currently mapped to \`resolved_pending_proof\`.
2. Independently review the imported Patterns, Rules and Controls; no rule is binding merely because the old rulebook stated it.
3. Re-run the source PR #834 final-head CI and review status; PR #834 is still unmerged in the source snapshot.
4. Implement live GitHub review/CI intake in this repository using least-privilege capture and trusted-base processing.
5. Run the independent review sample and produce an automated source/destination no-loss reconciliation.

The import deliberately preserves uncertainty rather than manufacturing closure. No legacy source data was deleted or edited.
