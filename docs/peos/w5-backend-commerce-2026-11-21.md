# W5 — Backend and commerce outcomes: current evidence

**Snapshot:** 2026-11-21  
**Backend source:** `waelhe/app-java-v3/main@8ab2c667aef190b58d88cb116d8ce004bf948cf9`  
**Machine registry:** `registry/peos/app-java-v3.w5-backend-commerce.json`  
**Purpose:** refresh the historical PR queue and risk snapshot against current GitHub heads without treating a green check, a mergeable flag, or a branch-only implementation as product completion.

## Current state

GitHub returned 25 open pull requests in `app-java-v3`. The single full-commerce release candidate remains PR #787. Its head is `aa05af4494615fa299abba78091970c5a3a25c56`, with base at the captured current main SHA. The canonical-plan, container, OpenRewrite, Integration Test, Android client and CodeQL workflows completed successfully; the general CI workflow was still queued at capture. Review shards #806–#811 remain tracking-only / DO_NOT_MERGE and are not alternate merge candidates.

## High-impact candidate queue

| PR | Area | Captured workflow state | Remaining control |
|---:|---|---|---|
| #787 | Full commerce promotion | Six workflows success; CI queued | Current CI, review coverage and governed promotion |
| #839 | Railway deployment repair | Integration, canonical plan, OpenRewrite, CodeQL and container success; CI queued | CI and a successful post-merge production deployment |
| #840 | Resend HTTPS email transport | CI, Integration Test, OpenRewrite, Container Scan and CodeQL failed | Diagnose every failed workflow and rerun on repaired head |
| #832 | Delivery-fee/courier ledger model (A1) | Five workflows success; CI in progress | Owner decision on accounting treatment remains a hard gate |
| #831 | Delivery refund/completion concurrency (A3) | Observed workflows success | Prove recognition/refund symmetry and both event orders |
| #828 | Refund transaction boundary (A4/B2) | Observed workflows success | Exact-head review/coverage and post-merge financial proof |
| #833 | Account media erasure (G3) | Five workflows success; CI in progress | Prove permanent object-version deletion under actual bucket settings |
| #827 | PSP absence response contract (W3) | Observed workflows success | Exact-head review/coverage and post-merge money-path proof |
| #822 | Identity mail-link origin (W2) | Observed workflows success | Current-head review and post-merge link-origin verification |
| #847 | CodeRabbit skipped-file coverage | Observed workflows success | Exact-head review and fail-closed coverage verification |
| #842 | CodeRabbit coverage declaration parser | Merged 2026-11-19 | Historical merged repair; do not track as open work |

Exact heads and per-workflow conclusions are preserved in the registry. A skipped retired-plan guard is not counted as a passing functional check. Queued and in-progress runs are not successes.

## Controls and decisions

1. PR #787 remains the one full-commerce candidate; do not merge the six tracking shards.
2. A1 (#832) remains blocked by the conflict between the accepted accounting decision and the candidate's alternate seller/clearing postings. No implementation should silently choose either treatment.
3. A3 (#831) remains semantically open until the recognition path uses the same per-delivery lock and the refund/recognition event-order cases are proven against PostgreSQL.
4. G3 (#833) does not establish permanent deletion of prior S3 object versions without inspecting bucket versioning and retention and testing version-ID deletion.
5. #840 has observed failed workflows and is not a merge candidate until their causes are fixed and a new exact-head run succeeds.

## Exit evidence for W5

- A current dependency/PR graph, not the 2026-11-14 W0 list.
- Exact-head CI and review coverage for every candidate.
- Owner-authorized resolution for accounting choices.
- Real PostgreSQL concurrency and financial-invariant tests.
- GraphQL/OpenAPI compatibility and client contract evidence.
- Post-merge verification tied to the actual main SHA.

This snapshot is descriptive evidence only. It does not merge PRs, approve owner decisions, deploy production, or claim that commerce journeys are complete.
