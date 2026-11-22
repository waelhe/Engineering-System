# W4 — Critical-risk prioritization and proof ledger

**Snapshot:** 2026-11-17
**Upstream source:** waelhe/app-java-v3/main at 8b1d2a82bf5c870d88ffc7d5d05e36bb06175c26
**Registry:** registry/peos/app-java-v3.critical-risks.json
**Authority:** operating-model.md §9 (W4), ADR-0013, owner-gate recommendation in PR #826, and official documentation linked below.

## Scope and capture boundary

This is a point-in-time, read-only assessment of seven high-impact candidate changes. It uses exact PR heads, base SHAs, compare results, check-runs, review submissions and source-blob identities. It does not copy underlying EGM defect or evidence bodies: the registry stores only risk summaries and references to authoritative source artifacts and PR records.

No source file in app-java-v3 was changed. No PR was merged. No production service, configuration, database, object store, notification destination or deployment was mutated.

## Decision rules

1. A passing build is not a completed PR. A PR remains open until repository review and protection requirements are satisfied.
2. CI and review evidence are accepted only when bound to the exact PR head SHA. A CodeRabbit check marked skipped is not a review.
3. The current CodeRabbit gate has two effective stages: (a) a completed acceptable review on the current head, then (b) explicit processed-file coverage evidence. A review approval can satisfy stage (a) while the job still fails stage (b).
4. A branch behind or diverged from current main must be synchronized and retested; its previous green checks do not prove the new head.
5. A risk is closed_verified only after its change is merged into main and post-merge verification is linked to the exact verified main SHA. This snapshot closes none of the seven risks.

## Current priority order

| Risk | Priority | Current assessment | PR | Head SHA |
|---|---:|---|---:|---|
| A1 — delivery-fee funding and courier compensation | P0 | Blocked by a recorded decision conflict | #832 | ff0af304e9bc5e35890456bea190566e3e6ed50a |
| A3 — refund-delta concurrency and event ordering | P0 | Partial lock implementation; missing recognition-side symmetry | #831 | a73d453aa11f7228e4eff395e0940e0c90ebf8a6 |
| A4/B2 — refund transaction boundary and identity erasure | P0 | Candidate review exists, but coverage verifier fails | #828 | b25c8e7086b500711fcdb073508af414e204b8e4 |
| W3 — PSP absence error contract | P0 | Exact-head review exists; coverage verifier fails; branch stale | #827 | 84c14efcdaa962f09064b5543eb11c8c93cd75c0 |
| G3 — account media erasure | P0 | Batch purge exists; permanent version erasure unproven | #833 | 3ee5713760e17164811a4362f9f601fb782efb88 |
| W2 — mail link origin configuration | P1 | Exact-head review missing; branch stale | #822 | 2bc484f6a5ed51631bb2c5e15243be0b6da12889 |
| W8 — CodeRabbit coverage verifier | P0 | Candidate fix added, but its own head still needs review | #842 | a94fa6fd4ded45d654cc5b7eb88d071d7e5953b2 |

## 1. A1 — delivery-fee funding / courier compensation

**Decision conflict — do not merge #832 until resolved.**

The accepted ADR-0013 on the captured main source identifies the platform as merchant of record and states that the platform keeps the delivery fee to fund the carrier. The owner-gate recommendation in PR #826 makes this more specific: it recommends that the seller's balance not be touched by the delivery fee, and that the dedicated delivery journal records debit to delivery-fee revenue and credit to courier payable.

The unmerged #832 branch adds ADR-0014 and implements a different ledger interpretation: a seller-side DELIVERY_FEE debit plus a dedicated-journal PSP_CLEARING claim debit and courier payable. The ADR is branch-only, not merged, and must not be treated as silently superseding the owner-gate recommendation. These alternatives produce different seller balances and accounting traces.

The PR has a CodeRabbit approval on its exact head and no non-gate check failures in the captured check-run set. Its re-run accepted the exact-head review but failed the subsequent coverage verifier: the review did not supply an explicit processed-file declaration. That CI state does not settle the accounting conflict.

**Next closure gate:** record the owner-authorized accounting treatment against ADR-0013 D1/D4 and the owner-gate recommendation, then align seller postings, carrier payable, refund mirror and reconciliation tests to that one treatment.

## 2. A3 — delivery refund-delta race

PR #831 introduces pg_advisory_xact_lock before the refund path reads the latest cumulative refund and posts the delta. This correctly targets the measured refund/refund race within that method.

The inspected candidate does not yet satisfy the full A3 recommendation: recognize() does not take the same per-delivery lock; it posts the gross completion amount instead of reconciling refunds that may have arrived first; and it does not implement the R = G rule where revenue is zero but the already-earned courier payable remains due and is charged to DELIVERY_REFUNDS. The candidate also has not demonstrated both event orders under concurrency. The branch is two commits behind the captured main and has no exact-head CodeRabbit review; a review request was posted.

**Next closure gate:** use the same key and transaction boundary in refund() and recognize(), prove READ COMMITTED visibility after lock acquisition, implement G - R recognition and the zero-revenue courier-payable rule, then test both event orders and concurrent webhook snapshots using real PostgreSQL.

## 3. A4/B2 — refund transaction and identity erasure

PR #828 is based on the current main SHA. Its current head has a CodeRabbit APPROVED review; all captured non-gate check runs were successful. After the gate rerun, the review stage passed, but the processed-file coverage step failed with: CodeRabbit omitted its explicit processed-file list.

This is a review-evidence/coverage blocker, not an observed failing application test. It still blocks PR completion. The PR remains open and has no post-merge proof.

**Next closure gate:** validate the coverage-verifier fix on #842, rerun #828's coverage gate against its exact head, then capture post-merge tests for refund rollback/idempotency and the relevant identity-erasure behavior.

## 4. W3 — missing PSP channel

PR #827 has an exact-head CodeRabbit review sequence ending in COMMENTED, after an APPROVED review on the same SHA. The rerun's first review stage passed. The subsequent coverage verifier failed because it could not find an explicit processed-file declaration. The branch comparison is diverged: five commits ahead and three behind the captured current main.

**Next closure gate:** repair the review-coverage evidence without weakening the fail-closed policy, synchronize with current main and rerun the money-path integration/API contract tests against the new head.

## 5. G3 — account-erasure media purge

PR #833 improves the bounded deletion path: it deduplicates known object keys, sends batches of no more than 1,000 keys, and surfaces per-key errors. Those are useful implementation improvements, but they do not prove permanent object-version destruction.

The inspected S3MediaStorage.deleteObjects builds each ObjectIdentifier with a key and no version ID. AWS's official documentation states that, in a versioning-enabled bucket, a key-only delete adds a delete marker; it does not permanently delete existing object versions. The same issue applies to versioning-suspended buckets for existing non-null versions. The actual production bucket's provider, versioning mode, Object Lock and retention settings were not inspected, so this is a conditional gap, not a claim about the live bucket's configuration.

Sources:
- AWS: [Deleting object versions from a versioning-enabled bucket](https://docs.aws.amazon.com/AmazonS3/latest/userguide/DeletingObjectVersions.html)
- AWS: [Deleting Amazon S3 objects](https://docs.aws.amazon.com/AmazonS3/latest/userguide/DeletingObjects.html)
- AWS: [Troubleshooting versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/troubleshooting-versioning.html)

The branch is two commits behind current main and lacks an exact-head CodeRabbit review; a fresh review request was posted.

**Next closure gate:** inspect actual bucket versioning/retention through the authorized provider API. Where versioning is enabled or suspended, use the documented version-list and version-ID deletion flow (including delete markers where applicable), and prove the behavior with provider-compatible integration tests. Test unversioned buckets, versioned buckets, suspended buckets, batches over 1,000, partial failures and idempotent reruns.

## 6. W2 — identity mail-link origin

PR #822 changes mail-link origin validation and its deployable profile/documentation paths. No exact-head CodeRabbit review was present in the captured review submissions; a fresh review request was posted. The branch is diverged from current main, eight commits ahead and three behind.

**Next closure gate:** review the current head, synchronize the branch, then rerun the configuration-binding, redirect-origin and email-link integration tests on the resulting SHA.

## 7. W8 — CodeRabbit review-coverage verifier

PR #842 is the candidate fix for the downstream coverage error. Its diff selects the latest accepted CodeRabbit review on the exact candidate SHA that contains the explicit Files selected for processing declaration, rather than reading only the newest (possibly empty-bodied) approval. It adds tests for a declaration followed by an empty approval, empty approval alone, stale-head declarations, changes-requested declarations, malformed declarations and newest-declaration precedence.

This direction preserves fail-closed behavior: an empty approval is not treated as file-coverage proof. However, #842 itself had no completed exact-head CodeRabbit review when captured, and its own gate was still failing. A fresh review request was posted.

**Next closure gate:** obtain exact-head review and coverage for #842; after it is merged under repository protection, rerun the affected coverage gates on #827/#828/#832 and confirm every changed path is accounted for by current source blob identity.

## Official technical basis

- PostgreSQL advisory locks: [Explicit locking — advisory locks](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)
- PostgreSQL isolation: [Transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- AWS S3 versioned deletion: official links above.
- Stripe Connect charge ownership and separate charges/transfers: [Charge types and merchant of record](https://docs.stripe.com/connect/charges), [Separate charges and transfers](https://docs.stripe.com/connect/separate-charges-and-transfers), and [Application fees](https://docs.stripe.com/connect/direct-charges#application-fees).

## Snapshot conclusion

W4 is implemented as a risk inventory and deterministic proof gate, not as a claim that the seven risks are resolved. The highest-severity items remain blocked or partial until their exact gates are met. The unmerged candidates are not a substitute for main-branch and post-merge evidence.
